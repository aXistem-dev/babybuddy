# -*- coding: utf-8 -*-
import datetime as dt

from django.test import TestCase
from django.utils import timezone

from core import models, stash
from reports.graphs import stash_balance, stash_flow, stash_use


class StashGraphsTestCase(TestCase):
    def test_graphs_render(self):
        robin = models.Parent.objects.create(first_name="Robin")
        t = timezone.now() - dt.timedelta(days=2)
        models.Pumping.objects.create(
            parent=robin,
            start=t,
            end=t + dt.timedelta(minutes=20),
            amount=100,
            stash_amount=100,
        )
        models.StashAdjustment.objects.create(
            time=t + dt.timedelta(hours=5),
            amount=30,
            kind="discarded",
            reason="Spilled",
        )
        events = stash.stash_events()
        for graph in (stash_balance, stash_flow):
            html, js = graph(events)
            self.assertIsNotNone(html)
            self.assertIsNotNone(js)

    def test_stash_use_graph_renders_one_series_per_baby(self):
        alex = models.Child.objects.create(
            first_name="Alex", birth_date=timezone.now().date()
        )
        sam = models.Child.objects.create(
            first_name="Sam", birth_date=timezone.now().date()
        )
        t = timezone.now() - dt.timedelta(hours=2)
        models.Feeding.objects.create(
            child=alex,
            start=t,
            end=t,
            type="breast milk",
            method="bottle",
            amount=50,
            stash_amount=50,
        )
        models.Feeding.objects.create(
            child=sam,
            start=t,
            end=t,
            type="breast milk",
            method="bottle",
            amount=30,
            stash_amount=30,
        )
        feedings = models.Feeding.objects.filter(
            stash_amount__isnull=False
        ).select_related("child")
        html, js = stash_use(feedings)
        self.assertIsNotNone(html)
        self.assertIsNotNone(js)
