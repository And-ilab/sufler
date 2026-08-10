from __future__ import annotations

from typing import Any

from django.db import transaction
from django.db.models import Count, F, Q
from django.utils import timezone

from online_chat.models import (
    Department,
    Dialog,
    DialogEvent,
    OperatorProfile,
    RoutingRule,
    WidgetPlacement,
)


def record_event(
    dialog: Dialog, event_type: str, *, actor_name: str = "", payload: dict[str, Any] | None = None
) -> DialogEvent:
    return DialogEvent.objects.create(
        dialog=dialog, type=event_type, actor_name=actor_name, payload=payload or {}
    )


def _conditions_match(conditions: object, context: dict[str, Any]) -> bool:
    if not isinstance(conditions, dict):
        return False
    for key, expected in conditions.items():
        if key == "max_load":
            continue
        actual = context.get(key)
        if isinstance(expected, list):
            if actual not in expected:
                return False
        elif actual != expected:
            return False
    return True


def _rule_max_load(conditions: object) -> int | None:
    if not isinstance(conditions, dict):
        return None
    raw = conditions.get("max_load")
    try:
        value = int(raw)
    except (TypeError, ValueError):
        return None
    return value if value > 0 else None


def select_department(
    *,
    widget_id: str = "",
    channel: str = "widget",
    context: dict[str, Any] | None = None,
) -> tuple[Department | None, WidgetPlacement | None, str]:
    placement = WidgetPlacement.objects.filter(widget_id=widget_id, is_active=True).first()
    rules = RoutingRule.objects.filter(is_active=True, department__is_active=True).select_related(
        "department", "placement"
    )
    rules = rules.filter(Q(channel="") | Q(channel=channel))
    if placement:
        rules = rules.filter(Q(placement__isnull=True) | Q(placement=placement))
    else:
        rules = rules.filter(placement__isnull=True)
    rule_context = {"widget_id": widget_id, "channel": channel, **(context or {})}
    for rule in rules:
        if _conditions_match(rule.conditions, rule_context):
            return rule.department, placement, f"routing_rule:{rule.name}"
    if placement and placement.department and placement.department.is_active:
        return placement.department, placement, f"placement:{placement.widget_id}"
    fallback = Department.objects.filter(is_active=True).order_by("priority", "name").first()
    return fallback, placement, "default_department" if fallback else "unrouted"


def department_queue_is_full(department: Department | None) -> bool:
    """True when department waiting queue already reached its configured limit."""
    if department is None or not department.max_queue_size:
        return False
    waiting = Dialog.objects.filter(
        department=department,
        status=Dialog.Status.WAITING,
    ).count()
    return waiting >= department.max_queue_size


def _eligible_operators(dialog: Dialog, *, max_load: int | None = None):
    qs = OperatorProfile.objects.filter(
        is_active=True,
        auto_assign=True,
        presence=OperatorProfile.Presence.ONLINE,
    )
    if dialog.department_id:
        qs = qs.filter(departments=dialog.department)
    annotated = qs.annotate(
        active_count=Count(
            "dialogs",
            filter=Q(dialogs__status=Dialog.Status.ACTIVE),
            distinct=True,
        )
    ).filter(active_count__lt=F("max_active_dialogs"))
    if max_load is not None:
        annotated = annotated.filter(active_count__lt=max_load)
    return annotated.order_by("active_count", "last_seen_at", "display_name")


