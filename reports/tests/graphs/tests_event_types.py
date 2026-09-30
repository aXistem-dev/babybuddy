# -*- coding: utf-8 -*-
import datetime as dt
from unittest import mock

from django.test import TestCase
from django.utils import timezone
from django.utils.translation import get_language

import plotly.offline as plotly

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

        # The test time zone is UTC-23:00, so each of these falls on the day
        # before its UTC date.
        for event_type, day, hour in (
            (bath, 1, 18),
            (bath, 2, 18),
            (bath, 2, 20),
            (nail_trim, 2, 10),
            (bath, 4, 19),
        ):
            models.Event.objects.create(
                child=c,
                type=event_type,
                time=dt.datetime(2000, 1, day, hour, 0, tzinfo=dt.timezone.utc),
            )

        with mock.patch("plotly.offline.plot", wraps=plotly.plot) as plot:
            html, js = event_types(models.Event.objects.filter(child=c))
        self.assertIsNotNone(html)
        self.assertIsNotNone(js)
        self.assertIn("Bath", js)
        self.assertIn("Nail trim", js)

        figure = plot.call_args.args[0]
        self.assertEqual(
            {trace.name: dict(zip(trace.x, trace.y)) for trace in figure.data},
            {
                "Bath": {
                    dt.date(1999, 12, 31): 1,
                    dt.date(2000, 1, 1): 2,
                    dt.date(2000, 1, 3): 1,
                },
                "Nail trim": {dt.date(2000, 1, 1): 1},
            },
        )
        for trace in figure.data:
            self.assertIn("%{y}", trace.hovertemplate)
        self.assertEqual(plot.call_args.kwargs["config"], {"locale": get_language()})

    def test_event_types_no_data(self):
        html, js = event_types(models.Event.objects.none())
        self.assertIsNone(html)
        self.assertIsNone(js)
