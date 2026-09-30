# -*- coding: utf-8 -*-
import datetime as dt

from django.test import TestCase
from django.utils import timezone

from core import models
from reports.graphs import event_types


class EventTypesTestCase(TestCase):
    def setUp(self):
        self.original_tz = timezone.get_current_timezone()
        self.tz = dt.timezone(dt.timedelta(days=-1, hours=1))
        timezone.activate(self.tz)

    def tearDown(self):
        timezone.activate(self.original_tz)

    def test_event_types(self):
        c = models.Child(birth_date=dt.datetime.now())
        c.save()
        bath = models.EventType.objects.create(name="Bath")
        nail_trim = models.EventType.objects.create(name="Nail trim")

        for event_type, day, hour in (
            (bath, 1, 18),
            (bath, 2, 18),
            (nail_trim, 2, 10),
            (bath, 4, 19),
        ):
            models.Event.objects.create(
                child=c,
                type=event_type,
                time=dt.datetime(2000, 1, day, hour, 0, tzinfo=dt.timezone.utc),
            )

        html, js = event_types(models.Event.objects.filter(child=c))
        self.assertIsNotNone(html)
        self.assertIsNotNone(js)
        self.assertIn("Bath", js)
        self.assertIn("Nail trim", js)

    def test_event_types_no_data(self):
        html, js = event_types(models.Event.objects.none())
        self.assertIsNone(html)
        self.assertIsNone(js)
