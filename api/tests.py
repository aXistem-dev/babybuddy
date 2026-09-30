# -*- coding: utf-8 -*-
from unittest.mock import patch

from babybuddy.models import get_user_model
from api import serializers
from core import models, stash
from django.conf import settings
from django.contrib.auth.forms import PasswordResetForm
from django.contrib.auth.models import Group, Permission
from django.core.exceptions import PermissionDenied
from django.db import connection
from django.test.utils import CaptureQueriesContext
from django.urls import reverse
from django.utils import timezone
from rest_framework import serializers as drf_serializers
from rest_framework import status
from rest_framework.test import APIRequestFactory, APITestCase

from webhooks.models import WebhookEndpoint


class TestBase:
    class BabyBuddyAPITestCaseBase(APITestCase):
        fixtures = ["tests.json"]
        model = None
        endpoint = None
        delete_id = 1
        timer_test_data = {}

        def setUp(self):
            self.client.login(username="admin", password="admin")

        def test_options(self):
            response = self.client.options(self.endpoint)
            self.assertEqual(response.status_code, status.HTTP_200_OK)
            self.assertEqual(
                response.data["name"], "{} List".format(self.model._meta.verbose_name)
            )

        def test_delete(self):
            endpoint = "{}{}/".format(self.endpoint, self.delete_id)
            response = self.client.get(endpoint)
            self.assertEqual(response.status_code, status.HTTP_200_OK)
            response = self.client.delete(endpoint)
            self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)

        def test_post_with_timer(self):
            if not self.timer_test_data:
                return
            user = get_user_model().objects.first()
            start = timezone.now() - timezone.timedelta(minutes=10)
            timer = models.Timer.objects.create(user=user, start=start)
            self.timer_test_data["timer"] = timer.id

            if "child" in self.timer_test_data:
                del self.timer_test_data["child"]
            response = self.client.post(
                self.endpoint, self.timer_test_data, format="json"
            )
            self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
            timer.refresh_from_db()
            child = models.Child.objects.first()

            self.timer_test_data["child"] = child.id
            response = self.client.post(
                self.endpoint, self.timer_test_data, format="json"
            )
            self.assertEqual(response.status_code, status.HTTP_201_CREATED)
            obj = self.model.objects.get(pk=response.data["id"])
            self.assertEqual(obj.start, start)
            self.assertIsNotNone(obj.end)

        def test_post_with_timer_with_child(self):
            if not self.timer_test_data:
                return
            user = get_user_model().objects.first()
            child = models.Child.objects.first()
            start = timezone.now() - timezone.timedelta(minutes=10)
            timer = models.Timer.objects.create(user=user, child=child, start=start)
            self.timer_test_data["timer"] = timer.id
            response = self.client.post(
                self.endpoint, self.timer_test_data, format="json"
            )
            self.assertEqual(response.status_code, status.HTTP_201_CREATED)
            obj = self.model.objects.get(pk=response.data["id"])
            self.assertIsNotNone(obj.child)
            self.assertEqual(obj.start, start)
            self.assertIsNotNone(obj.end)


class BMIAPITestCase(TestBase.BabyBuddyAPITestCaseBase):
    endpoint = reverse("api:bmi-list")
    model = models.BMI

    def test_get(self):
        response = self.client.get(self.endpoint)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(
            response.data["results"][0],
            {
                "id": 2,
                "child": 1,
                "bmi": 26.5,
                "date": "2017-11-18",
                "notes": "before feed",
                "tags": [],
            },
        )

    def test_post(self):
        data = {
            "child": 1,
            "bmi": "27.0",
            "date": "2017-11-15",
        }
        response = self.client.post(self.endpoint, data, format="json")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        obj = self.model.objects.get(pk=response.data["id"])
        self.assertEqual(str(obj.bmi), data["bmi"])

    def test_post_null_date(self):
        data = {"child": 1, "bmi": "12.25"}
        response = self.client.post(self.endpoint, data, format="json")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        obj = self.model.objects.get(pk=response.data["id"])
        self.assertEqual(str(obj.bmi), data["bmi"])
        self.assertEqual(str(obj.date), timezone.localdate().strftime("%Y-%m-%d"))

    def test_patch(self):
        endpoint = "{}{}/".format(self.endpoint, 2)
        response = self.client.get(endpoint)
        entry = response.data
        entry["bmi"] = 30.0
        response = self.client.patch(endpoint, {"bmi": entry["bmi"]})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data, entry)


class ChildAPITestCase(TestBase.BabyBuddyAPITestCaseBase):
    endpoint = reverse("api:child-list")
    model = models.Child
    delete_id = "fake-child"

    def test_get(self):
        response = self.client.get(self.endpoint)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(
            response.data["results"][0],
            {
                "id": 1,
                "first_name": "Fake",
                "last_name": "Child",
                "birth_date": "2017-11-11",
                "birth_time": None,
                "due_date": None,
                "slug": "fake-child",
                "picture": None,
            },
        )

    def test_post(self):
        data = {
            "first_name": "Test",
            "last_name": "Child",
            "birth_date": "2017-11-12",
            "birth_time": "23:25",
        }
        response = self.client.post(self.endpoint, data, format="json")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        obj = models.Child.objects.get(pk=response.data["id"])
        self.assertEqual(obj.first_name, data["first_name"])

    def test_patch(self):
        endpoint = "{}{}/".format(self.endpoint, "fake-child")
        response = self.client.get(endpoint)
        entry = response.data
        entry["first_name"] = "New"
        entry["last_name"] = "Name"
        response = self.client.patch(
            endpoint,
            {
                "first_name": entry["first_name"],
                "last_name": entry["last_name"],
            },
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # The slug we be updated by the name change.
        entry["slug"] = "new-name"
        self.assertEqual(response.data, entry)


class PumpingAPITestCase(TestBase.BabyBuddyAPITestCaseBase):
    endpoint = reverse("api:pumping-list")
    model = models.Pumping
    timer_test_data = {"amount": 2}

    def setUp(self):
        super().setUp()
        self.parent = models.Parent.objects.create(first_name="Alex")
        self.parent.children.add(models.Child.objects.get(pk=1))

    def test_get(self):
        response = self.client.get(self.endpoint)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(
            response.data["results"][0],
            {
                "id": 2,
                "child": 1,
                "parent": None,
                "amount": 9.0,
                "stash_amount": None,
                "start": "2017-11-17T15:03:00-05:00",
                "end": "2017-11-17T15:22:00-05:00",
                "duration": "00:19:00",
                "notes": "new device",
                "tags": [],
            },
        )

    def test_post_with_timer(self):
        # Overridden: with a single milk-producing parent, a timer without a
        # child still gets that parent; with two, the parent must be sent.
        user = get_user_model().objects.first()
        start = timezone.now() - timezone.timedelta(minutes=10)
        timer = models.Timer.objects.create(user=user, start=start)
        response = self.client.post(
            self.endpoint, {"amount": 2, "timer": timer.id}, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.data)
        self.assertEqual(response.data["parent"], self.parent.id)

        models.Parent.objects.create(first_name="Casey")
        timer = models.Timer.objects.create(user=user, start=start)
        response = self.client.post(
            self.endpoint, {"amount": 2, "timer": timer.id}, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_parent_who_doesnt_produce_milk_is_refused(self):
        sam = models.Parent.objects.create(first_name="Sam", produces_milk=False)
        data = {
            "parent": sam.id,
            "amount": "21.0",
            "start": "2017-11-20T22:52:00-05:00",
            "end": "2017-11-20T23:05:00-05:00",
        }
        response = self.client.post(self.endpoint, data, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("parent", response.data)

    def test_post(self):
        data = {
            "child": 1,
            "amount": "21.0",
            "start": "2017-11-20T22:52:00-05:00",
            "end": "2017-11-20T23:05:00-05:00",
            "notes": "old device",
        }
        response = self.client.post(self.endpoint, data, format="json")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        obj = models.Pumping.objects.get(pk=response.data["id"])
        self.assertEqual(str(obj.amount), data["amount"])
        self.assertEqual(obj.notes, data["notes"])
        self.assertIsNone(obj.child)
        self.assertEqual(obj.parent, self.parent)

    def test_patch(self):
        endpoint = "{}{}/".format(self.endpoint, 1)
        response = self.client.get(endpoint)
        entry = response.data
        entry["amount"] = 41
        response = self.client.patch(
            endpoint,
            {
                "amount": entry["amount"],
            },
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data, entry)

    def test_patch_legacy_rows_of_different_children_at_the_same_time(self):
        start = timezone.now() - timezone.timedelta(hours=3)
        end = start + timezone.timedelta(minutes=15)
        rows = [
            models.Pumping.objects.create(
                child=models.Child.objects.create(
                    first_name=name, birth_date=timezone.localdate()
                ),
                start=start,
                end=end,
                amount=40,
            )
            for name in ("Casey", "Jamie")
        ]
        for row in rows:
            response = self.client.patch(
                "{}{}/".format(self.endpoint, row.id), {"notes": "checked"}
            )
            self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)

    def test_post_with_timer_with_child(self):
        # Overridden: a pumping session belongs to a parent, so the child
        # resolved from the timer ends up NULL, unlike other timer-backed
        # models where the base test expects a stored child.
        user = get_user_model().objects.first()
        child = models.Child.objects.first()
        start = timezone.now() - timezone.timedelta(minutes=10)
        timer = models.Timer.objects.create(user=user, child=child, start=start)
        self.timer_test_data["timer"] = timer.id
        response = self.client.post(self.endpoint, self.timer_test_data, format="json")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        obj = self.model.objects.get(pk=response.data["id"])
        self.assertIsNone(obj.child)
        self.assertEqual(obj.parent, self.parent)
        self.assertEqual(obj.start, start)
        self.assertIsNotNone(obj.end)

    def test_legacy_row_patch_without_parent_succeeds(self):
        # pk=1 is a fixture row that predates parent tracking (child set,
        # parent NULL). Editing an unrelated field must not force a parent.
        endpoint = "{}{}/".format(self.endpoint, 1)
        response = self.client.patch(endpoint, {"notes": "x"}, format="json")
        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)
        obj = models.Pumping.objects.get(pk=1)
        self.assertEqual(obj.notes, "x")
        self.assertIsNone(obj.parent)
        self.assertEqual(obj.child_id, 1)

    def test_update_ignores_child_sent_on_parent_owned_row(self):
        response = self.client.post(
            self.endpoint,
            {
                "parent": self.parent.id,
                "amount": 50,
                "start": "2017-11-21T08:00:00-05:00",
                "end": "2017-11-21T08:20:00-05:00",
            },
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.data)
        pk = response.data["id"]
        other_child = models.Child.objects.create(
            first_name="Other", last_name="Kid", birth_date="2018-01-01"
        )
        endpoint = "{}{}/".format(self.endpoint, pk)
        response = self.client.patch(endpoint, {"child": other_child.id}, format="json")
        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)
        self.assertIsNone(response.data["child"])
        obj = models.Pumping.objects.get(pk=pk)
        self.assertIsNone(obj.child)
        self.assertEqual(obj.parent_id, self.parent.id)

    def test_update_via_timer_does_not_resurrect_child_on_parent_owned_row(self):
        # CoreModelWithDurationSerializer.validate() sets attrs["child"] from
        # a supplied timer's child; a parent-owned row must still end up with
        # child=None even when it arrives this way rather than directly.
        response = self.client.post(
            self.endpoint,
            {
                "parent": self.parent.id,
                "amount": 50,
                "start": "2017-11-21T08:30:00-05:00",
                "end": "2017-11-21T08:50:00-05:00",
            },
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.data)
        pk = response.data["id"]
        other_child = models.Child.objects.create(
            first_name="Other", last_name="Kid", birth_date="2018-01-01"
        )
        timer = models.Timer.objects.create(
            user=get_user_model().objects.first(),
            child=other_child,
            start=timezone.now() - timezone.timedelta(minutes=5),
        )
        endpoint = "{}{}/".format(self.endpoint, pk)
        response = self.client.patch(
            endpoint, {"timer": timer.id, "amount": 55}, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)
        self.assertIsNone(response.data["child"])
        obj = models.Pumping.objects.get(pk=pk)
        self.assertIsNone(obj.child)
        self.assertEqual(obj.parent_id, self.parent.id)

    def test_amount_change_follows_full_stash(self):
        response = self.client.post(
            self.endpoint,
            {
                "parent": self.parent.id,
                "amount": 100,
                "start": "2017-11-21T09:00:00-05:00",
                "end": "2017-11-21T09:20:00-05:00",
            },
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.data)
        self.assertEqual(response.data["stash_amount"], 100.0)
        endpoint = "{}{}/".format(self.endpoint, response.data["id"])
        response = self.client.patch(endpoint, {"amount": 90}, format="json")
        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)
        self.assertEqual(response.data["stash_amount"], 90.0)

    def test_amount_change_leaves_partial_stash_that_still_fits(self):
        response = self.client.post(
            self.endpoint,
            {
                "parent": self.parent.id,
                "amount": 100,
                "stash_amount": 40,
                "start": "2017-11-21T10:00:00-05:00",
                "end": "2017-11-21T10:20:00-05:00",
            },
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.data)
        endpoint = "{}{}/".format(self.endpoint, response.data["id"])
        response = self.client.patch(endpoint, {"amount": 120}, format="json")
        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)
        self.assertEqual(response.data["stash_amount"], 40.0)

    def test_amount_change_clamps_partial_stash_that_would_exceed(self):
        response = self.client.post(
            self.endpoint,
            {
                "parent": self.parent.id,
                "amount": 100,
                "stash_amount": 40,
                "start": "2017-11-21T11:00:00-05:00",
                "end": "2017-11-21T11:20:00-05:00",
            },
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.data)
        endpoint = "{}{}/".format(self.endpoint, response.data["id"])
        response = self.client.patch(endpoint, {"amount": 30}, format="json")
        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)
        self.assertEqual(response.data["stash_amount"], 30.0)

    def test_filter_by_parent(self):
        other_parent = models.Parent.objects.create(first_name="Casey")
        mine = models.Pumping.objects.create(
            parent=self.parent, amount=10, start=timezone.now(), end=timezone.now()
        )
        theirs = models.Pumping.objects.create(
            parent=other_parent, amount=20, start=timezone.now(), end=timezone.now()
        )
        response = self.client.get(self.endpoint, {"parent": self.parent.id})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        ids = [row["id"] for row in response.data["results"]]
        self.assertIn(mine.id, ids)
        self.assertNotIn(theirs.id, ids)

    def test_filter_by_stash_amount_isnull(self):
        with_stash = models.Pumping.objects.create(
            parent=self.parent,
            amount=10,
            stash_amount=10,
            start=timezone.now(),
            end=timezone.now(),
        )
        without_stash = models.Pumping.objects.create(
            parent=self.parent, amount=10, start=timezone.now(), end=timezone.now()
        )
        response = self.client.get(self.endpoint, {"stash_amount__isnull": "false"})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        ids = [row["id"] for row in response.data["results"]]
        self.assertIn(with_stash.id, ids)
        self.assertNotIn(without_stash.id, ids)