@transaction.atomic
def accept_waiting_dialog(
    dialog_id: object,
    *,
    operator: OperatorProfile | None = None,
    operator_name: str = "",
) -> Dialog:
    dialog = Dialog.objects.select_for_update().get(pk=dialog_id)
    if dialog.status != Dialog.Status.WAITING:
        raise ValueError("dialog is not waiting")
    if operator:
        locked_operator = OperatorProfile.objects.select_for_update().get(pk=operator.pk)
        active = Dialog.objects.filter(
            operator=locked_operator, status=Dialog.Status.ACTIVE
        ).count()
        if active >= locked_operator.max_active_dialogs:
            raise ValueError("operator capacity reached")
        operator = locked_operator
        operator_name = operator.display_name
    operator_name = operator_name.strip()
    if not operator_name:
        raise ValueError("operator is required")
    now = timezone.now()
    dialog.status = Dialog.Status.ACTIVE
    dialog.operator = operator
    dialog.operator_name = operator_name
    dialog.accepted_at = now
    dialog.save(
        update_fields=["status", "operator", "operator_name", "accepted_at", "updated_at"]
    )
    record_event(
        dialog,
        "accepted",
        actor_name=operator_name,
        payload={"operator_id": str(operator.id) if operator else None},
    )
    return dialog


def _max_load_for_dialog(dialog: Dialog) -> int | None:
    reason = dialog.routing_reason or ""
    if not reason.startswith("routing_rule:"):
        return None
    rule_name = reason.split(":", 1)[1]
    rule = (
        RoutingRule.objects.filter(name=rule_name, is_active=True)
        .order_by("priority", "created_at")
        .first()
    )
    if rule is None:
        return None
    return _rule_max_load(rule.conditions)


def auto_assign_dialog(dialog: Dialog) -> Dialog | None:
    if dialog.status != Dialog.Status.WAITING:
        return None
    max_load = _max_load_for_dialog(dialog)
    for candidate in _eligible_operators(dialog, max_load=max_load)[:20]:
        try:
            return accept_waiting_dialog(dialog.pk, operator=candidate)
        except ValueError:
            continue
    return None


def run_assignments(*, department: Department | None = None) -> list[Dialog]:
    qs = Dialog.objects.filter(status=Dialog.Status.WAITING).order_by("created_at")
    if department:
        qs = qs.filter(department=department)
    assigned: list[Dialog] = []
    for dialog in qs[:500]:
        result = auto_assign_dialog(dialog)
        if result:
            assigned.append(result)
    return assigned


def update_operator_presence(operator: OperatorProfile, presence: str) -> OperatorProfile:
    if presence not in OperatorProfile.Presence.values:
        raise ValueError("invalid presence")
    operator.presence = presence
    operator.last_seen_at = timezone.now()
    operator.save(update_fields=["presence", "last_seen_at", "updated_at"])
    if presence == OperatorProfile.Presence.ONLINE and operator.auto_assign:
        for department in operator.departments.filter(is_active=True):
            run_assignments(department=department)
    return operator


@transaction.atomic
def transfer_to_operator(
    dialog: Dialog, *, operator_id: object | None = None, operator_name: str = ""
) -> Dialog:
    dialog = Dialog.objects.select_for_update().get(pk=dialog.pk)
    target = None
    if operator_id:
        target = OperatorProfile.objects.select_for_update().get(pk=operator_id, is_active=True)
    elif operator_name:
        target = (
            OperatorProfile.objects.select_for_update()
            .filter(display_name=operator_name, is_active=True)
            .first()
        )
    name = target.display_name if target else operator_name.strip()
    if not name:
        raise ValueError("target operator is required")
    if target:
        active = Dialog.objects.filter(
            operator=target, status=Dialog.Status.ACTIVE
        ).exclude(pk=dialog.pk).count()
        if active >= target.max_active_dialogs:
            raise ValueError("operator capacity reached")
    previous = dialog.operator_name
    dialog.operator = target
    dialog.operator_name = name
    dialog.status = Dialog.Status.ACTIVE
    if not dialog.accepted_at:
        dialog.accepted_at = timezone.now()
    dialog.save(
        update_fields=["operator", "operator_name", "status", "accepted_at", "updated_at"]
    )
    record_event(
        dialog,
        "transferred",
        actor_name=previous,
        payload={"from": previous, "to": name, "operator_id": str(target.id) if target else None},
    )
    return dialog
