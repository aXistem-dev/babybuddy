# -*- coding: utf-8 -*-
import datetime as dt

from django.core.management import call_command
from django.test import TestCase
from django.test.utils import override_settings
from django.utils import timezone

from core import models, stash


def at(hours_ago):
    return timezone.now() - dt.timedelta(hours=hours_ago)


class StashTestCase(TestCase):
    def setUp(self):
        call_command("migrate", verbosity=0)
        self.robin = models.Parent.objects.create(first_name="Robin")
        self.alex = models.Child.objects.create(
            first_name="Alex", birth_date=timezone.localdate()
        )
        self.robin.children.add(self.alex)

    def pump(self, hours_ago, amount, stored):
        return models.Pumping.objects.create(
            parent=self.robin,
            start=at(hours_ago + 0.3),
            end=at(hours_ago),
            amount=amount,
            stash_amount=stored,
        )

    def bottle(self, hours_ago, drunk):
        return models.Feeding.objects.create(
            child=self.alex,
            start=at(hours_ago),
            end=at(hours_ago),
            type="breast milk",
            method="bottle",
            amount=drunk,
            stash_amount=drunk,
        )

    def adjust(self, hours_ago, amount, kind, reason=""):
        return models.StashAdjustment.objects.create(
            time=at(hours_ago),
            amount=amount,
            kind=kind,
            reason=reason,
        )

    def test_empty(self):
        self.assertFalse(stash.stash_has_activity())
        self.assertEqual(stash.stash_balance(), 0)
        self.assertEqual(stash.stash_summary()["status"], "ok")
        self.assertEqual(
            stash.stash_summary()["defaults"],
            {"pumping_to_stash": True, "bottle_from_stash": True},
        )

    def test_activity(self):
        models.Pumping.objects.create(
            parent=self.robin, start=at(2), end=at(1.8), amount=100
        )
        self.assertFalse(stash.stash_has_activity())  # pumped, not stored
        self.adjust(1, 10, "added")
        self.assertTrue(stash.stash_has_activity())

    def test_negative_since_marks_the_current_dip(self):
        self.assertIsNone(stash.stash_summary()["negative_since"])
        first = self.bottle(5, 30)
        self.assertEqual(stash.stash_summary()["negative_since"], first.start)
        self.bottle(4, 20)  # deeper in the same dip
        self.assertEqual(stash.stash_summary()["negative_since"], first.start)
        self.adjust(3, 50, "added")  # back at zero
        self.assertIsNone(stash.stash_summary()["negative_since"])
        second = self.bottle(2, 10)
        self.assertEqual(stash.stash_summary()["negative_since"], second.start)

    def test_balance_with_every_kind(self):
        self.pump(30, 150, 90)
        self.pump(20, 120, 120)
        f = self.bottle(10, 60)
        f.set_linked_discard(30, "Spilled")
        self.adjust(5, 30, "discarded", "Older than 72 h")
        self.adjust(4, 50, "added")
        self.assertEqual(stash.stash_balance(), 90 + 120 - 60 - 30 - 30 + 50)

    def test_fifo_uses_oldest_first(self):
        self.pump(50, 100, 100)
        self.pump(10, 80, 80)
        self.bottle(5, 100)
        self.adjust(4, 20, "discarded", "Spilled")
        lots = stash.stash_lots()
        self.assertEqual(len(lots), 1)
        self.assertAlmostEqual(lots[0].amount, 60)
        self.assertAlmostEqual(lots[0].age_hours(), 10, places=1)

    def test_status_boundaries(self):
        now = timezone.now()
        self.assertEqual(stash.lot_status(47.9, 48, 72), "ok")
        self.assertEqual(stash.lot_status(48, 48, 72), "warn")
        self.assertEqual(stash.lot_status(72, 48, 72), "expired")
        self.pump(50, 100, 100)
        summary = stash.stash_summary(at=now)
        self.assertEqual(summary["status"], "warn")
        self.assertEqual(summary["lots"][0]["status"], "warn")
        self.assertEqual(
            summary["lots"][0]["expires_at"],
            summary["lots"][0]["time"] + dt.timedelta(hours=72),
        )

    def test_spill_consumes_oldest_lot(self):
        self.pump(80, 50, 50)  # expired lot
        self.pump(10, 50, 50)
        self.assertEqual(stash.stash_summary()["status"], "expired")
        self.adjust(1, 50, "discarded", "Spilled")
        self.assertEqual(stash.stash_summary()["status"], "ok")

    def test_same_time_inflow_first(self):
        t = at(3)
        models.Pumping.objects.create(
            parent=self.robin,
            start=t - dt.timedelta(minutes=20),
            end=t,
            amount=100,
            stash_amount=100,
        )
        models.Feeding.objects.create(
            child=self.alex,
            start=t,
            end=t,
            type="breast milk",
            method="bottle",
            amount=100,
            stash_amount=100,
        )
        self.assertEqual([e.kind for e in stash.stash_events()], ["pumping", "feeding"])
        self.assertEqual(stash.stash_balance(), 0)

    def test_negative_balance(self):
        self.bottle(2, 50)
        self.assertEqual(stash.stash_balance(), -50)
        self.assertEqual(stash.stash_lots(), [])
        self.assertIsNone(stash.stash_summary()["oldest"])

    def assert_lots_match_balance(self, expected_lots):
        lots = [round(lot.amount, 2) for lot in stash.stash_lots()]
        self.assertEqual(lots, expected_lots)
        self.assertAlmostEqual(sum(lots), max(stash.stash_balance(), 0))

    def test_later_inflows_repay_a_negative_balance_first(self):
        self.bottle(5, 100)
        self.assert_lots_match_balance([])
        self.pump(4, 50, 50)
        self.assertEqual(stash.stash_balance(), -50)
        self.assert_lots_match_balance([])
        self.adjust(0, 100, "added")
        self.assertEqual(stash.stash_balance(), 50)
        self.assert_lots_match_balance([50])
        # Milk stored before the addition repays the shortfall first.
        self.pump(0.5, 30, 30)
        self.assert_lots_match_balance([80])

    def test_balance_at_point_in_time(self):
        self.pump(20, 100, 100)
        self.bottle(10, 40)
        self.assertEqual(stash.stash_balance(at=at(15)), 100)
        self.assertEqual(stash.stash_balance(), 60)

    def test_exact_age_boundaries(self):
        """Test that status uses exact (unrounded) age for classification."""
        now = timezone.now()
        # Create a lot that will be aged exactly 47.96 hours at test time
        t_47_96 = now - dt.timedelta(hours=47.96)
        models.Pumping.objects.create(
            parent=self.robin,
            start=t_47_96 - dt.timedelta(minutes=20),
            end=t_47_96,
            amount=100,
            stash_amount=100,
        )
        summary = stash.stash_summary(at=now)
        # 47.96h rounds to 48.0, but should still be "ok" since exact age < 48
        self.assertEqual(summary["lots"][0]["age_hours"], 48.0)
        self.assertEqual(summary["lots"][0]["status"], "ok")

        # Create a lot aged exactly 71.96 hours
        t_71_96 = now - dt.timedelta(hours=71.96)
        models.Pumping.objects.create(
            parent=self.robin,
            start=t_71_96 - dt.timedelta(minutes=20),
            end=t_71_96,
            amount=100,
            stash_amount=100,
        )
        summary = stash.stash_summary(at=now)
        # Find the 71.96-hour lot (it will be oldest)
        oldest_lot = summary["lots"][0]
        # 71.96h rounds to 72.0, should be "warn" since exact age >= 72 is expired
        self.assertEqual(oldest_lot["age_hours"], 72.0)
        self.assertEqual(oldest_lot["status"], "warn")

    def test_fifo_drains_and_partially_consumes_lots(self):
        """Test FIFO where one outflow fully drains oldest lot and partially
        consumes the next."""
        self.pump(40, 50, 50)  # oldest lot, 50ml
        self.pump(10, 80, 80)  # newer lot, 80ml
        # Drink 100ml: drains entire 50ml from oldest, 50ml from newer
        self.bottle(5, 100)
        lots = stash.stash_lots()
        self.assertEqual(len(lots), 1)
        self.assertAlmostEqual(lots[0].amount, 30)  # 80 - 50 = 30
        self.assertAlmostEqual(lots[0].age_hours(), 10, places=1)

    def test_stash_events_start_filter(self):
        """Test that stash_events(start=...) excludes events before start."""
        self.pump(30, 100, 100)
        self.bottle(20, 30)
        self.adjust(10, 20, "added")
        self.pump(5, 50, 50)

        # All events
        all_events = stash.stash_events()
        self.assertEqual(len(all_events), 4)

        # Events from 15 hours ago: excludes first pump and bottle
        start_time = at(15)
        filtered = stash.stash_events(start=start_time)
        self.assertEqual(len(filtered), 2)  # adjust + last pump
        kinds = [e.kind for e in filtered]
        self.assertIn("added", kinds)
        self.assertIn("pumping", kinds)

    def test_use_by_child_matches_bottle_outflow(self):
        sam = models.Child.objects.create(
            first_name="Sam", birth_date=timezone.localdate()
        )
        self.robin.children.add(sam)
        self.bottle(10, 40)  # Alex
        self.bottle(5, 20)  # Alex
        models.Feeding.objects.create(
            child=sam,
            start=at(4),
            end=at(4),
            type="breast milk",
            method="bottle",
            amount=30,
            stash_amount=30,
        )
        self.adjust(1, 15, "discarded", "Spilled")

        use = stash.stash_use_by_child()
        self.assertEqual(use[self.alex.id], 60)
        self.assertEqual(use[sam.id], 30)
        # The discard (15ml) is not attributed to any baby.
        total_bottle_outflow = sum(
            f.stash_amount
            for f in models.Feeding.objects.filter(stash_amount__isnull=False)
        )
        self.assertEqual(sum(use.values()), total_bottle_outflow)

    def test_use_by_child_start_filter(self):
        self.bottle(30, 40)
        self.bottle(5, 20)
        use = stash.stash_use_by_child(start=at(15))
        self.assertEqual(use[self.alex.id], 20)

    def test_throw_away_amount_empties_a_fractional_lot(self):
        """The pre-filled throw-away amount is built from the unrounded lot
        amount, so discarding it leaves no fractional milk behind."""
        self.pump(80, 10.125, 10.125)  # expired
        summary = stash.stash_summary()
        lot = summary["lots"][0]
        self.assertEqual(lot["amount"], 10.12)  # rounded, for display only
        self.adjust(1, lot["throw_away_amount"], "discarded", "Older than 72 h")
        self.assertEqual(stash.stash_summary()["lots"], [])

    def test_tiny_leftover_lots_are_dropped(self):
        """A lot under 0.01 ml left over by floating-point drift is treated
        as empty rather than lingering as a lot nobody can act on."""
        self.pump(80, 50, 50)
        self.adjust(1, 50 - 0.005, "discarded", "Spilled")
        self.assertEqual(stash.stash_lots(), [])
        self.assertEqual(stash.stash_summary()["lots"], [])

    @override_settings(DEBUG=True)
    def test_stash_summary_query_count(self):
        """Test that stash_summary fetches events once (3 base queries:
        Pumping, Feeding, StashAdjustment) plus stash_settings queries."""
        from django.test.utils import CaptureQueriesContext
        from django.db import connection

        self.pump(50, 100, 100)
        self.pump(20, 80, 80)
        self.bottle(10, 50)
        self.adjust(5, 30, "discarded", "Older than 72 h")

        with CaptureQueriesContext(connection) as ctx:
            summary = stash.stash_summary()

        # Check for balance and lots in result
        self.assertGreater(summary["balance"], 0)
        self.assertGreater(len(summary["lots"]), 0)
        # stash_settings (Pumping.stash_settings) may query the database
        # 3 base queries (Pumping, Feeding, StashAdjustment) +
        # up to 4 for stash_settings = max 7 queries
        query_count = len(ctx)
        self.assertLessEqual(query_count, 7, f"Expected ≤7 queries, got {query_count}")
