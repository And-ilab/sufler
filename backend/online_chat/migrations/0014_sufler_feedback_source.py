from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("online_chat", "0013_dialog_summaries"),
    ]

    operations = [
        migrations.AddField(
            model_name="suflerhintfeedback",
            name="source",
            field=models.CharField(
                blank=True,
                db_index=True,
                default="chat",
                max_length=32,
            ),
        ),
        migrations.AddField(
            model_name="suflerhintfeedback",
            name="call_id",
            field=models.CharField(blank=True, default="", max_length=64),
        ),
    ]
