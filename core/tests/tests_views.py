# -*- coding: utf-8 -*-
import re

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.core.management import call_command
from django.db import connection
from django.test import TestCase
from django.test.utils import CaptureQueriesContext
from django.test import Client as HttpClient
from django.utils import timezone

from faker import Faker

from core import models, views


class ViewsTestCase(TestCase):
    @classmethod
    def setUpClass(cls):
        super(ViewsTestCase, cls).setUpClass()
        fake = Faker()
        call_command("migrate", verbosity=0)
        call_command("fake", verbosity=0)

        cls.c = HttpClient()

        fake_user = fake.simple_profile()
        cls.credentials = {
            "username": fake_user["username"],
            "password": fake.password(),
        }
        cls.user = get_user_model().objects.create_user(
            is_superuser=True, **cls.credentials
        )

        cls.c.login(**cls.credentials)

    def test_bmi_views(self):
        page = self.c.get("/bmi/")
        self.assertEqual(page.status_code, 200)
        page = self.c.get("/bmi/add/")
        self.assertEqual(page.status_code, 200)

        entry = models.BMI.objects.first()
        page = self.c.get("/bmi/{}/".format(entry.id))
        self.assertEqual(page.status_code, 200)
        page = self.c.get("/bmi/{}/delete/".format(entry.id))
        self.assertEqual(page.status_code, 200)

    def test_child_views(self):
        page = self.c.get("/children/")
        self.assertEqual(page.status_code, 200)
        page = self.c.get("/children/add/")
        self.assertEqual(page.status_code, 200)

        entry = models.Child.objects.first()
        page = self.c.get("/children/{}/".format(entry.slug))
        self.assertEqual(page.status_code, 200)
        page = self.c.get(
            "/children/{}/".format(entry.slug),
            {"date": timezone.localdate() - timezone.timedelta(days=1)},
        )
        self.assertEqual(page.status_code, 200)

        page = self.c.get("/children/{}/edit/".format(entry.slug))
        self.assertEqual(page.status_code, 200)
        page = self.c.get("/children/{}/delete/".format(entry.slug))
        self.assertEqual(page.status_code, 200)

    def test_diaperchange_views(self):
        page = self.c.get("/changes/")
        self.assertEqual(page.status_code, 200)
        page = self.c.get("/changes/add/")
        self.assertEqual(page.status_code, 200)

        entry = models.DiaperChange.objects.first()
        page = self.c.get("/changes/{}/".format(entry.id))
        self.assertEqual(page.status_code, 200)
        page = self.c.get("/changes/{}/delete/".format(entry.id))
        self.assertEqual(page.status_code, 200)

    def test_feeding_admin_shows_and_filters_by_parent(self):
        admin = get_user_model().objects.create_superuser("feeding-admin")
        client = HttpClient()
        client.force_login(admin)
        parent = models.Parent.objects.first()
        page = client.get("/admin/core/feeding/?parent__id__exact={}".format(parent.id))
        self.assertEqual(page.status_code, 200)
        self.assertContains(page, "column-parent")

    def test_feeding_views(self):
        page = self.c.get("/feedings/")
        self.assertEqual(page.status_code, 200)
        page = self.c.get("/feedings/add/")
        self.assertEqual(page.status_code, 200)

        entry = models.Feeding.objects.first()
        page = self.c.get("/feedings/{}/".format(entry.id))
        self.assertEqual(page.status_code, 200)
        page = self.c.get("/feedings/{}/delete/".format(entry.id))
        self.assertEqual(page.status_code, 200)

    def test_headcircumference_views(self):
        page = self.c.get("/head-circumference/")
        self.assertEqual(page.status_code, 200)
        page = self.c.get("/head-circumference/add/")
        self.assertEqual(page.status_code, 200)

        entry = models.HeadCircumference.objects.first()
        page = self.c.get("/head-circumference/{}/".format(entry.id))
        self.assertEqual(page.status_code, 200)
        page = self.c.get("/head-circumference/{}/delete/".format(entry.id))
        self.assertEqual(page.status_code, 200)

    def test_height_views(self):
        page = self.c.get("/height/")
        self.assertEqual(page.status_code, 200)
        page = self.c.get("/height/add/")
        self.assertEqual(page.status_code, 200)

        entry = models.Height.objects.first()
        page = self.c.get("/height/{}/".format(entry.id))
        self.assertEqual(page.status_code, 200)
        page = self.c.get("/height/{}/delete/".format(entry.id))
        self.assertEqual(page.status_code, 200)

    def test_note_views(self):
        page = self.c.get("/notes/")
        self.assertEqual(page.status_code, 200)
        page = self.c.get("/notes/add/")
        self.assertEqual(page.status_code, 200)

        entry = models.Note.objects.first()
        page = self.c.get("/notes/{}/".format(entry.id))
        self.assertEqual(page.status_code, 200)
        page = self.c.get("/notes/{}/delete/".format(entry.id))
        self.assertEqual(page.status_code, 200)

    def test_parent_views(self):
        page = self.c.get("/parents/")
        self.assertEqual(page.status_code, 200)
        page = self.c.get("/parents/add/")
        self.assertEqual(page.status_code, 200)

    def test_pumping_views(self):
        page = self.c.get("/pumping/")
        self.assertEqual(page.status_code, 200)
        page = self.c.get("/pumping/add/")
        self.assertEqual(page.status_code, 200)

        entry = models.Pumping.objects.first()
        page = self.c.get("/pumping/{}/".format(entry.id))
        self.assertEqual(page.status_code, 200)
        page = self.c.get("/pumping/{}/delete/".format(entry.id))
        self.assertEqual(page.status_code, 200)

    def test_stash_views(self):
        page = self.c.get("/stash/")
        self.assertEqual(page.status_code, 200)
        page = self.c.get("/stash/adjustments/")
        self.assertEqual(page.status_code, 200)
        page = self.c.get("/stash/adjustments/add/")
        self.assertEqual(page.status_code, 200)

    def test_sleep_views(self):
        page = self.c.get("/sleep/")
        self.assertEqual(page.status_code, 200)
        page = self.c.get("/sleep/add/")
        self.assertEqual(page.status_code, 200)

        entry = models.Sleep.objects.first()
        page = self.c.get("/sleep/{}/".format(entry.id))
        self.assertEqual(page.status_code, 200)
        page = self.c.get("/sleep/{}/delete/".format(entry.id))
        self.assertEqual(page.status_code, 200)

    def test_tags_views(self):
        page = self.c.get("/tags/")
        self.assertEqual(page.status_code, 200)
        page = self.c.get("/tags/add/")
        self.assertEqual(page.status_code, 200)

        entry = models.Tag.objects.first()
        page = self.c.get("/tags/{}/".format(entry.slug))
        self.assertEqual(page.status_code, 200)
        entry = models.Tag.objects.first()
        page = self.c.get("/tags/{}/edit".format(entry.slug))
        self.assertEqual(page.status_code, 200)
        page = self.c.get("/tags/{}/delete/".format(entry.slug))
        self.assertEqual(page.status_code, 200)

    def test_temperature_views(self):
        page = self.c.get("/temperature/")
        self.assertEqual(page.status_code, 200)
        page = self.c.get("/temperature/add/")
        self.assertEqual(page.status_code, 200)

        entry = models.Temperature.objects.first()
        page = self.c.get("/temperature/{}/".format(entry.id))
        self.assertEqual(page.status_code, 200)
        page = self.c.get("/temperature/{}/delete/".format(entry.id))
        self.assertEqual(page.status_code, 200)

    def test_medication_views(self):
        page = self.c.get("/medication/")
        self.assertEqual(page.status_code, 200)
        page = self.c.get("/medication/add/")
        self.assertEqual(page.status_code, 200)

        entry = models.Medication.objects.first()
        page = self.c.get("/medication/{}/".format(entry.id))
        self.assertEqual(page.status_code, 200)
        page = self.c.get("/medication/{}/delete/".format(entry.id))
        self.assertEqual(page.status_code, 200)

    def test_timer_views(self):
        page = self.c.get("/timers/")
        self.assertEqual(page.status_code, 200)
        page = self.c.get("/timers/add/")
        self.assertEqual(page.status_code, 200)

        page = self.c.get("/timers/add/quick/")
        self.assertEqual(page.status_code, 405)
        page = self.c.post("/timers/add/quick/", follow=True)
        self.assertEqual(page.status_code, 200)

        entry = models.Timer.objects.first()
        page = self.c.get("/timers/{}/".format(entry.id))
        self.assertEqual(page.status_code, 200)
        page = self.c.get("/timers/{}/edit/".format(entry.id))
        self.assertEqual(page.status_code, 200)
        page = self.c.get("/timers/{}/delete/".format(entry.id))
        self.assertEqual(page.status_code, 200)

        page = self.c.get("/timers/{}/restart/".format(entry.id))
        self.assertEqual(page.status_code, 405)
        page = self.c.post("/timers/{}/restart/".format(entry.id), follow=True)
        self.assertEqual(page.status_code, 200)

    def test_timer_add_quick_assigns_posted_child(self):
        child = models.Child.objects.first()
        models.Child.objects.create(
            first_name="Second", last_name="Child", birth_date="2000-01-01"
        )
        response = self.c.post("/timers/add/quick/", {"child": child.pk}, follow=True)
        self.assertEqual(response.status_code, 200)
        timer = models.Timer.objects.latest("id")
        self.assertEqual(timer.child, child)

    def test_quick_timer_buttons_post_child_as_hidden_input(self):
        models.Child.objects.create(
            first_name="Second", last_name="Child", birth_date="2000-01-01"
        )
        page = self.c.get("/timers/")
        self.assertEqual(page.status_code, 200)
        self.assertContains(page, 'type="hidden" name="child"')
        self.assertNotRegex(page.content.decode("utf-8"), r"<button[^>]*name=\"child\"")

    def test_compact_quick_timer_buttons_post_child_as_hidden_input(self):
        models.Child.objects.create(
            first_name="Second", last_name="Child", birth_date="2000-01-01"
        )
        child = models.Child.objects.first()
        page = self.c.get("/children/{}/".format(child.slug))
        self.assertEqual(page.status_code, 200)
        self.assertContains(page, 'id="quick-timer-menu-toggle"')
        self.assertContains(page, 'type="hidden" name="child"')
        self.assertNotRegex(page.content.decode("utf-8"), r"<button[^>]*name=\"child\"")

    def test_timeline_views(self):
        child = models.Child.objects.first()
        response = self.c.get("/timeline/")
        self.assertRedirects(response, "/children/{}/".format(child.slug))

        models.Child.objects.create(
            first_name="Second", last_name="Child", birth_date="2000-01-01"
        )
        response = self.c.get("/timeline/")
        self.assertEqual(response.status_code, 200)

    def test_tummytime_views(self):
        page = self.c.get("/tummy-time/")
        self.assertEqual(page.status_code, 200)
        page = self.c.get("/tummy-time/add/")
        self.assertEqual(page.status_code, 200)

        entry = models.TummyTime.objects.first()
        page = self.c.get("/tummy-time/{}/".format(entry.id))
        self.assertEqual(page.status_code, 200)
        page = self.c.get("/tummy-time/{}/delete/".format(entry.id))
        self.assertEqual(page.status_code, 200)

    def test_weight_views(self):
        page = self.c.get("/weight/")
        self.assertEqual(page.status_code, 200)
        page = self.c.get("/weight/add/")
        self.assertEqual(page.status_code, 200)

        entry = models.Weight.objects.first()
        page = self.c.get("/weight/{}/".format(entry.id))
        self.assertEqual(page.status_code, 200)
        page = self.c.get("/weight/{}/delete/".format(entry.id))
        self.assertEqual(page.status_code, 200)


