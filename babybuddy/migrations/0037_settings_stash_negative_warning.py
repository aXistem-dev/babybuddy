from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("babybuddy", "0036_settings_access_expires"),
    ]

    operations = [
        migrations.AddField(
            model_name="settings",
            name="stash_negative_warning",
            field=models.BooleanField(
                default=True,
                help_text="Shown on the milk stash page while more milk has left the stash than was logged going in.",
                verbose_name="Show the negative milk stash warning",
            ),
        ),
    ]
