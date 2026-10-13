# -*- coding: utf-8 -*-
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.urls import reverse
from django.utils import timezone

from rest_framework import status
from rest_framework.test import APITestCase

from core import models as core_models
from stash import models
from webhooks.models import WebhookEndpoint, WebhookEvent


class StashAPITestCase(APITestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="parent", password="parent", is_superuser=True
        )
        self.client.login(username="parent", password="parent")
        self.child = core_models.Child.objects.create(
            first_name="First", last_name="Last", birth_date=timezone.localdate()
        )

    def test_api_root_lists_the_stash(self):
        response = self.client.get("/api/")
        self.assertIn("stash", response.data)
        self.assertIn("stash-adjustments", response.data)

    def test_adjustments(self):
        endpoint = reverse("api:stashadjustment-list")
        response = self.client.post(
            endpoint,
            {
                "time": "2026-01-02T08:00:00Z",
                "amount": 120,
                "kind": "added",
                "notes": "From the freezer",
                "tags": ["freezer"],
            },
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        adjustment = models.StashAdjustment.objects.get(pk=response.data["id"])
        self.assertEqual(adjustment.amount, 120)
        self.assertEqual(list(adjustment.tags.names()), ["freezer"])

        response = self.client.patch(
            f"{endpoint}{adjustment.id}/", {"kind": "discarded"}, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["kind"], "discarded")

        response = self.client.get(endpoint, {"kind": "added"})
        self.assertEqual(response.data["count"], 0)
        response = self.client.get(endpoint, {"date_min": "2026-01-02T07:00:00Z"})
        self.assertEqual(response.data["count"], 1)

    def test_adjustment_validation(self):
        endpoint = reverse("api:stashadjustment-list")
        response = self.client.post(
            endpoint, {"amount": 0, "kind": "added"}, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("amount", response.data)
        response = self.client.post(
            endpoint, {"amount": 10, "kind": "spilled"}, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("kind", response.data)

    def test_stash(self):
        end = timezone.now() - timezone.timedelta(hours=80)
        pumping = core_models.Pumping.objects.create(
            child=self.child,
            start=end - timezone.timedelta(minutes=10),
            end=end,
            amount=100,
            to_stash=True,
        )
        adjustment = models.StashAdjustment.objects.create(amount=30, kind="added")
        response = self.client.get(reverse("api:stash"))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(
            set(response.data),
            {
                "balance",
                "status",
                "warn_age_hours",
                "max_age_hours",
                "expired_amount",
                "lots",
            },
        )
        self.assertEqual(response.data["balance"], 130)
        self.assertEqual(response.data["status"], "expired")
        self.assertEqual(response.data["expired_amount"], 100)
        self.assertEqual(
            [(lot["amount"], lot["status"]) for lot in response.data["lots"]],
            [(100, "expired"), (30, "ok")],
        )
        self.assertEqual(
            set(response.data["lots"][0]),
            {"time", "amount", "warn_at", "expires_at", "status", "source"},
        )
        self.assertEqual(
            [lot["source"] for lot in response.data["lots"]],
            [
                {"type": "pumping", "id": pumping.id},
                {"type": "stash_adjustment", "id": adjustment.id},
            ],
        )

    def test_stash_needs_the_view_permission(self):
        user = get_user_model().objects.create_user(username="other", password="other")
        self.client.login(username="other", password="other")
        self.assertEqual(
            self.client.get(reverse("api:stash")).status_code,
            status.HTTP_403_FORBIDDEN,
        )
        user.user_permissions.add(
            Permission.objects.get(codename="view_stashadjustment")
        )
        self.assertEqual(
            self.client.get(reverse("api:stash")).status_code, status.HTTP_200_OK
        )

    def test_webhook_events(self):
        WebhookEndpoint.objects.create(name="Home", url="https://example.com/hook")
        adjustment = models.StashAdjustment.objects.create(amount=30, kind="added")
        adjustment.delete()
        self.assertEqual(
            list(WebhookEvent.objects.order_by("id").values_list("type", flat=True)),
            ["stash_adjustment.created", "stash_adjustment.deleted"],
        )