CARE_ENTRY_PERMISSIONS = (
    "view_child",
    "view_timer",
    "view_feeding",
    "view_diaperchange",
    "view_sleep",
)


class TimelinePermissionsTestCase(TestCase):
    """
    The timeline pulls events from every core model. It only includes the
    event types the user has the matching `view` permission for.
    """

    fixtures = ["tests.json"]

    def setUp(self):
        self.child = models.Child.objects.first()
        now = timezone.localtime()
        models.Medication.objects.create(
            child=self.child, name="Timeline Medication", time=now
        )
        models.Note.objects.create(
            child=self.child, note="Timeline private note", time=now
        )
        models.Temperature.objects.create(child=self.child, temperature=38.9, time=now)
        models.TummyTime.objects.create(
            child=self.child, start=now, end=now + timezone.timedelta(minutes=5)
        )
        models.Feeding.objects.create(
            child=self.child,
            start=now,
            end=now + timezone.timedelta(minutes=10),
            type="formula",
            method="bottle",
            amount=100,
        )
        self.c = HttpClient()
        self.url = "/children/{}/".format(self.child.slug)

    def _login(self, username, codenames=None, read_only=False):
        user = get_user_model().objects.create_user(
            username=username, password="password", is_active=True
        )
        if read_only:
            # The `read_only` group holds `view` on every core model. The
            # permissions are granted to the user directly, rather than by
            # looking the group up, so this keeps working whether or not the
            # group has been populated.
            codenames = tuple(
                Permission.objects.filter(
                    content_type__app_label="core", codename__startswith="view_"
                ).values_list("codename", flat=True)
            )
        if codenames:
            user.user_permissions.add(
                *Permission.objects.filter(
                    content_type__app_label="core", codename__in=codenames
                )
            )
        self.c.login(username=username, password="password")
        return user

    def _model_names(self, page):
        return {event.get("model_name") for event in page.context["timeline_objects"]}

    def test_timeline_excludes_models_without_permission(self):
        self._login("carer", codenames=CARE_ENTRY_PERMISSIONS)
        page = self.c.get(self.url)
        self.assertEqual(page.status_code, 200)

        model_names = self._model_names(page)
        self.assertIn("feeding", model_names)
        for excluded in ["medication", "note", "temperature", "tummytime"]:
            self.assertNotIn(excluded, model_names)

        content = page.content.decode()
        self.assertNotIn("Timeline Medication", content)
        self.assertNotIn("Timeline private note", content)

    def test_read_only_user_sees_the_whole_timeline(self):
        self._login("readonly", read_only=True)
        page = self.c.get(self.url)
        self.assertEqual(page.status_code, 200)

        model_names = self._model_names(page)
        self.assertIn("feeding", model_names)
        self.assertIn("medication", model_names)
        self.assertIn("note", model_names)

        content = page.content.decode()
        self.assertIn("Timeline Medication", content)
        self.assertIn("Timeline private note", content)


