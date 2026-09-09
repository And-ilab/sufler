from django.db import migrations, models
import django.db.models.deletion
import uuid


class Migration(migrations.Migration):

    dependencies = [
        ("online_chat", "0027_sufler_feedback_source"),
    ]

    operations = [
        migrations.CreateModel(
            name="OperatorPresenceLog",
            fields=[
                (
                    "id",
                    models.UUIDField(
                        default=uuid.uuid4,
                        editable=False,
                        primary_key=True,
                        serialize=False,
                    ),
                ),
                ("presence", models.CharField(db_index=True, max_length=16)),
                ("started_at", models.DateTimeField(db_index=True)),
                ("ended_at", models.DateTimeField(blank=True, db_index=True, null=True)),
                (
                    "operator",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="presence_logs",
                        to="online_chat.operatorprofile",
                    ),
                ),
            ],
            options={
                "ordering": ("started_at",),
            },
        ),
        migrations.AddIndex(
            model_name="operatorpresencelog",
            index=models.Index(
                fields=["operator", "started_at"],
                name="oc_oppres_started_idx",
            ),
        ),
        migrations.AddIndex(
            model_name="operatorpresencelog",
            index=models.Index(
                fields=["operator", "ended_at"],
                name="oc_oppres_ended_idx",
            ),
        ),
    ]
