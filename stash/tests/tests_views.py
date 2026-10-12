# -*- coding: utf-8 -*-
from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.test import TestCase
from django.utils import timezone

from core import models as core_models
from stash import models


class StashViewsTestCase(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="parent", password="parent", is_superuser=True
        )
        self.client.login(username="parent", password="parent")
        self.child = core_models.Child.objects.create(
            first_name="First", last_name="Last", birth_date=timezone.localdate()
        )

    def stored(self, amount=100, hours_ago=1):
        end = timezone.localtime() - timezone.timedelta(hours=hours_ago)
        return core_models.Pumping.objects.create(
            child=self.child,
            start=end - timezone.timedelta(minutes=15),
            end=end,
            amount=amount,
            to_stash=True,
        )

    def test_pages(self):
        adjustment = models.StashAdjustment.objects.create(amount=20, kind="added")
        for url in (
            "/stash/",
            "/stash/adjustments/",
            "/stash/adjustments/add/",
            f"/stash/adjustments/{adjustment.id}/",
            f"/stash/adjustments/{adjustment.id}/delete/",
        ):
            with self.subTest(url=url):
                self.assertEqual(self.client.get(url).status_code, 200)

    def test_stash_page(self):
        page = self.client.get("/stash/")
        self.assertContains(page, "The stash is empty.")

        self.stored(100, hours_ago=80)
        self.stored(40)
        page = self.client.get("/stash/")
        self.assertContains(page, "140")
        self.assertContains(page, "Expired")
        self.assertContains(
            page,
            "/stash/adjustments/add/?kind=discarded&amount=100.0&notes=Expired%20milk",
        )

    def test_below_zero(self):
        core_models.Feeding.objects.create(
            child=self.child,
            start=timezone.localtime(),
            end=timezone.localtime(),
            type="breast milk",
            method="bottle",
            amount=60,
            from_stash=True,
        )
        page = self.client.get("/stash/")
        self.assertContains(page, "-60")
        self.assertContains(page, "More milk was taken from the stash")

    def test_add_is_prefilled_from_the_query(self):
        page = self.client.get(
            "/stash/adjustments/add/",
            {"kind": "discarded", "amount": "12.5", "notes": "Expired milk"},
        )
        form = page.context["form"]
        self.assertEqual(form.initial["kind"], "discarded")
        self.assertEqual(form.initial["amount"], "12.5")
        self.assertEqual(form.initial["notes"], "Expired milk")

    def test_add(self):
        page = self.client.post(
            "/stash/adjustments/add/",
            {
                "kind": "added",
                "time": timezone.localtime().strftime("%Y-%m-%dT%H:%M:%S"),
                "amount": 150,
            },
            follow=True,
        )
        self.assertRedirects(page, "/stash/")
        self.assertEqual(models.StashAdjustment.objects.get().amount, 150)
        self.assertContains(page, "150")

    def test_bottle_from_the_stash(self):
        self.stored(100)
        page = self.client.post(
            "/feedings/bottle/add/",
            {
                "child": self.child.id,
                "type": "breast milk",
                "start": timezone.localtime().strftime("%Y-%m-%dT%H:%M:%S"),
                "amount": 60,
                "from_stash": "on",
            },
        )
        self.assertEqual(page.status_code, 302)
        feeding = core_models.Feeding.objects.get()
        self.assertTrue(feeding.from_stash)
        self.assertEqual(feeding.method, "bottle")
        self.assertContains(self.client.get("/stash/"), "40")

        page = self.client.post(
            "/feedings/bottle/add/",
            {
                "child": self.child.id,
                "type": "formula",
                "start": timezone.localtime().strftime("%Y-%m-%dT%H:%M:%S"),
                "amount": 60,
                "from_stash": "on",
            },
        )
        self.assertEqual(page.status_code, 200)
        self.assertContains(page, "Only breast milk can come from the milk stash.")

    def test_dashboard_card(self):
        page = self.client.get(f"/children/{self.child.slug}/dashboard/")
        card = '<a href="/stash/">Milk stash</a>'
        self.assertNotContains(page, card)
        self.stored(100)
        page = self.client.get(f"/children/{self.child.slug}/dashboard/")
        self.assertContains(page, card)

    def test_caregiver_has_no_stash(self):
        caregiver = get_user_model().objects.create_user(
            username="caregiver", password="caregiver"
        )
        caregiver.groups.add(
            Group.objects.get(name=settings.BABY_BUDDY["CAREGIVER_GROUP_NAME"])
        )
        self.client.login(username="caregiver", password="caregiver")
        self.assertEqual(self.client.get("/stash/").status_code, 403)

    def test_read_only_sees_the_stash(self):
        reader = get_user_model().objects.create_user(
            username="reader", password="reader"
        )
        reader.groups.add(
            Group.objects.get(name=settings.BABY_BUDDY["READ_ONLY_GROUP_NAME"])
        )
        self.client.login(username="reader", password="reader")
        self.assertEqual(self.client.get("/stash/").status_code, 200)
        self.assertEqual(self.client.get("/stash/adjustments/add/").status_code, 403)
