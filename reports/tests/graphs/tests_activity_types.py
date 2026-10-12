# -*- coding: utf-8 -*-
import datetime as dt
from unittest import mock

from django.test import TestCase
from django.utils import timezone
from django.utils.translation import get_language

import plotly.offline as plotly

from core import models
from reports.graphs import activity_types


class ActivityTypesTestCase(TestCase):
    def setUp(self):
        self.original_tz = timezone.get_current_timezone()
        self.tz = dt.timezone(dt.timedelta(days=-1, hours=1))
        timezone.activate(self.tz)

    def tearDown(self):
        timezone.activate(self.original_tz)

    def test_activity_types(self):
        c = models.Child(birth_date=dt.datetime.now())
        c.save()
        tooth_brushing = models.ActivityType.objects.create(name="Tooth brushing")
        nail_trim = models.ActivityType.objects.create(name="Nail trim")

        # The test time zone is UTC-23:00, so each of these falls on the day
        # before its UTC date.
        for activity_type, day, hour in (
            (tooth_brushing, 1, 18),
            (tooth_brushing, 2, 18),
            (tooth_brushing, 2, 20),
            (nail_trim, 2, 10),
            (tooth_brushing, 4, 19),
        ):
            models.Activity.objects.create(
                child=c,
                type=activity_type,
                start=dt.datetime(2000, 1, day, hour, 0, tzinfo=dt.timezone.utc),
            )

        with mock.patch("plotly.offline.plot", wraps=plotly.plot) as plot:
            html, js = activity_types(models.Activity.objects.filter(child=c))
        self.assertIsNotNone(html)
        self.assertIsNotNone(js)
        self.assertIn("Tooth brushing", js)
        self.assertIn("Nail trim", js)

        figure = plot.call_args.args[0]
        self.assertEqual(
            {trace.name: dict(zip(trace.x, trace.y)) for trace in figure.data},
            {
                "Tooth brushing": {
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

    def test_activity_types_no_data(self):
        html, js = activity_types(models.Activity.objects.none())
        self.assertIsNone(html)
        self.assertIsNone(js)
