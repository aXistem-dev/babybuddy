# Merges the milk stash and the activities migrations.

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0040_feeding_from_stash_pumping_to_stash"),
        ("core", "0043_alter_activity_type"),
    ]

    operations = []