class DiaperChangeAPITestCase(TestBase.BabyBuddyAPITestCaseBase):
    endpoint = reverse("api:diaperchange-list")
    model = models.DiaperChange
    delete_id = 3

    def test_get(self):
        response = self.client.get(self.endpoint)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(
            response.data["results"][0],
            {
                "id": 3,
                "child": 1,
                "time": "2017-11-18T14:00:00-05:00",
                "wet": True,
                "solid": False,
                "color": "",
                "amount": 2.25,
                "notes": "stinky",
                "tags": [],
            },
        )

    def test_post(self):
        data = {
            "child": 1,
            "time": "2017-11-18T12:00:00-05:00",
            "wet": True,
            "solid": True,
            "color": "brown",
            "amount": 1.25,
            "notes": "seedy",
        }
        response = self.client.post(self.endpoint, data, format="json")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        obj = models.DiaperChange.objects.get(pk=response.data["id"])
        self.assertTrue(obj.wet)
        self.assertTrue(obj.solid)
        self.assertEqual(obj.color, data["color"])
        self.assertEqual(obj.amount, data["amount"])
        self.assertEqual(obj.notes, data["notes"])

    def test_post_null_time(self):
        data = {
            "child": 1,
            "wet": False,
            "solid": True,
            "color": "black",
            "amount": 3,
            "notes": "noxious",
        }
        response = self.client.post(self.endpoint, data, format="json")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        obj = models.DiaperChange.objects.get(pk=response.data["id"])
        self.assertFalse(obj.wet)
        self.assertTrue(obj.solid)
        self.assertEqual(obj.color, data["color"])
        self.assertEqual(obj.amount, data["amount"])
        self.assertEqual(obj.notes, data["notes"])

    def test_patch(self):
        endpoint = "{}{}/".format(self.endpoint, 3)
        response = self.client.get(endpoint)
        entry = response.data
        entry["wet"] = False
        entry["solid"] = True
        response = self.client.patch(
            endpoint,
            {
                "wet": entry["wet"],
                "solid": entry["solid"],
            },
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data, entry)