class ParentDetailPermissionsTestCase(TestCase):
    """
    The parent page only requires core.view_parent, but its pumping cards
    and the shared stash card both render pumping data, so they stay hidden
    without core.view_pumping too.
    """

    def setUp(self):
        self.parent = models.Parent.objects.create(first_name="Robin")
        self.c = HttpClient()
        self.url = "/parents/{}/".format(self.parent.slug)

    def _login(self, username, codenames):
        user = get_user_model().objects.create_user(
            username=username, password="password", is_active=True
        )
        user.user_permissions.add(
            *Permission.objects.filter(
                content_type__app_label="core", codename__in=codenames
            )
        )
        self.c.login(username=username, password="password")
        return user

    def test_view_parent_without_view_pumping_hides_pumping_and_stash_cards(self):
        self._login("viewer", ["view_parent"])
        page = self.c.get(self.url)
        self.assertEqual(page.status_code, 200)

        content = page.content.decode()
        self.assertNotIn("Last Pumping", content)
        self.assertNotIn("Recent Pumpings", content)
        self.assertNotIn("Milk stash", content)

    def test_view_parent_with_view_pumping_shows_pumping_and_stash_cards(self):
        self._login("viewer-with-pumping", ["view_parent", "view_pumping"])
        page = self.c.get(self.url)
        self.assertEqual(page.status_code, 200)

        content = page.content.decode()
        self.assertIn("Last Pumping", content)
        self.assertIn("Recent Pumpings", content)
        self.assertIn("Milk stash", content)

    def test_tables_follow_their_own_view_permissions(self):
        self._login("parent-only", ["view_parent"])
        content = self.c.get(self.url).content.decode()
        self.assertNotIn("No pumping entries found.", content)
        self.assertNotIn("No stash adjustments found.", content)

        self._login("pumping-only", ["view_parent", "view_pumping"])
        content = self.c.get(self.url).content.decode()
        self.assertIn("No pumping entries found.", content)
        self.assertNotIn("No stash adjustments found.", content)

        self._login("adjustments-only", ["view_parent", "view_stashadjustment"])
        content = self.c.get(self.url).content.decode()
        self.assertNotIn("No pumping entries found.", content)
        self.assertIn("No stash adjustments found.", content)

    def test_parent_page_breastfeeding_card(self):
        child = models.Child.objects.create(
            first_name="Sam", birth_date=timezone.localdate()
        )
        now = timezone.localtime()
        for start, end in ((25, 15), (15, 0)):
            models.Feeding.objects.create(
                child=child,
                parent=self.parent,
                start=now - timezone.timedelta(minutes=start),
                end=now - timezone.timedelta(minutes=end),
                type="breast milk",
                method="left breast",
            )
        self._login("breastfeeding-viewer", ["view_parent", "view_feeding"])
        content = self.c.get(self.url).content.decode()
        self.assertIn("2 sessions, 25 min today", content)
        self.assertIn("2 sessions, 25 min in the last 7 days", content)

    def test_parent_page_breastfeeding_card_counts_tandem_minutes_once(self):
        now = timezone.localtime()
        for name in ("Sam", "Casey"):
            child = models.Child.objects.create(
                first_name=name, birth_date=timezone.localdate()
            )
            models.Feeding.objects.create(
                child=child,
                parent=self.parent,
                start=now - timezone.timedelta(minutes=15),
                end=now,
                type="breast milk",
                method="both breasts",
            )
        self._login("tandem-viewer", ["view_parent", "view_feeding"])
        content = self.c.get(self.url).content.decode()
        self.assertIn("2 sessions, 15 min today", content)
        self.assertIn("2 sessions, 15 min in the last 7 days", content)

    def test_feeding_list_links_parent_only_with_view_parent(self):
        # Names show only when there is a choice of milk-producing parent.
        models.Parent.objects.create(first_name="Casey")
        child = models.Child.objects.create(
            first_name="Sam", birth_date=timezone.localdate()
        )
        now = timezone.localtime()
        models.Feeding.objects.create(
            child=child,
            parent=self.parent,
            start=now - timezone.timedelta(minutes=10),
            end=now,
            type="breast milk",
            method="left breast",
        )
        self._login("feeding-viewer", ["view_feeding"])
        content = self.c.get("/feedings/").content.decode()
        self.assertIn("Robin", content)
        self.assertNotIn('href="{}"'.format(self.url), content)

        self._login("feeding-and-parent-viewer", ["view_feeding", "view_parent"])
        content = self.c.get("/feedings/").content.decode()
        self.assertIn('href="{}"'.format(self.url), content)

    def test_view_parent_without_view_feeding_hides_breastfeeding_card(self):
        child = models.Child.objects.create(
            first_name="Sam", birth_date=timezone.localdate()
        )
        now = timezone.localtime()
        models.Feeding.objects.create(
            child=child,
            parent=self.parent,
            start=now - timezone.timedelta(minutes=10),
            end=now,
            type="breast milk",
            method="left breast",
        )
        self._login("no-feeding-viewer", ["view_parent"])
        content = self.c.get(self.url).content.decode()
        self.assertNotIn("Breastfeeding", content)


