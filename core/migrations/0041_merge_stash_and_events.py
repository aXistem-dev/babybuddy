# Merges the milk stash and the events migrations.

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0040_eventtype_event"),
        ("core", "0040_parent_pumping_milk_stash"),
    ]

    operations = []