class FeedingAPITestCase(TestBase.BabyBuddyAPITestCaseBase):
    endpoint = reverse("api:feeding-list")
    model = models.Feeding
    timer_test_data = {"type": "breast milk", "method": "left breast"}

    def test_get(self):
        response = self.client.get(self.endpoint)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(
            response.data["results"][0],
            {
                "id": 3,
                "child": 1,
                "parent": None,
                "start": "2017-11-18T09:00:00-05:00",
                "end": "2017-11-18T09:15:00-05:00",
                "duration": "00:15:00",
                "type": "formula",
                "method": "bottle",
                "amount": 2.5,
                "stash_amount": None,
                "stash_discarded": None,
                "stash_discard_reason": "",
                "notes": "forgot vitamins :(",
                "tags": [],
            },
        )

    # check backwards compatibility
    def test_get_with_date_filter(self):
        response = self.client.get(self.endpoint, {"start_min": "2017-11-18"})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 3)

    def test_get_with_iso_filter(self):
        response = self.client.get(
            self.endpoint, {"start_min": "2017-11-18T04:00:00-05:00"}
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 3)

    def test_post(self):
        data = {
            "child": 1,
            "start": "2017-11-19T14:00:00-05:00",
            "end": "2017-11-19T14:15:00-05:00",
            "type": "breast milk",
            "method": "left breast",
            "notes": "with vitamins",
        }
        response = self.client.post(self.endpoint, data, format="json")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        obj = models.Feeding.objects.get(pk=response.data["id"])
        self.assertEqual(obj.type, data["type"])
        self.assertEqual(obj.notes, data["notes"])

    def test_post_solid_food_from_the_breast_is_refused(self):
        data = {
            "child": 1,
            "start": "2017-11-19T14:00:00-05:00",
            "end": "2017-11-19T14:15:00-05:00",
            "type": "solid food",
            "method": "both breasts",
        }
        response = self.client.post(self.endpoint, data, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("method", response.data)

    def test_patch(self):
        endpoint = "{}{}/".format(self.endpoint, 3)
        response = self.client.get(endpoint)
        entry = response.data
        entry["type"] = "breast milk"
        entry["method"] = "left breast"
        entry["amount"] = 0
        response = self.client.patch(
            endpoint,
            {
                "type": entry["type"],
                "method": entry["method"],
                "amount": entry["amount"],
            },
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data, entry)


class StashAPITestCase(APITestCase):
    """Cross-cutting stash behaviour spanning pumping, feeding, adjustments
    and the /api/stash summary: not tied to a single endpoint, so this is
    based directly on APITestCase rather than the single-endpoint TestBase
    (whose generic options/delete/timer checks assume one)."""

    fixtures = ["tests.json"]

    def setUp(self):
        self.client.login(username="admin", password="admin")
        self.child = models.Child.objects.get(pk=1)
        self.robin = models.Parent.objects.create(first_name="Robin")
        self.robin.children.add(self.child)

    def post(self, name, data):
        return self.client.post(reverse(name), data, format="json")

    def pumping(self, hour, **kwargs):
        data = {
            "amount": 100,
            "start": "2017-11-18T%02d:00:00-05:00" % hour,
            "end": "2017-11-18T%02d:20:00-05:00" % hour,
        }
        data.update(kwargs)
        return self.post("api:pumping-list", data)

    def test_parent_pumping_defaults_to_stored(self):
        r = self.pumping(8, parent=self.robin.id)
        self.assertEqual(r.status_code, 201, r.data)
        self.assertEqual(
            (r.data["parent"], r.data["child"], r.data["stash_amount"]),
            (self.robin.id, None, 100.0),
        )

    def test_child_only_resolves_parent(self):
        r = self.pumping(9, child=self.child.id)
        self.assertEqual(r.status_code, 201, r.data)
        self.assertEqual((r.data["parent"], r.data["child"]), (self.robin.id, None))

    def test_child_with_two_parents_is_400(self):
        models.Parent.objects.create(first_name="Casey").children.add(self.child)
        self.assertEqual(self.pumping(10, child=self.child.id).status_code, 400)

    def test_timer_to_pumping_resolves_parent(self):
        timer = models.Timer.objects.create(
            user=get_user_model().objects.first(),
            child=self.child,
            start=timezone.now() - timezone.timedelta(minutes=15),
        )
        r = self.post("api:pumping-list", {"timer": timer.id, "amount": 80})
        self.assertEqual(r.status_code, 201, r.data)
        self.assertEqual(r.data["parent"], self.robin.id)

    def test_explicit_null_opts_out(self):
        r = self.pumping(11, parent=self.robin.id, stash_amount=None)
        self.assertIsNone(r.data["stash_amount"])

    def bottle(self, hour, **kwargs):
        data = {
            "child": 1,
            "type": "breast milk",
            "method": "bottle",
            "amount": 60,
            "start": "2017-11-19T%02d:00:00-05:00" % hour,
            "end": "2017-11-19T%02d:00:00-05:00" % hour,
        }
        data.update(kwargs)
        return self.post("api:feeding-list", data)

    def breastfeed(self, hour, **kwargs):
        data = {
            "child": self.child.id,
            "type": "breast milk",
            "method": "left breast",
            "start": "2017-11-19T%02d:00:00-05:00" % hour,
            "end": "2017-11-19T%02d:15:00-05:00" % hour,
        }
        data.update(kwargs)
        return self.post("api:feeding-list", data)

    def test_api_breastfeed_resolves_parent(self):
        r = self.breastfeed(6)
        self.assertEqual(r.status_code, 201, r.data)
        self.assertEqual(r.data["parent"], self.robin.id)

    def test_api_breastfeed_explicit_null_opts_out(self):
        # Unlike an omitted `parent`, an explicit `"parent": null` is a
        # deliberate choice and must not be auto-filled, same as
        # `stash_amount` in StashDefaultsMixin.
        r = self.breastfeed(20, parent=None)
        self.assertEqual(r.status_code, 201, r.data)
        self.assertIsNone(r.data["parent"])

    def test_api_breastfeed_child_with_two_parents_is_not_an_error(self):
        models.Parent.objects.create(first_name="Casey").children.add(self.child)
        r = self.breastfeed(21)
        self.assertEqual(r.status_code, 201, r.data)
        self.assertIsNone(r.data["parent"])

    def test_timer_to_breastfeed_resolves_parent(self):
        timer = models.Timer.objects.create(
            user=get_user_model().objects.first(),
            child=self.child,
            start=timezone.now() - timezone.timedelta(minutes=10),
        )
        r = self.post(
            "api:feeding-list",
            {"timer": timer.id, "type": "breast milk", "method": "left breast"},
        )
        self.assertEqual(r.status_code, 201, r.data)
        self.assertEqual(r.data["parent"], self.robin.id)

    def test_api_parent_rejected_for_bottle(self):
        r = self.bottle(7, parent=self.robin.id)
        self.assertEqual(r.status_code, 201, r.data)
        self.assertIsNone(r.data["parent"])
        obj = models.Feeding.objects.get(pk=r.data["id"])
        self.assertIsNone(obj.parent)

    def test_feeding_create_default_skipped_without_activity(self):
        self.assertIsNone(self.bottle(8).data["stash_amount"])

    def test_feeding_create_default_applies(self):
        models.StashAdjustment.objects.create(
            time=timezone.now() - timezone.timedelta(days=1),
            amount=200,
            kind="added",
        )
        self.assertEqual(self.bottle(9).data["stash_amount"], 60.0)
        self.assertIsNone(self.bottle(10, type="formula").data["stash_amount"])

    def test_feeding_discard_reason_free_text(self):
        r = self.bottle(
            11, stash_amount=60, stash_discarded=10, stash_discard_reason="Spilled"
        )
        self.assertEqual(r.status_code, 201, r.data)
        self.assertEqual(
            (r.data["stash_discarded"], r.data["stash_discard_reason"]),
            (10.0, "Spilled"),
        )
        f = models.Feeding.objects.get(pk=r.data["id"])
        self.assertEqual(f.linked_discard().reason, "Spilled")
        r = self.client.get(reverse("api:feeding-detail", args=[f.id]))
        self.assertEqual(r.data["stash_discard_reason"], "Spilled")
        r = self.client.patch(
            reverse("api:feeding-detail", args=[f.id]),
            {"stash_discard_reason": "Baby fell asleep"},
            format="json",
        )
        self.assertEqual(r.status_code, 200, r.data)
        self.assertEqual(r.data["stash_discard_reason"], "Baby fell asleep")
        self.assertEqual(f.linked_discard().reason, "Baby fell asleep")
        r = self.client.patch(
            reverse("api:feeding-detail", args=[f.id]),
            {"stash_discard_reason": "x" * 256},
            format="json",
        )
        self.assertEqual(r.status_code, 400)
        self.assertIn("stash_discard_reason", r.data)

    def test_discard_reason_round_trip(self):
        r = self.bottle(
            11, stash_amount=60, stash_discarded=10, stash_discard_reason="Spilled"
        )
        self.assertEqual(r.status_code, 201, r.data)
        self.assertEqual(
            (r.data["stash_discarded"], r.data["stash_discard_reason"]),
            (10.0, "Spilled"),
        )
        f = models.Feeding.objects.get(pk=r.data["id"])
        self.assertEqual(f.stash_adjustments.count(), 1)
        r = self.client.patch(
            reverse("api:feeding-detail", args=[f.id]),
            {"stash_discarded": None},
            format="json",
        )
        self.assertIsNone(r.data["stash_discarded"])
        self.assertEqual(f.stash_adjustments.count(), 0)

    def test_discard_without_stash_is_400(self):
        response = self.bottle(12, stash_amount=None, stash_discarded=10)
        self.assertEqual(response.status_code, 400)
        self.assertIn("stash_discarded", response.data)

    def test_discard_reason_only_without_existing_discard_is_400(self):
        r = self.bottle(15, stash_amount=60)
        self.assertEqual(r.status_code, 201, r.data)
        f = models.Feeding.objects.get(pk=r.data["id"])
        response = self.client.patch(
            reverse("api:feeding-detail", args=[f.id]),
            {"stash_discard_reason": "Spilled"},
            format="json",
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("stash_discard_reason", response.data)
        self.assertFalse(f.stash_adjustments.exists())

    def test_discard_reason_only_with_existing_discard_updates_it(self):
        r = self.bottle(
            16, stash_amount=60, stash_discarded=10, stash_discard_reason="Spilled"
        )
        self.assertEqual(r.status_code, 201, r.data)
        f = models.Feeding.objects.get(pk=r.data["id"])
        response = self.client.patch(
            reverse("api:feeding-detail", args=[f.id]),
            {"stash_discard_reason": "Left over"},
            format="json",
        )
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(response.data["stash_discard_reason"], "Left over")
        self.assertEqual(response.data["stash_discarded"], 10.0)
        discard = f.linked_discard()
        self.assertEqual((discard.amount, discard.reason), (10.0, "Left over"))

    def test_discard_reason_with_stash_cleared_removes_discard(self):
        for hour, change in (
            (17, {"method": "left breast"}),
            (18, {"stash_amount": None}),
        ):
            with self.subTest(change=change):
                r = self.bottle(
                    hour,
                    stash_amount=60,
                    stash_discarded=10,
                    stash_discard_reason="Spilled",
                )
                self.assertEqual(r.status_code, 201, r.data)
                f = models.Feeding.objects.get(pk=r.data["id"])
                response = self.client.patch(
                    reverse("api:feeding-detail", args=[f.id]),
                    {**change, "stash_discard_reason": "Other"},
                    format="json",
                )
                self.assertEqual(response.status_code, 200, response.data)
                self.assertIsNone(response.data["stash_amount"])
                self.assertIsNone(response.data["stash_discarded"])
                self.assertFalse(f.stash_adjustments.exists())

    def test_start_change_moves_linked_discard(self):
        r = self.bottle(19, stash_amount=60, stash_discarded=10)
        self.assertEqual(r.status_code, 201, r.data)
        f = models.Feeding.objects.get(pk=r.data["id"])
        response = self.client.patch(
            reverse("api:feeding-detail", args=[f.id]),
            {"start": "2017-11-19T18:40:00-05:00"},
            format="json",
        )
        self.assertEqual(response.status_code, 200, response.data)
        f.refresh_from_db()
        self.assertEqual(f.linked_discard().time, f.start)

    def test_parent_fed_and_self_fed_can_come_from_the_stash(self):
        for hour, method in ((20, "parent fed"), (21, "self fed")):
            with self.subTest(method=method):
                r = self.bottle(hour, method=method, stash_amount=60, stash_discarded=5)
                self.assertEqual(r.status_code, 201, r.data)
                self.assertEqual(
                    (r.data["stash_amount"], r.data["stash_discarded"]), (60.0, 5.0)
                )

    def test_bottle_amount_change_follows_full_stash(self):
        r = self.bottle(13, stash_amount=60)
        self.assertEqual(r.status_code, 201, r.data)
        endpoint = reverse("api:feeding-detail", args=[r.data["id"]])
        r = self.client.patch(endpoint, {"amount": 50}, format="json")
        self.assertEqual(r.status_code, 200, r.data)
        self.assertEqual(r.data["stash_amount"], 50.0)

    def test_bottle_type_change_wipes_stash_and_linked_rows(self):
        r = self.bottle(14, stash_amount=60, stash_discarded=10)
        self.assertEqual(r.status_code, 201, r.data)
        f = models.Feeding.objects.get(pk=r.data["id"])
        self.assertEqual(f.stash_adjustments.count(), 1)
        endpoint = reverse("api:feeding-detail", args=[f.id])
        r = self.client.patch(endpoint, {"type": "formula"}, format="json")
        self.assertEqual(r.status_code, 200, r.data)
        self.assertIsNone(r.data["stash_amount"])
        self.assertEqual(models.StashAdjustment.objects.filter(feeding=f).count(), 0)

    def test_feeding_list_stash_fields_do_not_scale_with_row_count(self):
        # stash_discarded/stash_discard_reason read stash_adjustments for
        # every row; this counts only the queries touching that table, so it
        # stays focused on the prefetch fix regardless of unrelated per-row
        # queries (e.g. tags) the list view may also issue.
        def make_bottle(hour):
            r = self.bottle(hour, stash_amount=10, stash_discarded=2)
            self.assertEqual(r.status_code, 201, r.data)

        def stash_adjustment_query_count():
            with CaptureQueriesContext(connection) as ctx:
                response = self.client.get(reverse("api:feeding-list"))
            self.assertEqual(response.status_code, 200)
            return sum(
                1 for q in ctx.captured_queries if "core_stashadjustment" in q["sql"]
            )

        make_bottle(15)
        one_row_count = stash_adjustment_query_count()

        make_bottle(16)
        make_bottle(17)
        make_bottle(18)
        four_row_count = stash_adjustment_query_count()

        self.assertEqual(one_row_count, 1)
        self.assertEqual(one_row_count, four_row_count)

    def test_adjustments_and_summary(self):
        r = self.post(
            "api:stashadjustment-list",
            {
                "time": "2017-11-18T07:00:00-05:00",
                "amount": 300,
                "kind": "added",
                "parent": self.robin.id,
            },
        )
        self.assertEqual(r.status_code, 201, r.data)
        summary = self.client.get("/api/stash").data
        for key in (
            "balance",
            "status",
            "warn_age_hours",
            "max_age_hours",
            "lots",
            "defaults",
        ):
            self.assertIn(key, summary)

    def test_parents_endpoint(self):
        r = self.client.get(reverse("api:parent-list"))
        self.assertEqual(r.data["results"][0]["children"], [1])

    def test_api_root_advertises_stash(self):
        root = self.client.get("/api/").data
        for key in ("parents", "stash-adjustments", "stash"):
            self.assertIn(key, root)

    def test_stash_defaults_values(self):
        summary = self.client.get("/api/stash").data
        self.assertEqual(
            summary["defaults"],
            {"pumping_to_stash": True, "bottle_from_stash": True},
        )
        self.assertEqual(
            (summary["warn_age_hours"], summary["max_age_hours"]), (48, 72)
        )


class ParentAPITestCase(TestBase.BabyBuddyAPITestCaseBase):
    endpoint = reverse("api:parent-list")
    model = models.Parent

    def setUp(self):
        super().setUp()
        self.parent = models.Parent.objects.create(first_name="Alex", last_name="Doe")
        self.parent.children.add(models.Child.objects.get(pk=1))
        self.delete_id = self.parent.slug

    def test_get(self):
        response = self.client.get(self.endpoint)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(
            response.data["results"][0],
            {
                "id": self.parent.id,
                "first_name": "Alex",
                "last_name": "Doe",
                "slug": self.parent.slug,
                "picture": None,
                "produces_milk": True,
                "children": [1],
            },
        )

    def test_post(self):
        data = {"first_name": "Sam", "last_name": "Doe", "children": [1]}
        response = self.client.post(self.endpoint, data, format="json")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        obj = models.Parent.objects.get(pk=response.data["id"])
        self.assertEqual(obj.first_name, data["first_name"])
        self.assertEqual(list(obj.children.values_list("id", flat=True)), [1])

    def test_patch(self):
        endpoint = "{}{}/".format(self.endpoint, self.parent.slug)
        response = self.client.patch(endpoint, {"last_name": "Smith"}, format="json")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["last_name"], "Smith")

    def test_delete_parent_with_entries_is_refused(self):
        start = timezone.now() - timezone.timedelta(hours=2)
        models.Pumping.objects.create(
            parent=self.parent,
            start=start,
            end=start + timezone.timedelta(minutes=10),
            amount=50,
        )
        endpoint = "{}{}/".format(self.endpoint, self.parent.slug)
        response = self.client.delete(endpoint)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(
            response.data["detail"],
            "Alex Doe still has pumping or stash entries; move or delete them first.",
        )
        self.assertTrue(models.Parent.objects.filter(pk=self.parent.pk).exists())

    def test_delete_parent_with_breastfeeding_succeeds(self):
        # Feeding.parent is SET_NULL: unlike pumping and stash entries, a
        # breastfeeding history must not block deleting the parent.
        start = timezone.now() - timezone.timedelta(hours=1)
        feeding = models.Feeding.objects.create(
            child=models.Child.objects.get(pk=1),
            parent=self.parent,
            start=start,
            end=start + timezone.timedelta(minutes=10),
            type="breast milk",
            method="left breast",
        )
        endpoint = "{}{}/".format(self.endpoint, self.parent.slug)
        response = self.client.delete(endpoint)
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(models.Parent.objects.filter(pk=self.parent.pk).exists())
        feeding.refresh_from_db()
        self.assertIsNone(feeding.parent)


class StashSettingsAPITestCase(APITestCase):
    fixtures = ["tests.json"]
    endpoint = reverse("api:stash-settings")

    def test_admin_reads_and_changes_the_settings(self):
        self.client.login(username="admin", password="admin")
        response = self.client.get(self.endpoint)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(
            response.data,
            {
                "pumping_to_stash": True,
                "bottle_from_stash": True,
                "warn_age_hours": 48,
                "max_age_hours": 72,
                "can_edit": True,
            },
        )
        response = self.client.patch(
            self.endpoint,
            {"bottle_from_stash": False, "warn_age_hours": 24},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)
        self.assertFalse(response.data["bottle_from_stash"])
        self.assertEqual(response.data["warn_age_hours"], 24)
        self.assertFalse(stash.settings().bottle_from_stash_default)
        self.assertEqual(stash.stash_summary()["warn_age_hours"], 24)

    def test_warn_age_must_be_below_the_throw_away_age(self):
        self.client.login(username="admin", password="admin")
        response = self.client.patch(
            self.endpoint, {"warn_age_hours": 72}, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("warn_age_hours", response.data)

    def test_other_users_can_read_but_not_change(self):
        user = get_user_model().objects.create_user(username="viewer", password="pw")
        user.user_permissions.add(
            *Permission.objects.filter(
                content_type__app_label="core",
                codename__in=["view_pumping", "change_pumping"],
            )
        )
        self.client.login(username="viewer", password="pw")
        response = self.client.get(self.endpoint)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertFalse(response.data["can_edit"])
        response = self.client.patch(
            self.endpoint, {"pumping_to_stash": False}, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertTrue(stash.settings().pumping_to_stash_default)


class StashAdjustmentAPITestCase(TestBase.BabyBuddyAPITestCaseBase):
    endpoint = reverse("api:stashadjustment-list")
    model = models.StashAdjustment

    def setUp(self):
        super().setUp()
        self.adjustment = models.StashAdjustment.objects.create(
            time="2017-11-18T07:00:00-05:00", amount=200, kind="added"
        )
        self.delete_id = self.adjustment.pk

    def test_get(self):
        response = self.client.get(self.endpoint)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(
            response.data["results"][0],
            {
                "id": self.adjustment.id,
                "time": "2017-11-18T07:00:00-05:00",
                "amount": 200.0,
                "kind": "added",
                "reason": "",
                "signed_amount": 200.0,
                "parent": None,
                "feeding": None,
                "notes": None,
                "tags": [],
            },
        )

    def test_post(self):
        data = {
            "time": "2017-11-19T08:00:00-05:00",
            "amount": 50,
            "kind": "discarded",
            "reason": "Older than 72 h",
        }
        response = self.client.post(self.endpoint, data, format="json")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        obj = models.StashAdjustment.objects.get(pk=response.data["id"])
        self.assertEqual(obj.kind, "discarded")
        self.assertEqual(obj.reason, "Older than 72 h")
        self.assertEqual(obj.signed_amount, -50.0)

    def test_patch(self):
        endpoint = "{}{}/".format(self.endpoint, self.adjustment.pk)
        response = self.client.patch(endpoint, {"amount": 250}, format="json")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["amount"], 250.0)

    def test_signed_amount_is_a_float_field(self):
        # A plain ReadOnlyField would type this as a string in the generated
        # schema, even though the value is always numeric.
        field = serializers.StashAdjustmentSerializer().fields["signed_amount"]
        self.assertIsInstance(field, drf_serializers.FloatField)

    def test_reason_free_text_both_kinds(self):
        for kind, reason in (("added", "Donor milk"), ("discarded", "Spilled")):
            with self.subTest(kind=kind):
                response = self.client.post(
                    self.endpoint,
                    {
                        "time": "2017-11-19T08:00:00-05:00",
                        "amount": 50,
                        "kind": kind,
                        "reason": reason,
                    },
                    format="json",
                )
                self.assertEqual(response.status_code, 201, response.data)
                self.assertEqual(response.data["reason"], reason)
        response = self.client.post(
            self.endpoint,
            {
                "time": "2017-11-19T08:00:00-05:00",
                "amount": 50,
                "kind": "added",
                "reason": "x" * 256,
            },
            format="json",
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("reason", response.data)

    def test_filter_adjustments_by_kind(self):
        models.StashAdjustment.objects.create(
            time="2017-11-19T08:00:00-05:00",
            amount=10,
            kind="discarded",
            reason="Spilled",
        )
        models.StashAdjustment.objects.create(
            time="2017-11-19T09:00:00-05:00",
            amount=15,
            kind="discarded",
            reason="Left over",
        )
        response = self.client.get(self.endpoint, {"kind": "discarded"})
        self.assertEqual(response.data["count"], 2)
        response = self.client.get(self.endpoint, {"kind": "added"})
        self.assertEqual(response.data["count"], 1)

    def test_api_adjustment_parent_auto_fill(self):
        data = {
            "time": "2017-11-19T08:00:00-05:00",
            "amount": 50,
            "kind": "added",
        }
        robin = models.Parent.objects.create(first_name="Robin")

        response = self.client.post(self.endpoint, data, format="json")
        self.assertEqual(response.status_code, 201, response.data)
        self.assertEqual(response.data["parent"], robin.id)

        response = self.client.post(
            self.endpoint, {**data, "parent": None}, format="json"
        )
        self.assertEqual(response.status_code, 201, response.data)
        self.assertIsNone(response.data["parent"])

        # An update never fills in a parent.
        endpoint = "{}{}/".format(self.endpoint, response.data["id"])
        response = self.client.patch(endpoint, {"amount": 60}, format="json")
        self.assertEqual(response.status_code, 200, response.data)
        self.assertIsNone(response.data["parent"])

        models.Parent.objects.create(first_name="Casey")
        response = self.client.post(self.endpoint, data, format="json")
        self.assertEqual(response.status_code, 201, response.data)
        self.assertIsNone(response.data["parent"])


class HeadCircumferenceAPITestCase(TestBase.BabyBuddyAPITestCaseBase):
    endpoint = reverse("api:headcircumference-list")
    model = models.HeadCircumference

    def test_get(self):
        response = self.client.get(self.endpoint)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(
            response.data["results"][0],
            {
                "id": 2,
                "child": 1,
                "head_circumference": 6.5,
                "date": "2017-11-18",
                "notes": "before feed",
                "tags": [],
            },
        )

    def test_post(self):
        data = {
            "child": 1,
            "head_circumference": "9.5",
            "date": "2017-11-15",
        }
        response = self.client.post(self.endpoint, data, format="json")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        obj = self.model.objects.get(pk=response.data["id"])
        self.assertEqual(str(obj.head_circumference), data["head_circumference"])

    def test_post_null_date(self):
        data = {"child": 1, "head_circumference": "10.0"}
        response = self.client.post(self.endpoint, data, format="json")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        obj = self.model.objects.get(pk=response.data["id"])
        self.assertEqual(str(obj.head_circumference), data["head_circumference"])
        self.assertEqual(str(obj.date), timezone.localdate().strftime("%Y-%m-%d"))

    def test_patch(self):
        endpoint = "{}{}/".format(self.endpoint, 2)
        response = self.client.get(endpoint)
        entry = response.data
        entry["head_circumference"] = 23
        response = self.client.patch(
            endpoint, {"head_circumference": entry["head_circumference"]}
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data, entry)


class HeightAPITestCase(TestBase.BabyBuddyAPITestCaseBase):
    endpoint = reverse("api:height-list")
    model = models.Height

    def test_get(self):
        response = self.client.get(self.endpoint)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(
            response.data["results"][0],
            {
                "id": 2,
                "child": 1,
                "height": 10.5,
                "date": "2017-11-18",
                "notes": "before feed",
                "tags": [],
            },
        )

    def test_post(self):
        data = {
            "child": 1,
            "height": "12.5",
            "date": "2017-11-15",
        }
        response = self.client.post(self.endpoint, data, format="json")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        obj = self.model.objects.get(pk=response.data["id"])
        self.assertEqual(str(obj.height), data["height"])

    def test_post_null_date(self):
        data = {"child": 1, "height": "19.0"}
        response = self.client.post(self.endpoint, data, format="json")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        obj = self.model.objects.get(pk=response.data["id"])
        self.assertEqual(str(obj.height), data["height"])
        self.assertEqual(str(obj.date), timezone.localdate().strftime("%Y-%m-%d"))

    def test_patch(self):
        endpoint = "{}{}/".format(self.endpoint, 2)
        response = self.client.get(endpoint)
        entry = response.data
        entry["height"] = 23.5
        response = self.client.patch(endpoint, {"height": entry["height"]})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data, entry)


class MedicationAPITestCase(TestBase.BabyBuddyAPITestCaseBase):
    endpoint = reverse("api:medication-list")
    model = models.Medication

    def test_delete(self):
        # Create a medication entry first, then delete it
        data = {
            "child": 1,
            "name": "Test Medication for Delete",
            "dosage": "5.0",
            "dosage_unit": "ml",
            "time": "2017-11-18T12:00:00-05:00",
        }
        response = self.client.post(self.endpoint, data, format="json")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        delete_id = response.data["id"]

        # Test the delete functionality
        endpoint = f"{self.endpoint}{delete_id}/"
        response = self.client.get(endpoint)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        response = self.client.delete(endpoint)
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)

    def test_get(self):
        response = self.client.get(self.endpoint)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # Test basic structure - we'll need fixture data for specific content

    def test_post(self):
        data = {
            "child": 1,
            "name": "Tylenol",
            "dosage": "5.0",
            "dosage_unit": "ml",
            "time": "2017-11-18T12:00:00-05:00",
            "next_dose_interval": "04:00:00",
            "notes": "For fever",
        }
        response = self.client.post(self.endpoint, data, format="json")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        obj = self.model.objects.get(pk=response.data["id"])
        self.assertEqual(obj.name, data["name"])
        self.assertEqual(str(obj.dosage), data["dosage"])
        self.assertEqual(obj.dosage_unit, data["dosage_unit"])
        self.assertEqual(obj.notes, data["notes"])
        self.assertEqual(obj.next_dose_interval.total_seconds(), 4 * 3600)

    def test_post_null_time(self):
        data = {
            "child": 1,
            "name": "Vitamin D",
            "dosage": "1",
            "dosage_unit": "drops",
        }
        response = self.client.post(self.endpoint, data, format="json")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        obj = self.model.objects.get(pk=response.data["id"])
        self.assertEqual(obj.name, data["name"])

    def test_patch(self):
        # First create a medication entry to patch
        data = {
            "child": 1,
            "name": "Test Medication",
            "dosage": "2.5",
            "dosage_unit": "ml",
            "time": "2017-11-18T12:00:00-05:00",
        }
        response = self.client.post(self.endpoint, data, format="json")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        # Now patch it
        endpoint = "{}{}/".format(self.endpoint, response.data["id"])
        patch_data = {"dosage": "5.0", "notes": "Updated dosage"}
        response = self.client.patch(endpoint, patch_data, format="json")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(str(response.data["dosage"]), patch_data["dosage"])
        self.assertEqual(response.data["notes"], patch_data["notes"])


class NoteAPITestCase(TestBase.BabyBuddyAPITestCaseBase):
    endpoint = reverse("api:note-list")
    model = models.Note

    def test_get(self):
        response = self.client.get(self.endpoint)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertDictEqual(
            response.data["results"][0],
            {
                "id": 1,
                "child": 1,
                "note": "Fake note.",
                "image": None,
                "time": "2017-11-17T22:45:00-05:00",
                "tags": [],
            },
        )

    def test_post(self):
        data = {
            "child": 1,
            "note": "New fake note.",
            "time": "2017-11-18T22:45:00-05:00",
        }
        response = self.client.post(self.endpoint, data, format="json")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        obj = models.Note.objects.get(pk=response.data["id"])
        self.assertEqual(obj.note, data["note"])

    def test_post_null_time(self):
        data = {
            "child": 1,
            "note": "Another fake note.",
        }
        response = self.client.post(self.endpoint, data, format="json")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        obj = models.Note.objects.get(pk=response.data["id"])
        self.assertEqual(obj.note, data["note"])

    def test_patch(self):
        endpoint = "{}{}/".format(self.endpoint, 1)
        response = self.client.get(endpoint)
        entry = response.data
        entry["note"] = "Updated note text."
        response = self.client.patch(
            endpoint,
            {
                "note": entry["note"],
            },
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # The time of entry will always update automatically, so only check the
        # new value.
        self.assertEqual(response.data["note"], entry["note"])


class SleepAPITestCase(TestBase.BabyBuddyAPITestCaseBase):
    endpoint = reverse("api:sleep-list")
    model = models.Sleep
    timer_test_data = {"child": 1}

    def test_get(self):
        response = self.client.get(self.endpoint)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertDictEqual(
            response.data["results"][0],
            {
                "id": 4,
                "child": 1,
                "start": "2017-11-19T03:00:00-05:00",
                "end": "2017-11-19T04:30:00-05:00",
                "duration": "01:30:00",
                "nap": True,
                "notes": "lots of squirming",
                "tags": [],
            },
        )

    def test_post(self):
        data = {
            "child": 1,
            "start": "2017-11-21T19:30:00-05:00",
            "end": "2017-11-21T23:00:00-05:00",
            "notes": "used new swaddle",
        }
        response = self.client.post(self.endpoint, data, format="json")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        obj = models.Sleep.objects.get(pk=response.data["id"])
        self.assertEqual(str(obj.duration), "3:30:00")
        self.assertEqual(obj.notes, data["notes"])

    def test_patch(self):
        endpoint = "{}{}/".format(self.endpoint, 4)
        response = self.client.get(endpoint)
        entry = response.data
        entry["end"] = "2017-11-19T08:30:00-05:00"
        response = self.client.patch(
            endpoint,
            {
                "end": entry["end"],
            },
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # The duration of entry will always update automatically, so only check
        # the new value.
        self.assertEqual(response.data["end"], entry["end"])


class TagsAPITestCase(TestBase.BabyBuddyAPITestCaseBase):
    endpoint = reverse("api:tag-list")
    model = models.Tag

    def test_get(self):
        response = self.client.get(self.endpoint)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertDictEqual(
            dict(response.data["results"][0]),
            {
                "name": "a name",
                "slug": "a-name",
                "color": "#FF0000",
                "last_used": "2017-11-18T11:00:00-05:00",
            },
        )

    def test_post(self):
        data = {"name": "new tag", "color": "#123456"}
        response = self.client.post(self.endpoint, data, format="json")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        response = self.client.get(self.endpoint)
        results = response.json()["results"]
        results_by_name = {r["name"]: r for r in results}

        tag_data = results_by_name["new tag"]
        self.assertEqual(tag_data, tag_data | data)
        self.assertEqual(tag_data["slug"], "new-tag")
        self.assertTrue(tag_data["last_used"])

    def test_patch(self):
        endpoint = f"{self.endpoint}a-name/"

        modified_data = {
            "name": "A different name",
            "color": "#567890",
        }
        response = self.client.patch(
            endpoint,
            modified_data,
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data, response.data | modified_data)

    def test_delete(self):
        endpoint = f"{self.endpoint}a-name/"
        response = self.client.delete(endpoint)
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        response = self.client.delete(endpoint)
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_post_tags_to_model(self):
        data = {"child": 1, "note": "New tagged note.", "tags": ["tag1", "tag2"]}
        response = self.client.post(reverse("api:note-list"), data, format="json")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertCountEqual(response.data["tags"], data["tags"])
        note = models.Note.objects.get(pk=response.data["id"])
        self.assertCountEqual(list(note.tags.names()), data["tags"])


class TemperatureAPITestCase(TestBase.BabyBuddyAPITestCaseBase):
    endpoint = reverse("api:temperature-list")
    model = models.Temperature

    def test_get(self):
        response = self.client.get(self.endpoint)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(
            response.data["results"][0],
            {
                "id": 1,
                "child": 1,
                "temperature": 98.6,
                "time": "2017-11-17T12:52:00-05:00",
                "notes": "tympanic",
                "tags": [],
            },
        )

    def test_post(self):
        data = {
            "child": 1,
            "temperature": "100.1",
            "time": "2017-11-20T22:52:00-05:00",
            "notes": "rectal",
        }
        response = self.client.post(self.endpoint, data, format="json")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        obj = models.Temperature.objects.get(pk=response.data["id"])
        self.assertEqual(str(obj.temperature), data["temperature"])
        self.assertEqual(obj.notes, data["notes"])

    def test_post_null_time(self):
        data = {
            "child": 1,
            "temperature": "100.5",
            "notes": "temporal",
        }
        response = self.client.post(self.endpoint, data, format="json")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        obj = models.Temperature.objects.get(pk=response.data["id"])
        self.assertEqual(str(obj.temperature), data["temperature"])
        self.assertEqual(obj.notes, data["notes"])

    def test_patch(self):
        endpoint = "{}{}/".format(self.endpoint, 1)
        response = self.client.get(endpoint)
        entry = response.data
        entry["temperature"] = 99
        response = self.client.patch(
            endpoint,
            {
                "temperature": entry["temperature"],
            },
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data, entry)


class TimerAPITestCase(TestBase.BabyBuddyAPITestCaseBase):
    endpoint = reverse("api:timer-list")
    model = models.Timer

    def test_get(self):
        response = self.client.get(self.endpoint)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["results"][0]["id"], 1)

    def test_post(self):
        data = {"name": "New fake timer", "user": 1}
        response = self.client.post(self.endpoint, data, format="json")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        obj = models.Timer.objects.get(pk=response.data["id"])
        self.assertEqual(obj.name, data["name"])

    def test_post_default_user(self):
        user = get_user_model().objects.first()
        response = self.client.post(self.endpoint)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        obj = models.Timer.objects.get(pk=response.data["id"])
        self.assertEqual(obj.user, user)

    def test_patch(self):
        endpoint = "{}{}/".format(self.endpoint, 1)
        response = self.client.get(endpoint)
        entry = response.data
        entry["name"] = "New Timer Name"
        response = self.client.patch(
            endpoint,
            {
                "name": entry["name"],
            },
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["name"], entry["name"])

    def test_start_restart_timer(self):
        endpoint = "{}{}/".format(self.endpoint, 1)
        response = self.client.get(endpoint)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        response = self.client.patch(f"{endpoint}restart/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        # Restart twice is allowed
        response = self.client.patch(f"{endpoint}restart/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)


class TummyTimeAPITestCase(TestBase.BabyBuddyAPITestCaseBase):
    endpoint = reverse("api:tummytime-list")
    model = models.TummyTime
    timer_test_data = {"milestone": "Timer test"}

    def test_get(self):
        response = self.client.get(self.endpoint)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(
            response.data["results"][0],
            {
                "id": 3,
                "child": 1,
                "start": "2017-11-18T15:30:00-05:00",
                "end": "2017-11-18T15:30:45-05:00",
                "duration": "00:00:45",
                "milestone": "",
                "notes": None,
                "tags": [],
            },
        )

    def test_post(self):
        data = {
            "child": 1,
            "start": "2017-11-18T12:30:00-05:00",
            "end": "2017-11-18T12:35:30-05:00",
            "milestone": "Rolled over.",
        }
        response = self.client.post(self.endpoint, data, format="json")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        obj = models.TummyTime.objects.get(pk=response.data["id"])
        self.assertEqual(str(obj.duration), "0:05:30")

    def test_post_notes(self):
        data = {
            "child": 1,
            "start": "2017-11-18T12:30:00-05:00",
            "end": "2017-11-18T12:35:30-05:00",
            "milestone": "Rolled over.",
            "notes": "First time on the play mat.",
        }
        response = self.client.post(self.endpoint, data, format="json")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        obj = models.TummyTime.objects.get(pk=response.data["id"])
        self.assertEqual(obj.notes, data["notes"])

    def test_patch(self):
        endpoint = "{}{}/".format(self.endpoint, 3)
        response = self.client.get(endpoint)
        entry = response.data
        entry["milestone"] = "Switched sides!"
        response = self.client.patch(
            endpoint,
            {
                "milestone": entry["milestone"],
            },
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data, entry)


class WeightAPITestCase(TestBase.BabyBuddyAPITestCaseBase):
    endpoint = reverse("api:weight-list")
    model = models.Weight

    def test_get(self):
        response = self.client.get(self.endpoint)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(
            response.data["results"][0],
            {
                "id": 2,
                "child": 1,
                "weight": 9.5,
                "date": "2017-11-18",
                "notes": "before feed",
                "tags": [],
            },
        )

    def test_post(self):
        data = {
            "child": 1,
            "weight": "9.75",
            "date": "2017-11-20",
            "notes": "after feed",
        }
        response = self.client.post(self.endpoint, data, format="json")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        obj = models.Weight.objects.get(pk=response.data["id"])
        self.assertEqual(str(obj.weight), data["weight"])
        self.assertEqual(str(obj.notes), data["notes"])

    def test_post_null_date(self):
        data = {
            "child": 1,
            "weight": "12.25",
            "notes": "with diaper at peds",
        }
        response = self.client.post(self.endpoint, data, format="json")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        obj = models.Weight.objects.get(pk=response.data["id"])
        self.assertEqual(str(obj.weight), data["weight"])
        self.assertEqual(str(obj.notes), data["notes"])

    def test_patch(self):
        endpoint = "{}{}/".format(self.endpoint, 2)
        response = self.client.get(endpoint)
        entry = response.data
        entry["weight"] = 8.25
        response = self.client.patch(
            endpoint,
            {
                "weight": entry["weight"],
            },
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data, entry)


class TestProfileAPITestCase(APITestCase):
    endpoint = reverse("api:profile")

    def setUp(self):
        self.client.login(username="admin", password="admin")

    def test_get(self):
        response = self.client.get(self.endpoint)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        self.assertEqual(
            response.data,
            response.data
            | {
                "language": "en-US",
                "timezone": "UTC",
            },
        )
        self.assertEqual(
            response.data["user"],
            response.data["user"]
            | {
                "id": 1,
                "username": "admin",
                "first_name": "",
                "last_name": "",
                "email": "",
                "is_staff": True,
            },
        )
        # Test that api_key is in the mix and "some long string"
        self.assertIn("api_key", response.data)
        self.assertTrue(isinstance(response.data["api_key"], str))
        self.assertGreater(len(response.data["api_key"]), 30)


class CaregiverAPITestCase(APITestCase):
    """
    A caregiver can log care entries, including medication, and use timers
    via the stock API, but cannot delete entries or manage users or tags.
    """

    fixtures = ["tests.json"]

    def setUp(self):
        self.caregiver = get_user_model().objects.create_user(
            username="caregiver", password="caregiver", is_active=True
        )
        self.caregiver.groups.add(
            Group.objects.get(name=settings.BABY_BUDDY["CAREGIVER_GROUP_NAME"])
        )
        # Re-fetch so group permissions are visible to the permission checks.
        self.caregiver = get_user_model().objects.get(username="caregiver")
        self.client.login(username="caregiver", password="caregiver")
        self.parent = models.Parent.objects.create(first_name="Alex")
        self.parent.children.add(models.Child.objects.get(pk=1))

    def test_caregiver_can_add_feeding(self):
        data = {
            "child": 1,
            "start": "2017-11-19T14:00:00-05:00",
            "end": "2017-11-19T14:15:00-05:00",
            "type": "breast milk",
            "method": "left breast",
            "notes": "with vitamins",
        }
        response = self.client.post(reverse("api:feeding-list"), data, format="json")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        obj = models.Feeding.objects.get(pk=response.data["id"])
        self.assertEqual(obj.type, data["type"])

    def test_caregiver_can_add_diaper_change(self):
        data = {
            "child": 1,
            "time": "2017-11-18T12:00:00-05:00",
            "wet": True,
            "solid": True,
            "color": "brown",
        }
        response = self.client.post(
            reverse("api:diaperchange-list"), data, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

    def test_caregiver_can_add_sleep(self):
        data = {
            "child": 1,
            "start": "2017-11-21T19:30:00-05:00",
            "end": "2017-11-21T23:00:00-05:00",
            "notes": "used new swaddle",
        }
        response = self.client.post(reverse("api:sleep-list"), data, format="json")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

    def test_caregiver_can_use_timers(self):
        response = self.client.post(
            reverse("api:timer-list"), {"name": "Nap timer"}, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        timer_id = response.data["id"]
        response = self.client.get(f"{reverse('api:timer-list')}{timer_id}/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_caregiver_can_view_child_dashboard_data(self):
        response = self.client.get(reverse("api:child-list"))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        response = self.client.get(reverse("api:feeding-list"))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        response = self.client.get(reverse("api:sleep-list"))
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_caregiver_cannot_delete_entries(self):
        endpoint = "{}3/".format(reverse("api:feeding-list"))
        self.assertEqual(self.client.get(endpoint).status_code, status.HTTP_200_OK)
        response = self.client.delete(endpoint)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_caregiver_can_add_medication(self):
        data = {"child": 1, "name": "Tylenol", "time": "2017-11-18T12:00:00-05:00"}
        response = self.client.post(reverse("api:medication-list"), data, format="json")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        response = self.client.get(reverse("api:medication-list"))
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_caregiver_can_add_temperature_note_and_tummy_time(self):
        endpoints_and_data = (
            (reverse("api:temperature-list"), {"child": 1, "temperature": 38.5}),
            (reverse("api:note-list"), {"child": 1, "note": "A note"}),
            (
                reverse("api:tummytime-list"),
                {
                    "child": 1,
                    "start": "2017-11-18T12:00:00-05:00",
                    "end": "2017-11-18T12:15:00-05:00",
                },
            ),
        )
        for endpoint, data in endpoints_and_data:
            response = self.client.post(endpoint, data, format="json")
            self.assertEqual(response.status_code, status.HTTP_201_CREATED, endpoint)

    def test_caregiver_can_add_weight(self):
        response = self.client.post(
            reverse("api:weight-list"),
            {"child": 1, "weight": 8.5, "date": "2017-11-18"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

    def test_caregiver_cannot_delete_medication(self):
        endpoint = "{}1/".format(reverse("api:medication-list"))
        response = self.client.delete(endpoint)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def grant(self, *codenames):
        self.caregiver.user_permissions.add(
            *Permission.objects.filter(
                content_type__app_label="core", codename__in=codenames
            )
        )

    def test_timer_consumption_without_delete_permission_is_limited_to_owner(self):
        self.grant("add_pumping")
        admin = get_user_model().objects.get(username="admin")
        for model, endpoint, extra in (
            (
                models.Feeding,
                "feeding",
                {"type": "breast milk", "method": "left breast"},
            ),
            (models.Sleep, "sleep", {}),
            (models.TummyTime, "tummytime", {}),
            (models.Pumping, "pumping", {"amount": 2}),
        ):
            for owner, allowed in ((self.caregiver, True), (admin, False)):
                with self.subTest(endpoint=endpoint, owner=owner.username):
                    timer = models.Timer.objects.create(
                        child_id=1,
                        user=owner,
                        start=timezone.now() - timezone.timedelta(minutes=5),
                    )
                    count = model.objects.count()
                    response = self.client.post(
                        reverse(f"api:{endpoint}-list"),
                        {"timer": timer.pk, **extra},
                        format="json",
                    )
                    if allowed:
                        self.assertEqual(response.status_code, 201, response.data)
                        self.assertEqual(model.objects.count(), count + 1)
                    else:
                        self.assertEqual(response.status_code, 403)
                        self.assertEqual(model.objects.count(), count)
                    self.assertEqual(
                        models.Timer.objects.filter(pk=timer.pk).exists(), not allowed
                    )

    def test_timer_owner_is_kept_without_delete_permission(self):
        admin = get_user_model().objects.get(username="admin")
        timer = models.Timer.objects.create(
            child_id=1, user=admin, start=timezone.now() - timezone.timedelta(minutes=5)
        )
        endpoint = f"{reverse('api:timer-list')}{timer.pk}/"
        response = self.client.patch(endpoint, {"name": "Renamed"}, format="json")
        self.assertEqual(response.status_code, 200)
        timer.refresh_from_db()
        self.assertEqual(timer.user, admin)
        response = self.client.patch(
            endpoint, {"user": self.caregiver.pk}, format="json"
        )
        self.assertEqual(response.status_code, 403)
        timer.refresh_from_db()
        self.assertEqual(timer.user, admin)
        response = self.client.post(
            reverse("api:sleep-list"), {"timer": timer.pk}, format="json"
        )
        self.assertEqual(response.status_code, 403)
        self.assertTrue(models.Timer.objects.filter(pk=timer.pk).exists())

    def request_as_caregiver(self):
        request = APIRequestFactory().post("/")
        request.user = self.caregiver
        return {"request": request}

    def test_timer_reassigned_after_validation_is_not_consumed(self):
        admin = get_user_model().objects.get(username="admin")
        timer = models.Timer.objects.create(
            child_id=1,
            user=self.caregiver,
            start=timezone.now() - timezone.timedelta(minutes=5),
        )
        serializer = serializers.SleepSerializer(
            data={"timer": timer.pk}, context=self.request_as_caregiver()
        )
        self.assertTrue(serializer.is_valid(), serializer.errors)
        models.Timer.objects.filter(pk=timer.pk).update(user=admin)
        count = models.Sleep.objects.count()
        with self.assertRaises(PermissionDenied):
            serializer.save()
        self.assertEqual(models.Sleep.objects.count(), count)
        self.assertTrue(models.Timer.objects.filter(pk=timer.pk).exists())

    def test_timer_update_does_not_restore_a_stale_owner(self):
        admin = get_user_model().objects.get(username="admin")
        timer = models.Timer.objects.create(child_id=1, user=self.caregiver)
        serializer = serializers.TimerSerializer(
            timer,
            data={"name": "Renamed"},
            partial=True,
            context=self.request_as_caregiver(),
        )
        self.assertTrue(serializer.is_valid(), serializer.errors)
        models.Timer.objects.filter(pk=timer.pk).update(user=admin)
        serializer.save()
        timer.refresh_from_db()
        self.assertEqual(timer.name, "Renamed")
        self.assertEqual(timer.user, admin)

    def test_timer_reassigned_after_validation_cannot_be_taken_back(self):
        admin = get_user_model().objects.get(username="admin")
        timer = models.Timer.objects.create(child_id=1, user=self.caregiver)
        serializer = serializers.TimerSerializer(
            timer,
            data={"user": self.caregiver.pk},
            partial=True,
            context=self.request_as_caregiver(),
        )
        self.assertTrue(serializer.is_valid(), serializer.errors)
        models.Timer.objects.filter(pk=timer.pk).update(user=admin)
        with self.assertRaises(PermissionDenied):
            serializer.save()
        timer.refresh_from_db()
        self.assertEqual(timer.user, admin)

    def test_delete_timer_grant_allows_changing_timer_user(self):
        self.grant("delete_timer")
        admin = get_user_model().objects.get(username="admin")
        timer = models.Timer.objects.create(child_id=1, user=admin)
        response = self.client.patch(
            f"{reverse('api:timer-list')}{timer.pk}/",
            {"user": self.caregiver.pk},
            format="json",
        )
        self.assertEqual(response.status_code, 200)
        timer.refresh_from_db()
        self.assertEqual(timer.user, self.caregiver)

    def test_timer_grant_consumes_only_after_successful_validation(self):
        self.grant("delete_timer")
        timer = models.Timer.objects.create(
            user=self.caregiver, start=timezone.now() - timezone.timedelta(minutes=5)
        )
        url = reverse("api:sleep-list")
        response = self.client.post(url, {"timer": timer.pk}, format="json")
        self.assertEqual(response.status_code, 400)
        self.assertTrue(models.Timer.objects.filter(pk=timer.pk).exists())
        response = self.client.post(url, {"timer": timer.pk, "child": 1}, format="json")
        self.assertEqual(response.status_code, 201, response.data)
        self.assertFalse(models.Timer.objects.filter(pk=timer.pk).exists())

    def test_invalid_and_missing_timer_input(self):
        self.grant("delete_timer")
        for data in ({}, {"timer": None}, {"timer": "bad"}, {"timer": 999999}):
            with self.subTest(data=data):
                response = self.client.post(
                    reverse("api:sleep-list"), data, format="json"
                )
                self.assertEqual(response.status_code, 400)

    def test_tag_permissions_on_post_and_patch(self):
        models.Tag.objects.create(name="existing")
        url = reverse("api:note-list")
        for tags in (["existing"], ["new"]):
            response = self.client.post(
                url, {"child": 1, "note": "note", "tags": tags}, format="json"
            )
            self.assertEqual(response.status_code, 403)
        self.assertFalse(models.Tag.objects.filter(name="new").exists())
        note = models.Note.objects.create(child_id=1, note="original")
        note.tags.add("existing")
        detail = f"{url}{note.pk}/"
        for tags in ([], ["new"]):
            response = self.client.patch(
                detail, {"child": 1, "note": "changed", "tags": tags}, format="json"
            )
            self.assertEqual(response.status_code, 403)
            note.refresh_from_db()
            self.assertEqual(note.note, "original")
            self.assertEqual(list(note.tags.names()), ["existing"])
        for extra in ({}, {"tags": ["existing"]}):
            response = self.client.patch(
                detail, {"child": 1, "note": "original", **extra}, format="json"
            )
            self.assertEqual(response.status_code, 200, response.data)
            self.assertEqual(list(note.tags.names()), ["existing"])

    def test_put_remains_unsupported_and_does_not_change_tags(self):
        note = models.Note.objects.create(child_id=1, note="original")
        note.tags.add("existing")
        for extra in ({}, {"tags": []}, {"tags": ["new"]}):
            response = self.client.put(
                f"{reverse('api:note-list')}{note.pk}/",
                {"child": 1, "note": "changed", **extra},
                format="json",
            )
            self.assertEqual(response.status_code, 405)
            note.refresh_from_db()
            self.assertEqual(note.note, "original")
            self.assertEqual(list(note.tags.names()), ["existing"])
        self.assertFalse(models.Tag.objects.filter(name="new").exists())

    def test_timer_save_failure_rolls_back_entry_and_retains_timer(self):
        self.grant("delete_timer")
        timer = models.Timer.objects.create(
            child_id=1,
            user=self.caregiver,
            start=timezone.now() - timezone.timedelta(minutes=5),
        )
        count = models.Sleep.objects.count()
        original_save = models.Sleep.save

        def failing_save(instance, *args, **kwargs):
            original_save(instance, *args, **kwargs)
            raise RuntimeError("save failed")

        with patch.object(models.Sleep, "save", failing_save):
            with self.assertRaisesMessage(RuntimeError, "save failed"):
                self.client.post(
                    reverse("api:sleep-list"), {"timer": timer.pk}, format="json"
                )
        self.assertEqual(models.Sleep.objects.count(), count)
        self.assertTrue(models.Timer.objects.filter(pk=timer.pk).exists())

    def test_tag_permission_grants(self):
        models.Tag.objects.create(name="existing")
        self.grant("change_tag")
        url = reverse("api:note-list")
        response = self.client.post(
            url, {"child": 1, "note": "note", "tags": ["existing"]}, format="json"
        )
        self.assertEqual(response.status_code, 201, response.data)
        detail = f"{url}{response.data['id']}/"
        response = self.client.patch(detail, {"tags": []}, format="json")
        self.assertEqual(response.status_code, 200)
        response = self.client.patch(detail, {"tags": ["new"]}, format="json")
        self.assertEqual(response.status_code, 403)
        self.assertFalse(models.Tag.objects.filter(name="new").exists())
        self.grant("add_tag")
        response = self.client.patch(detail, {"tags": ["new"]}, format="json")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["tags"], ["new"])

    def test_caregiver_cannot_tag_admin(self):
        response = self.client.get(reverse("api:tag-list"))
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_caregiver_without_view_pumping_cannot_read_stash(self):
        # The caregiver group grants ordinary care-log permissions (feeding,
        # etc.) but not view_pumping, so the stash summary stays out of reach.
        response = self.client.get("/api/stash")
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)


class CaregiverWebTestCase(APITestCase):
    """
    The same caregiver scope applies to the web UI: care entries, reports
    and the (child) dashboard are reachable, while user management and
    site settings are not.
    """

    fixtures = ["tests.json"]

    def setUp(self):
        self.caregiver = get_user_model().objects.create_user(
            username="caregiver", password="caregiver", is_active=True
        )
        self.caregiver.groups.add(
            Group.objects.get(name=settings.BABY_BUDDY["CAREGIVER_GROUP_NAME"])
        )
        self.client.login(username="caregiver", password="caregiver")

    def test_caregiver_can_open_care_entry_pages(self):
        for url in [
            "/feedings/add/",
            "/changes/add/",
            "/sleep/add/",
            "/timers/add/",
            "/dashboard/",
            # Personal preferences stay available to every logged-in user.
            "/user/settings/",
        ]:
            page = self.client.get(url)
            self.assertIn(
                page.status_code,
                (status.HTTP_200_OK, status.HTTP_302_FOUND),
                f"caregiver should reach {url}",
            )

    def test_caregiver_cannot_open_user_management(self):
        for url in ["/users/", "/users/add/", "/settings/"]:
            page = self.client.get(url)
            self.assertIn(
                page.status_code,
                (status.HTTP_302_FOUND, status.HTTP_403_FORBIDDEN),
                f"caregiver should be blocked from {url}",
            )


class WebhookEndpointAPITestCase(APITestCase):
    """
    Another application can set up its own webhook endpoint, and nobody can
    read a secret back once it has been set.
    """

    fixtures = ["tests.json"]
    endpoint = reverse("api:webhookendpoint-list")

    def setUp(self):
        self.client.login(username="admin", password="admin")

    def test_create_returns_the_generated_secret_once(self):
        response = self.client.post(
            self.endpoint,
            {"name": "Phone", "url": "https://push.example.com/hook/abc"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        endpoint = WebhookEndpoint.objects.get(pk=response.data["id"])
        self.assertEqual(response.data["secret"], endpoint.secret)
        self.assertGreaterEqual(len(endpoint.secret), 16)
        detail = self.client.get("{}{}/".format(self.endpoint, endpoint.pk))
        self.assertNotIn("secret", detail.data)
        listed = self.client.get(self.endpoint)
        self.assertNotIn("secret", listed.data["results"][0])

    def test_create_keeps_a_secret_the_client_chose(self):
        secret = "a-secret-the-receiver-issued-0123"
        response = self.client.post(
            self.endpoint,
            {
                "name": "Phone",
                "url": "https://push.example.com/hook/abc",
                "secret": secret,
            },
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(
            WebhookEndpoint.objects.get(pk=response.data["id"]).secret, secret
        )
        self.assertEqual(response.data["secret"], secret)

    def test_a_short_secret_or_a_url_nothing_is_sent_to_is_refused(self):
        for data in (
            {
                "name": "Short",
                "url": "https://push.example.com/hook",
                "secret": "too-short",
            },
            {"name": "FTP", "url": "ftp://push.example.com/hook"},
        ):
            response = self.client.post(self.endpoint, data, format="json")
            self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST, data)
        self.assertFalse(WebhookEndpoint.objects.exists())

    def test_patch_switches_off_and_replaces_the_secret(self):
        endpoint = WebhookEndpoint.objects.create(
            name="Phone", url="https://push.example.com/hook/abc"
        )
        new_secret = "a-replacement-secret-0123456789"
        response = self.client.patch(
            "{}{}/".format(self.endpoint, endpoint.pk),
            {"active": False, "secret": new_secret},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertNotIn("secret", response.data)
        endpoint.refresh_from_db()
        self.assertFalse(endpoint.active)
        self.assertEqual(endpoint.secret, new_secret)

    def test_delete(self):
        endpoint = WebhookEndpoint.objects.create(
            name="Phone", url="https://push.example.com/hook/abc"
        )
        response = self.client.delete("{}{}/".format(self.endpoint, endpoint.pk))
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(WebhookEndpoint.objects.exists())

    def test_caregivers_and_read_only_users_cannot_see_or_add_endpoints(self):
        WebhookEndpoint.objects.create(name="Phone", url="https://push.example.com/a")
        for group in ("CAREGIVER_GROUP_NAME", "READ_ONLY_GROUP_NAME"):
            user = get_user_model().objects.create_user(
                username=group.lower(), password="password"
            )
            user.groups.add(Group.objects.get(name=settings.BABY_BUDDY[group]))
            self.client.login(username=group.lower(), password="password")
            self.assertEqual(
                self.client.get(self.endpoint).status_code, status.HTTP_403_FORBIDDEN
            )
            response = self.client.post(
                self.endpoint,
                {"name": "Mine", "url": "https://elsewhere.example.com/"},
                format="json",
            )
            self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(WebhookEndpoint.objects.count(), 1)


class CaregiverManagementAPITestCase(APITestCase):
    """
    A caregiver account can be created and withdrawn through the API, and
    that route reaches caregiver accounts and nothing else.
    """

    fixtures = ["tests.json"]
    endpoint = reverse("api:caregiver-list")

    def setUp(self):
        self.client.login(username="admin", password="admin")

    def create(self, **extra):
        data = {"username": "grandma", "first_name": "Grandma", **extra}
        response = self.client.post(self.endpoint, data, format="json")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.data)
        return response

    def with_key(self, key):
        client = self.client_class()
        client.credentials(HTTP_AUTHORIZATION="Token " + key)
        return client

    def test_create_makes_a_caregiver_and_returns_their_key_once(self):
        response = self.create()
        user = get_user_model().objects.get(username="grandma")
        self.assertTrue(
            user.groups.filter(
                name=settings.BABY_BUDDY["CAREGIVER_GROUP_NAME"]
            ).exists()
        )
        self.assertFalse(user.is_staff)
        self.assertFalse(user.is_superuser)
        self.assertFalse(user.has_usable_password())
        self.assertEqual(response.data["api_key"], user.settings.api_key().key)
        detail = self.client.get("{}{}/".format(self.endpoint, user.pk))
        self.assertNotIn("api_key", detail.data)

        # The key works within the caregiver's scope and not beyond it.
        sitter = self.with_key(response.data["api_key"])
        self.assertEqual(
            sitter.get(reverse("api:feeding-list")).status_code, status.HTTP_200_OK
        )
        self.assertEqual(
            sitter.get(self.endpoint).status_code, status.HTTP_403_FORBIDDEN
        )

    def test_an_email_lets_the_caregiver_claim_the_account(self):
        self.create(email="grandma@example.com")
        user = get_user_model().objects.get(username="grandma")
        self.assertEqual(user.email, "grandma@example.com")
        self.assertTrue(user.has_usable_password())

        # This is what the address buys: the reset form skips accounts whose
        # password is unusable, and this one has a password nobody knows, so
        # the mailbox holder is the one who can set a real one.
        form = PasswordResetForm({"email": "grandma@example.com"})
        self.assertTrue(form.is_valid())
        self.assertEqual(list(form.get_users("grandma@example.com")), [user])

    def test_an_email_added_later_opens_the_same_route(self):
        self.create()
        user = get_user_model().objects.get(username="grandma")
        self.assertFalse(user.has_usable_password())

        response = self.client.patch(
            "{}{}/".format(self.endpoint, user.pk),
            {"email": "grandma@example.com"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        user.refresh_from_db()
        self.assertTrue(user.has_usable_password())
        self.assertEqual(
            list(PasswordResetForm({"email": user.email}).get_users(user.email)),
            [user],
        )

    def test_the_role_cannot_be_raised_through_the_request(self):
        self.create(is_staff=True, is_superuser=True, groups=[1])
        user = get_user_model().objects.get(username="grandma")
        self.assertFalse(user.is_staff)
        self.assertFalse(user.is_superuser)
        self.assertEqual(
            list(user.groups.values_list("name", flat=True)),
            [settings.BABY_BUDDY["CAREGIVER_GROUP_NAME"]],
        )
        response = self.client.patch(
            "{}{}/".format(self.endpoint, user.pk),
            {"is_staff": True, "is_superuser": True},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        user.refresh_from_db()
        self.assertFalse(user.is_staff or user.is_superuser)

    def test_other_accounts_are_out_of_reach(self):
        admin = get_user_model().objects.get(username="admin")
        self.assertEqual(
            self.client.get("{}{}/".format(self.endpoint, admin.pk)).status_code,
            status.HTTP_404_NOT_FOUND,
        )
        response = self.client.patch(
            "{}{}/".format(self.endpoint, admin.pk), {"is_active": False}, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        admin.refresh_from_db()
        self.assertTrue(admin.is_active)
        self.create()
        listed = self.client.get(self.endpoint)
        self.assertEqual(
            [row["username"] for row in listed.data["results"]], ["grandma"]
        )

    def test_deactivating_or_an_expiry_in_the_past_ends_access(self):
        key = self.create().data["api_key"]
        user = get_user_model().objects.get(username="grandma")
        detail = "{}{}/".format(self.endpoint, user.pk)
        self.client.patch(
            detail,
            {
                "access_expires": (
                    timezone.now() - timezone.timedelta(hours=1)
                ).isoformat()
            },
            format="json",
        )
        self.assertIn(
            self.with_key(key).get(reverse("api:feeding-list")).status_code,
            (status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN),
        )
        self.client.patch(
            detail, {"access_expires": None, "is_active": False}, format="json"
        )
        self.assertIn(
            self.with_key(key).get(reverse("api:feeding-list")).status_code,
            (status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN),
        )
        self.client.patch(detail, {"is_active": True}, format="json")
        self.assertEqual(
            self.with_key(key).get(reverse("api:feeding-list")).status_code,
            status.HTTP_200_OK,
        )

    def test_an_expiry_can_be_set_when_the_account_is_created(self):
        expires = timezone.now() + timezone.timedelta(days=1)
        response = self.create(access_expires=expires.isoformat())
        user = get_user_model().objects.get(username="grandma")
        self.assertEqual(user.settings.access_expires, expires)
        self.assertIsNotNone(response.data["access_expires"])

    def test_there_is_no_delete(self):
        self.create()
        user = get_user_model().objects.get(username="grandma")
        response = self.client.delete("{}{}/".format(self.endpoint, user.pk))
        self.assertEqual(response.status_code, status.HTTP_405_METHOD_NOT_ALLOWED)
        self.assertTrue(get_user_model().objects.filter(username="grandma").exists())

    def test_caregivers_and_read_only_users_cannot_manage_caregivers(self):
        for group in ("CAREGIVER_GROUP_NAME", "READ_ONLY_GROUP_NAME"):
            user = get_user_model().objects.create_user(
                username=group.lower(), password="password"
            )
            user.groups.add(Group.objects.get(name=settings.BABY_BUDDY[group]))
            self.client.login(username=group.lower(), password="password")
            response = self.client.post(
                self.endpoint, {"username": "someone"}, format="json"
            )
            self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertFalse(get_user_model().objects.filter(username="someone").exists())


class TestSchemaAPITestCase(APITestCase):
    endpoint = reverse("api:openapi-schema")

    def setUp(self):
        self.client.login(username="admin", password="admin")

    def test_get(self):
        response = self.client.get(self.endpoint)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_get_includes_filter_parameters(self):
        """
        Filter parameters must appear in the schema.

        django-filter removed its built-in schema generation methods in 25.1,
        which made this endpoint raise an AttributeError.
        """
        response = self.client.get(self.endpoint)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        parameters = response.data["paths"]["/api/feedings/"]["get"]["parameters"]
        names = [parameter["name"] for parameter in parameters]
        for name in ("child", "start", "start_min", "end", "end_max", "tags"):
            self.assertIn(name, names)