class StashPagesTestCase(TestCase):
    def setUp(self):
        self.robin = models.Parent.objects.create(first_name="Robin")
        self.alex = models.Child.objects.create(
            first_name="Alex", birth_date=timezone.localdate()
        )
        self.c = HttpClient()

    def _login(self, username, codenames=(), **kwargs):
        user = get_user_model().objects.create_user(
            username=username, password="password", is_active=True, **kwargs
        )
        user.user_permissions.add(
            *Permission.objects.filter(
                content_type__app_label="core", codename__in=codenames
            )
        )
        self.c.login(username=username, password="password")
        return user

    def test_adjustment_form_reason_is_a_text_input(self):
        self._login("stash-admin", is_superuser=True)
        content = self.c.get("/stash/adjustments/add/").content.decode()
        self.assertRegex(
            content, r'<input type="text" name="reason"[^>]*maxlength="255"'
        )
        self.assertNotIn("id_discard_reason", content)

    def throw_away_links(self, content):
        return re.findall(
            r'<a href="/stash/adjustments/add/\?(kind=discarded&amount=[^"]*)"'
            r"[^>]*>\s*([^<]*?)\s*</a>",
            content,
        )

    def test_throw_away_links(self):
        def added(hours_ago, amount):
            models.StashAdjustment.objects.create(
                time=timezone.localtime() - timezone.timedelta(hours=hours_ago),
                amount=amount,
                kind="added",
            )

        reason = "reason=Older%20than%2072%20h"
        dashboard = "/children/{}/dashboard/".format(self.alex.slug)
        self._login("stash-admin", is_superuser=True)
        added(1, 40)
        self.assertEqual(
            self.throw_away_links(self.c.get("/stash/").content.decode()), []
        )
        self.assertNotIn(
            "?kind=discarded&amount=", self.c.get(dashboard).content.decode()
        )

        added(100, 60)
        links = self.throw_away_links(self.c.get("/stash/").content.decode())
        self.assertEqual(
            links,
            [
                ("kind=discarded&amount=60&" + reason, "Throw away all expired milk"),
                ("kind=discarded&amount=60&" + reason, "Throw away"),
            ],
        )
        self.assertEqual(
            self.throw_away_links(self.c.get(dashboard).content.decode()),
            [("kind=discarded&amount=60&" + reason, "Throw away")],
        )

        added(90, 25.5)
        links = self.throw_away_links(self.c.get("/stash/").content.decode())
        self.assertEqual(
            links,
            [
                ("kind=discarded&amount=85.5&" + reason, "Throw away all expired milk"),
                ("kind=discarded&amount=60&" + reason, "Throw away"),
            ],
        )

        self._login("viewer", ["view_pumping", "view_child"])
        for url in ("/stash/", dashboard):
            with self.subTest(url=url):
                content = self.c.get(url).content.decode()
                self.assertIn("Milk stash", content)
                self.assertNotIn("?kind=discarded&amount=", content)

    def add_movements(self, count, hours_ago):
        for i in range(count):
            t = timezone.localtime() - timezone.timedelta(hours=hours_ago + i)
            models.Pumping.objects.create(
                parent=self.robin,
                start=t - timezone.timedelta(minutes=50),
                end=t - timezone.timedelta(minutes=40),
                amount=100,
                stash_amount=100,
            )
            models.Feeding.objects.create(
                child=self.alex,
                start=t - timezone.timedelta(minutes=30),
                end=t - timezone.timedelta(minutes=30),
                type="breast milk",
                method="bottle",
                amount=50,
                stash_amount=50,
            )
            models.StashAdjustment.objects.create(
                time=t,
                amount=10,
                kind="discarded",
                reason="Spilled",
                parent=self.robin,
            )

    def test_movements_query_count_does_not_grow_with_rows(self):
        self._login("stash-admin", is_superuser=True)
        self.add_movements(1, 1)
        self.c.get("/stash/")  # warm the settings and session caches
        with CaptureQueriesContext(connection) as one:
            self.c.get("/stash/")
        self.add_movements(3, 10)
        with CaptureQueriesContext(connection) as more:
            self.c.get("/stash/")
        self.assertEqual(len(one), len(more))

    def test_movement_links_need_change_permission(self):
        # Names show only when there is a choice of milk-producing parent.
        models.Parent.objects.create(first_name="Casey")
        self.add_movements(1, 1)
        links = [
            "/pumping/{}/".format(models.Pumping.objects.get().id),
            "/feedings/{}/".format(models.Feeding.objects.get().id),
            "/stash/adjustments/{}/".format(models.StashAdjustment.objects.get().id),
        ]
        self._login("viewer", ["view_pumping"])
        content = self.c.get("/stash/").content.decode()
        self.assertIn("Robin", content)
        self.assertIn("Alex", content)
        for link in links:
            self.assertNotIn(link, content)

        self._login(
            "editor",
            ["view_pumping", "change_pumping", "change_feeding"]
            + ["change_stashadjustment"],
        )
        content = self.c.get("/stash/").content.decode()
        for link in links:
            self.assertIn(link, content)

    def test_stash_page_child_filter(self):
        # Names show only when there is a choice of milk-producing parent.
        models.Parent.objects.create(first_name="Casey")
        sam = models.Child.objects.create(
            first_name="Sam", birth_date=timezone.localdate()
        )
        self.robin.children.add(sam)
        self.add_movements(1, 1)  # pumping + Alex bottle + adjustment, all by Robin
        models.Feeding.objects.create(
            child=sam,
            start=timezone.localtime() - timezone.timedelta(hours=2),
            end=timezone.localtime() - timezone.timedelta(hours=2),
            type="breast milk",
            method="bottle",
            amount=40,
            stash_amount=40,
        )
        self._login("viewer", ["view_pumping"])

        content = self.c.get("/stash/").content.decode()
        self.assertIn('name="child"', content)

        content = self.c.get("/stash/?child={}".format(sam.slug)).content.decode()
        self.assertIn("Bottle · Sam", content)
        self.assertNotIn("Bottle · Alex", content)
        self.assertNotIn("Pumping · Robin", content)
        self.assertNotIn("Discarded", content)

        content = self.c.get("/stash/?child={}".format(self.alex.slug)).content.decode()
        self.assertIn("Bottle · Alex", content)
        self.assertNotIn("Bottle · Sam", content)

        # An unknown slug is not an error: every movement is shown, unfiltered.
        content = self.c.get("/stash/?child=does-not-exist").content.decode()
        self.assertIn("Bottle · Alex", content)
        self.assertIn("Pumping · Robin", content)

    def test_negative_balance_warning_is_translated(self):
        user = self._login("nl", ["view_pumping"])
        user.settings.language = "nl"
        user.settings.save()
        t = timezone.localtime() - timezone.timedelta(hours=1)
        models.Feeding.objects.create(
            child=self.alex,
            start=t,
            end=t,
            type="breast milk",
            method="bottle",
            amount=50,
            stash_amount=50,
        )
        page = self.c.get("/stash/")
        self.assertContains(
            page,
            "De voorraad staat onder nul: er is meer melk uitgehaald dan er ooit in ging.",
        )

    def test_warning_hidden_when_balance_positive(self):
        self._login("viewer", ["view_pumping"])
        t = timezone.localtime() - timezone.timedelta(hours=1)
        models.StashAdjustment.objects.create(time=t, amount=50, kind="added")
        page = self.c.get("/stash/")
        self.assertNotContains(page, "core:stash-warning-dismiss")
        self.assertNotContains(page, "/stash/warning/dismiss/")

    def test_warning_shown_when_negative(self):
        self._login("viewer", ["view_pumping"])
        t = timezone.localtime() - timezone.timedelta(hours=1)
        models.Feeding.objects.create(
            child=self.alex,
            start=t,
            end=t,
            type="breast milk",
            method="bottle",
            amount=50,
            stash_amount=50,
        )
        page = self.c.get("/stash/")
        self.assertContains(page, "/stash/warning/dismiss/")
        self.assertContains(
            page,
            "The stash is below zero: more milk was taken out than was ever put in.",
        )

    def _bottle_from_stash(self, hours_ago, amount=50):
        t = timezone.localtime() - timezone.timedelta(hours=hours_ago)
        return models.Feeding.objects.create(
            child=self.alex,
            start=t,
            end=t,
            type="breast milk",
            method="bottle",
            amount=amount,
            stash_amount=amount,
        )

    def _add_to_stash(self, hours_ago, amount):
        t = timezone.localtime() - timezone.timedelta(hours=hours_ago)
        return models.StashAdjustment.objects.create(
            time=t, amount=amount, kind="added"
        )

    def test_dismiss_hides_in_this_browser_only(self):
        self._login("viewer", ["view_pumping"])
        self._bottle_from_stash(1)
        page = self.c.post("/stash/warning/dismiss/", follow=True)
        self.assertRedirects(page, "/stash/")
        self.assertNotContains(page, "/stash/warning/dismiss/")
        self.assertIn(views.STASH_WARNING_COOKIE, self.c.cookies)

        other_browser = HttpClient()
        other_browser.login(username="viewer", password="password")
        page = other_browser.get("/stash/")
        self.assertContains(page, "/stash/warning/dismiss/")

    def test_dismissal_forgotten_once_back_at_zero(self):
        self._login("viewer", ["view_pumping"])
        self._bottle_from_stash(3)
        self.c.post("/stash/warning/dismiss/")

        self._add_to_stash(2, 50)  # back at zero
        self.c.get("/stash/")
        self.assertEqual(self.c.cookies[views.STASH_WARNING_COOKIE].value, "")

        self._bottle_from_stash(1)  # below zero again
        page = self.c.get("/stash/")
        self.assertContains(page, "/stash/warning/dismiss/")

    def test_next_dip_shows_again_without_a_visit_in_between(self):
        self._login("viewer", ["view_pumping"])
        self._bottle_from_stash(3)
        self.c.post("/stash/warning/dismiss/")
        self.assertNotContains(self.c.get("/stash/"), "/stash/warning/dismiss/")

        self._add_to_stash(2, 50)
        self._bottle_from_stash(1)
        page = self.c.get("/stash/")
        self.assertContains(page, "/stash/warning/dismiss/")

    def test_parent_pickers_show_the_adult_placeholder(self):
        self._login("stash-admin", is_superuser=True)
        models.Parent.objects.create(first_name="Casey")
        for path in ("/pumping/add/", "/stash/adjustments/add/"):
            with self.subTest(path=path):
                content = self.c.get(path).content.decode()
                self.assertIn("parent-placeholder", content)
                self.assertNotIn("child-placeholder", content)

    def test_one_milk_parent_is_never_named(self):
        self._login("stash-admin", is_superuser=True)
        models.Parent.objects.create(first_name="Sam", produces_milk=False)
        t = timezone.localtime() - timezone.timedelta(hours=2)
        models.Pumping.objects.create(
            parent=self.robin, start=t, end=t, amount=60, stash_amount=60
        )
        content = self.c.get("/stash/").content.decode()
        self.assertNotIn("Pumping · Robin", content)
        self.assertNotIn("<td>Robin</td>", content)
        form = self.c.get("/stash/adjustments/add/").context["form"]
        self.assertTrue(form.fields["parent"].widget.is_hidden)
        self.assertEqual(list(form.fields["parent"].queryset), [self.robin])

    def test_lots_show_whose_milk_and_throw_away_takes_that_lot(self):
        self._login("stash-admin", is_superuser=True)
        robin = self.robin
        models.Parent.objects.create(first_name="Casey")
        t = timezone.localtime() - timezone.timedelta(hours=80)
        models.Pumping.objects.create(
            parent=robin, start=t, end=t, amount=60, stash_amount=60
        )
        content = self.c.get("/stash/").content.decode()
        self.assertIn("<td>Robin</td>", content)
        self.assertIn("&parent={}".format(robin.slug), content)

    def test_menu_has_one_stash_entry_and_page_links_the_list(self):
        self._login("stash-admin", is_superuser=True)
        content = self.c.get("/stash/").content.decode()
        self.assertEqual(content.count('href="/stash/"'), 1)
        self.assertIn('href="/stash/adjustments/"', content)
        self.assertIn('href="/stash/adjustments/add/"', content)

    def test_dismiss_requires_post(self):
        self._login("viewer", ["view_pumping"])
        page = self.c.get("/stash/warning/dismiss/")
        self.assertEqual(page.status_code, 405)

    def test_legacy_banner_counts_and_explains(self):
        user = self._login("stash-admin", is_superuser=True)
        t = timezone.localtime() - timezone.timedelta(hours=3)
        legacy = dict(
            child=self.alex, start=t, end=t + timezone.timedelta(minutes=5), amount=9
        )
        models.Pumping.objects.create(**legacy)
        page = self.c.get("/pumping/")
        self.assertContains(page, "1 older pumping entry is not linked to a parent")
        self.assertContains(page, "link_pumping_to_parents")
        legacy["start"] -= timezone.timedelta(hours=1)
        legacy["end"] -= timezone.timedelta(hours=1)
        models.Pumping.objects.create(**legacy)
        page = self.c.get("/pumping/")
        self.assertContains(page, "2 older pumping entries are not linked")
        user.settings.language = "nl"
        user.settings.save()
        page = self.c.get("/pumping/")
        self.assertContains(
            page, "2 oudere kolfregistraties zijn nog niet aan een ouder gekoppeld."
        )
