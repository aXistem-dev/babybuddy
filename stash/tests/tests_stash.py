# -*- coding: utf-8 -*-
from datetime import timedelta

from django.core.exceptions import ValidationError
from django.test import TestCase
from django.utils import timezone

from core import models as core_models
from stash import models, stash


class StashTestCase(TestCase):
    def setUp(self):
        self.child = core_models.Child.objects.create(
            first_name="First", last_name="Last", birth_date=timezone.localdate()
        )
        self.now = timezone.now()

    def ago(self, hours):
        return self.now - timedelta(hours=hours)

    def pump(self, hours_ago, amount, to_stash=True):
        return core_models.Pumping.objects.create(
            child=self.child,
            start=self.ago(hours_ago) - timedelta(minutes=15),
            end=self.ago(hours_ago),
            amount=amount,
            to_stash=to_stash,
        )

    def bottle(self, hours_ago, amount, from_stash=True):
        return core_models.Feeding.objects.create(
            child=self.child,
            start=self.ago(hours_ago),
            end=self.ago(hours_ago),
            type="breast milk",
            method="bottle",
            amount=amount,
            from_stash=from_stash,
        )

    def adjust(self, hours_ago, amount, kind):
        return models.StashAdjustment.objects.create(
            time=self.ago(hours_ago), amount=amount, kind=kind
        )

    def lots(self):
        return [(lot["time"], lot["amount"]) for lot in stash.summary(self.now)["lots"]]

    def test_empty(self):
        summary = stash.summary(self.now)
        self.assertEqual(summary["balance"], 0)
        self.assertEqual(summary["status"], "ok")
        self.assertEqual(summary["expired_amount"], 0)
        self.assertEqual(summary["lots"], [])
        self.assertFalse(stash.in_use())

    def test_only_marked_entries_count(self):
        self.pump(10, 100, to_stash=False)
        self.bottle(5, 40, from_stash=False)
        self.assertEqual(stash.summary(self.now)["balance"], 0)
        self.assertFalse(stash.in_use())

    def test_oldest_milk_leaves_first(self):
        self.pump(10, 100)
        self.pump(6, 80)
        self.bottle(5, 120)
        self.adjust(4, 30, "added")
        summary = stash.summary(self.now)
        self.assertEqual(summary["balance"], 90)
        self.assertEqual(self.lots(), [(self.ago(6), 60), (self.ago(4), 30)])
        self.assertTrue(stash.in_use())

    def test_discarded_milk_is_the_oldest(self):
        self.pump(10, 100)
        self.pump(6, 80)
        self.adjust(5, 110, "discarded")
        self.assertEqual(self.lots(), [(self.ago(6), 70)])

    def test_milk_in_before_milk_out_at_the_same_time(self):
        self.adjust(5, 50, "added")
        self.bottle(5, 50)
        self.assertEqual(stash.summary(self.now)["balance"], 0)
        self.assertEqual(self.lots(), [])

    def test_shortfall_is_made_up_first(self):
        self.bottle(8, 60)
        summary = stash.summary(self.now)
        self.assertEqual(summary["balance"], -60)
        self.assertEqual(summary["lots"], [])

        self.pump(4, 100)
        summary = stash.summary(self.now)
        self.assertEqual(summary["balance"], 40)
        self.assertEqual(self.lots(), [(self.ago(4), 40)])

    def test_lots_keep_their_source(self):
        self.bottle(8, 20)
        pumping = self.pump(6, 100)
        adjustment = self.adjust(4, 30, "added")
        self.bottle(2, 90)
        self.assertEqual(
            [(lot["amount"], lot["source"]) for lot in stash.summary(self.now)["lots"]],
            [(20, {"type": "stash_adjustment", "id": adjustment.id})],
        )
        self.assertEqual(
            stash.lots(stash.movements(self.ago(3)))[0],
            [self.ago(6), 80, {"type": "pumping", "id": pumping.id}],
        )

    def test_history(self):
        pumping = self.pump(10, 100)
        added = self.adjust(8, 30, "added")
        bottle = self.bottle(6, 40)
        discarded = self.adjust(4, 10, "discarded")
        self.pump(2, 50, to_stash=False)
        self.assertEqual(
            [
                (entry["kind"], entry["amount"], entry["source"])
                for entry in stash.history(at=self.now)
            ],
            [
                ("discarded", -10, {"type": "stash_adjustment", "id": discarded.id}),
                ("bottle", -40, {"type": "feeding", "id": bottle.id}),
                ("added", 30, {"type": "stash_adjustment", "id": added.id}),
                ("pumping", 100, {"type": "pumping", "id": pumping.id}),
            ],
        )
        self.assertEqual(
            [entry["kind"] for entry in stash.history(limit=2, at=self.now)],
            ["discarded", "bottle"],
        )
        self.assertEqual(stash.history(at=self.ago(9))[0]["time"], self.ago(10))

    def test_pumping_counts_from_its_end(self):
        self.pump(1, 100)
        self.assertEqual(stash.summary(self.ago(2))["balance"], 0)
        self.assertEqual(stash.summary(self.now)["balance"], 100)

    def test_tiny_remainders_are_dropped(self):
        self.pump(10, 100)
        self.bottle(5, 99.995)
        self.assertEqual(self.lots(), [])

    def test_ages(self):
        self.pump(80, 50)  # past the 72 h limit
        self.pump(50, 40)  # past the 48 h warning
        self.pump(2, 30)
        summary = stash.summary(self.now)
        self.assertEqual(
            [lot["status"] for lot in summary["lots"]], ["expired", "warn", "ok"]
        )
        self.assertEqual(summary["status"], "expired")
        self.assertEqual(summary["expired_amount"], 50)
        self.assertEqual(
            summary["lots"][1]["warn_at"], self.ago(50) + timedelta(hours=48)
        )
        self.assertEqual(
            summary["lots"][1]["expires_at"], self.ago(50) + timedelta(hours=72)
        )

    def test_settings(self):
        settings = models.StashAdjustment.settings
        self.addCleanup(setattr, settings, "stash_warn_age_hours", 48)
        self.addCleanup(setattr, settings, "stash_max_age_hours", 72)
        models.StashAdjustment.settings.stash_warn_age_hours = 1
        models.StashAdjustment.settings.stash_max_age_hours = 3
        self.pump(2, 40)
        summary = stash.summary(self.now)
        self.assertEqual((summary["warn_age_hours"], summary["max_age_hours"]), (1, 3))
        self.assertEqual(summary["status"], "warn")

    def test_editing_an_entry_corrects_the_stash(self):
        pumping = self.pump(10, 100)
        self.bottle(5, 30)
        pumping.amount = 50
        pumping.save()
        self.assertEqual(stash.summary(self.now)["balance"], 20)
        pumping.delete()
        self.assertEqual(stash.summary(self.now)["balance"], -30)

    def test_adjustment(self):
        adjustment = self.adjust(1, 25, "discarded")
        self.assertEqual(str(adjustment), "Stored milk adjustment")
        self.assertEqual(adjustment.signed_amount, -25)
        adjustment.amount = 0
        with self.assertRaisesMessage(ValidationError, "more than zero"):
            adjustment.clean()
        adjustment.amount = 5
        adjustment.time = self.now + timedelta(hours=1)
        with self.assertRaisesMessage(ValidationError, "future"):
            adjustment.clean()

    def test_import_export(self):
        from stash.admin import StashAdjustmentImportExportResource

        adjustment = self.adjust(3, 45, "added")
        adjustment.tags.add("freezer")
        dataset = StashAdjustmentImportExportResource().export()
        models.StashAdjustment.objects.all().delete()
        result = StashAdjustmentImportExportResource().import_data(dataset)
        self.assertFalse(result.has_errors())
        imported = models.StashAdjustment.objects.get()
        self.assertEqual((imported.amount, imported.kind), (45, "added"))
