from __future__ import annotations

import json
import tempfile
from datetime import timedelta

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from online_chat.models import (
    Department,
    BotConfiguration,
    Dialog,
    DialogMessage,
    OperatorProfile,
    RoutingRule,
    WidgetPlacement,
)
from online_chat.routing_services import (
    accept_waiting_dialog,
    auto_assign_dialog,
    select_department,
    update_operator_presence,
)
from online_chat.services import (
    append_message,
    create_dialog_with_message,
    set_client_presence,
)
from online_chat.tasks import classify_stale_dialogs


class RoutingTests(TestCase):
    def setUp(self) -> None:
        self.sales = Department.objects.create(code="sales", name="Sales", priority=20)
        self.support = Department.objects.create(code="support", name="Support", priority=10)
        self.placement = WidgetPlacement.objects.create(
            widget_id="site-main", name="Main", department=self.support
        )

    def operator(self, name: str, capacity: int = 2) -> OperatorProfile:
        item = OperatorProfile.objects.create(
            external_id=name.lower(),
            display_name=name,
            presence=OperatorProfile.Presence.ONLINE,
            max_active_dialogs=capacity,
        )
        item.departments.add(self.support)
        return item

    def test_rule_overrides_placement_department(self) -> None:
        RoutingRule.objects.create(
            name="VIP", priority=1, placement=self.placement,
            department=self.sales, conditions={"segment": "vip"}
        )
        department, _, reason = select_department(
            widget_id="site-main", context={"segment": "vip"}
        )
        self.assertEqual(department, self.sales)
        self.assertEqual(reason, "routing_rule:VIP")

    def test_least_active_operator_and_capacity(self) -> None:
        first = self.operator("First", capacity=1)
        second = self.operator("Second", capacity=2)
        Dialog.objects.create(
            status=Dialog.Status.ACTIVE, department=self.support,
            operator=second, operator_name=second.display_name
        )
        waiting = Dialog.objects.create(status=Dialog.Status.WAITING, department=self.support)
        assigned = auto_assign_dialog(waiting)
        self.assertEqual(assigned.operator, first)
        another = Dialog.objects.create(status=Dialog.Status.WAITING, department=self.support)
        self.assertEqual(auto_assign_dialog(another).operator, second)

    def test_presence_online_reruns_queue(self) -> None:
        operator = self.operator("Away")
        operator.presence = OperatorProfile.Presence.OFFLINE
        operator.save()
        dialog = Dialog.objects.create(status=Dialog.Status.WAITING, department=self.support)
        update_operator_presence(operator, OperatorProfile.Presence.ONLINE)
        dialog.refresh_from_db()
        self.assertEqual(dialog.operator, operator)

    def test_double_acceptance_is_rejected(self) -> None:
        first = self.operator("First")
        second = self.operator("Second")
        dialog = Dialog.objects.create(status=Dialog.Status.WAITING, department=self.support)
        accept_waiting_dialog(dialog.id, operator=first)
        with self.assertRaisesMessage(ValueError, "dialog is not waiting"):
            accept_waiting_dialog(dialog.id, operator=second)
        dialog.refresh_from_db()
        self.assertEqual(dialog.operator, first)


