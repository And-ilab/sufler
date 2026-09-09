from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("online_chat", "0028_operator_presence_log"),
    ]

    operations = [
        migrations.AddField(
            model_name="dialogmessage",
            name="source_base_message_id",
            field=models.UUIDField(blank=True, db_index=True, null=True),
        ),
    ]
