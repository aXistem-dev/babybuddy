# -*- coding: utf-8 -*-
import io

from django.core.management import call_command
from django.test import TestCase
from django.utils import timezone

from core import models


class LinkPumpingCommandTestCase(TestCase):
    def test_moves_child_pumping_to_parent(self):
        call_command("migrate", verbosity=0)
        child = models.Child.objects.create(
            first_name="Alex", birth_date=timezone.localdate()
        )
        robin = models.Parent.objects.create(first_name="Robin")
        start = timezone.localtime() - timezone.timedelta(hours=5)
        models.Pumping.objects.create(
            child=child,
            start=start,
            end=start + timezone.timedelta(minutes=10),
            amount=50,
        )
        call_command("link_pumping_to_parents", "--parent", "robin", "--dry-run")
        self.assertIsNone(models.Pumping.objects.get().parent)
        call_command("link_pumping_to_parents", "--parent", "robin")
        p = models.Pumping.objects.get()
        self.assertEqual((p.parent, p.child), (robin, None))
        self.assertIn(child, robin.children.all())

    def test_reports_moved_entries_that_overlap(self):
        call_command("migrate", verbosity=0)
        alex, sam = (
            models.Child.objects.create(
                first_name=name, birth_date=timezone.localdate()
            )
            for name in ("Alex", "Sam")
        )
        robin = models.Parent.objects.create(first_name="Robin")
        start = timezone.localtime() - timezone.timedelta(hours=5)
        end = start + timezone.timedelta(minutes=10)
        models.Pumping.objects.create(parent=robin, start=start, end=end, amount=60)
        models.Pumping.objects.create(child=alex, start=start, end=end, amount=60)
        later = end + timezone.timedelta(hours=1)
        models.Pumping.objects.create(
            child=sam,
            start=later,
            end=later + timezone.timedelta(minutes=10),
            amount=30,
        )
        out = io.StringIO()
        call_command("link_pumping_to_parents", "--parent", "robin", stdout=out)
        self.assertIn("Moved 2 pumping entries to Robin", out.getvalue())
        self.assertIn("1 of them overlaps", out.getvalue())