class ApiTests(TestCase):
    def setUp(self) -> None:
        self.department = Department.objects.create(code="support", name="Support")
        self.placement = WidgetPlacement.objects.create(
            widget_id="public-widget",
            name="Public",
            department=self.department,
            welcome_message="Hello",
            config={"language": "en"},
        )

    def test_public_placement_config(self) -> None:
        response = self.client.get(
            reverse("online_chat_widget_config", args=[self.placement.widget_id])
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["config"]["welcome_message"], "Hello")

    @override_settings(DEBUG=True)
    def test_supervisor_kpis(self) -> None:
        Dialog.objects.create(status=Dialog.Status.WAITING, department=self.department)
        Dialog.objects.create(status=Dialog.Status.ACTIVE, department=self.department)
        response = self.client.get(reverse("online_chat_supervisor"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["kpis"]["waiting"], 1)
        self.assertEqual(response.json()["kpis"]["active"], 1)

    @override_settings(DEBUG=True)
    def test_seed_returns_active_and_waiting_summary(self) -> None:
        response = self.client.post(
            reverse("online_chat_dev_seed"),
            data=json.dumps({
                "operators": 1, "clients": 5, "messages_per_dialog": 2,
                "auto_assign": True, "reset": True,
            }),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 201)
        summary = response.json()["summary"]
        self.assertEqual(summary["dialogs"], 5)
        self.assertEqual(summary["messages"], 10)
        self.assertEqual(summary["active"], 3)
        self.assertEqual(summary["waiting"], 2)

    @override_settings(DEBUG=False)
    def test_seed_is_hidden_outside_debug(self) -> None:
        response = self.client.post(
            reverse("online_chat_dev_seed"), data="{}", content_type="application/json"
        )
        self.assertEqual(response.status_code, 404)

    def test_create_dialog_uses_placement_and_routing(self) -> None:
        dialog, _ = create_dialog_with_message(text="Help", widget_id="public-widget")
        self.assertEqual(dialog.department, self.department)
        self.assertEqual(dialog.routing_reason, "placement:public-widget")

    @override_settings(DEBUG=True)
    def test_management_aliases_match_spa_contract(self) -> None:
        response = self.client.post(
            reverse("online_chat_operators"),
            data=json.dumps(
                {
                    "name": "Иванов И.И.",
                    "username": "ivanov",
                    "capacity": 4,
                    "department_id": str(self.department.id),
                    "presence": "online",
                }
            ),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 201)
        operator = response.json()["operator"]
        self.assertEqual(operator["name"], "Иванов И.И.")
        self.assertEqual(operator["username"], "ivanov")
        self.assertEqual(operator["capacity"], 4)
        self.assertEqual(operator["department_id"], str(self.department.id))

    def test_client_history_links_dialogs_by_phone(self) -> None:
        create_dialog_with_message(
            text="Первое обращение",
            widget_id="public-widget",
            client_phone="+375 29 111-22-33",
        )
        current, _ = create_dialog_with_message(
            text="Повторное обращение",
            widget_id="public-widget",
            client_phone="375291112233",
        )
        response = self.client.get(
            reverse("online_chat_client_history"),
            {"dialog_id": str(current.id)},
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["count"], 2)

    def test_offline_dialog_becomes_lost_after_timeout(self) -> None:
        dialog, _ = create_dialog_with_message(
            text="Нет ответа",
            widget_id="public-widget",
        )
        set_client_presence(dialog, online=False)
        Dialog.objects.filter(pk=dialog.pk).update(
            client_last_seen_at=timezone.now() - timedelta(minutes=20)
        )
        with override_settings(ONLINE_CHAT_LOST_TIMEOUT_SECONDS=60):
            result = classify_stale_dialogs()
        dialog.refresh_from_db()
        self.assertEqual(result["classified_lost"], 1)
        self.assertEqual(dialog.outcome, Dialog.Outcome.LOST)

    def test_attachment_upload_uses_object_store(self) -> None:
        dialog, _ = create_dialog_with_message(
            text="Отправлю документ",
            widget_id="public-widget",
        )
        with tempfile.TemporaryDirectory() as root:
            with override_settings(
                ONLINE_CHAT_OBJECT_STORE_BACKEND="fs",
                ONLINE_CHAT_OBJECT_STORE_ROOT=root,
                ONLINE_CHAT_MAX_UPLOAD_BYTES=1024,
                ONLINE_CHAT_ALLOWED_UPLOAD_TYPES=("text/plain",),
                DEBUG=True,
            ):
                response = self.client.post(
                    reverse("online_chat_dialog_attachment_upload", args=[dialog.id]),
                    {
                        "speaker": "client",
                        "file": SimpleUploadedFile(
                            "note.txt",
                            b"test attachment",
                            content_type="text/plain",
                        ),
                    },
                )
        self.assertEqual(response.status_code, 201)
        message = DialogMessage.objects.get(pk=response.json()["message"]["id"])
        self.assertEqual(message.attachment_name, "note.txt")
        self.assertEqual(message.attachment_scan_status, "clean")

    def test_first_line_bot_replies_then_hands_off(self) -> None:
        BotConfiguration.objects.create(
            name="FAQ",
            department=self.department,
            is_active=True,
            welcome_message="Я виртуальный помощник.",
            trigger_responses={"карт": "Какой вопрос по карте?"},
            max_bot_turns=3,
            handoff_message="Передаю оператору.",
        )
        dialog, _ = create_dialog_with_message(
            text="Здравствуйте",
            widget_id="public-widget",
        )
        self.assertTrue(
            dialog.bot_active,
            (dialog.bot_turns, list(dialog.messages.values_list("speaker", "text"))),
        )
        append_message(
            dialog,
            speaker=DialogMessage.Speaker.CLIENT,
            text="Вопрос по карте",
        )
        dialog.refresh_from_db()
        self.assertTrue(
            dialog.bot_active,
            (dialog.bot_turns, list(dialog.messages.values_list("speaker", "text"))),
        )
        self.assertTrue(
            dialog.messages.filter(
                speaker=DialogMessage.Speaker.BOT,
                text="Какой вопрос по карте?",
            ).exists()
        )
        append_message(
            dialog,
            speaker=DialogMessage.Speaker.CLIENT,
            text="Другой вопрос",
        )
        dialog.refresh_from_db()
        self.assertFalse(dialog.bot_active)
        self.assertTrue(
            dialog.messages.filter(
                speaker=DialogMessage.Speaker.BOT,
                text="Передаю оператору.",
            ).exists()
        )
