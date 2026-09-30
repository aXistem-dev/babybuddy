# -*- coding: utf-8 -*-
import datetime

from django.core.exceptions import ValidationError
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.core.management import call_command
from django.db.models import ProtectedError
from django.test import TestCase
from django.utils import timezone

from core import models


class BMITestCase(TestCase):
    def setUp(self):
        call_command("migrate", verbosity=0)
        self.child = models.Child.objects.create(
            first_name="First", last_name="Last", birth_date=timezone.localdate()
        )
        self.bmi = models.BMI.objects.create(
            child=self.child,
            date=timezone.localdate(),
            bmi=63.2,
        )

    def test_weight_create(self):
        self.assertEqual(self.bmi, models.BMI.objects.first())
        self.assertEqual(str(self.bmi), "BMI")
        self.assertEqual(self.bmi.bmi, 63.2)


class ChildTestCase(TestCase):
    def setUp(self):
        call_command("migrate", verbosity=0)

    def test_child_create(self):
        child = models.Child.objects.create(
            first_name="First", last_name="Last", birth_date=timezone.localdate()
        )
        self.assertEqual(child, models.Child.objects.get(first_name="First"))
        self.assertEqual(child.slug, "first-last")
        self.assertEqual(str(child), "First Last")
        self.assertEqual(child.name(), "First Last")
        self.assertEqual(child.name(reverse=True), "Last, First")

    def test_child_due_date_optional(self):
        # Due date is optional and defaults to None.
        child = models.Child.objects.create(
            first_name="No", last_name="Duedate", birth_date=timezone.localdate()
        )
        self.assertIsNone(child.due_date)

    def test_child_due_date_stored(self):
        birth_date = datetime.date(2025, 6, 1)
        due_date = datetime.date(2025, 6, 24)
        child = models.Child.objects.create(
            first_name="Preterm",
            last_name="Child",
            birth_date=birth_date,
            due_date=due_date,
        )
        child.refresh_from_db()
        self.assertEqual(child.due_date, due_date)

    def test_child_create_without_last_name(self):
        child = models.Child.objects.create(
            first_name="Nolastname", birth_date=timezone.localdate()
        )
        self.assertEqual(child, models.Child.objects.get(first_name="Nolastname"))
        self.assertEqual(child.slug, "nolastname")
        self.assertEqual(str(child), "Nolastname")
        self.assertEqual(child.name(), "Nolastname")
        self.assertEqual(child.name(reverse=True), "Nolastname")

    def test_child_count(self):
        self.assertEqual(models.Child.count(), 0)
        models.Child.objects.create(
            first_name="First 1", last_name="Last 1", birth_date=timezone.localdate()
        )
        self.assertEqual(models.Child.count(), 1)
        child = models.Child.objects.create(
            first_name="First 2", last_name="Last 2", birth_date=timezone.localdate()
        )
        self.assertEqual(models.Child.count(), 2)
        child.delete()
        self.assertEqual(models.Child.count(), 1)

    def test_child_birth_datetime(self):
        birth_date = timezone.localdate()
        models.Child.objects.create(
            first_name="First", last_name="Last", birth_date=birth_date
        )
        self.assertEqual(models.Child.objects.last().birth_datetime(), birth_date)
        birth_time = datetime.datetime.now().time()
        models.Child.objects.create(
            first_name="Second",
            last_name="Last",
            birth_date=birth_date,
            birth_time=birth_time,
        )
        self.assertEqual(
            models.Child.objects.last().birth_datetime(),
            timezone.make_aware(datetime.datetime.combine(birth_date, birth_time)),
        )


class DiaperChangeTestCase(TestCase):
    def setUp(self):
        call_command("migrate", verbosity=0)
        self.child = models.Child.objects.create(
            first_name="First", last_name="Last", birth_date=timezone.localdate()
        )
        self.change = models.DiaperChange.objects.create(
            child=self.child,
            time=timezone.localtime() - timezone.timedelta(days=1),
            wet=1,
            solid=1,
            color="black",
            amount=1.25,
        )

    def test_diaperchange_create(self):
        self.assertEqual(self.change, models.DiaperChange.objects.first())
        self.assertEqual(str(self.change), "Diaper Change")
        self.assertEqual(self.change.child, self.child)
        self.assertTrue(self.change.wet)
        self.assertTrue(self.change.solid)
        self.assertEqual(self.change.color, "black")
        self.assertEqual(self.change.amount, 1.25)

    def test_diaperchange_attributes(self):
        self.assertListEqual(self.change.attributes(), ["Wet", "Solid", "Black"])

    def test_diaperchange_color_choices(self):
        colors = [
            choice[0] for choice in models.DiaperChange._meta.get_field("color").choices
        ]
        # Create a fresh child so the setUp fixture's DiaperChange doesn't
        # interfere with the count.
        child = models.Child.objects.create(
            first_name="Color", last_name="Test", birth_date=timezone.localdate()
        )
        for color in colors:
            models.DiaperChange.objects.create(
                child=child,
                time=timezone.localtime(),
                wet=False,
                solid=False,
                color=color,
            )
        self.assertEqual(
            models.DiaperChange.objects.filter(child=child).count(), len(colors)
        )


class FeedingTestCase(TestCase):
    def setUp(self):
        call_command("migrate", verbosity=0)
        self.child = models.Child.objects.create(
            first_name="First", last_name="Last", birth_date=timezone.localdate()
        )

    def test_feeding_create(self):
        feeding = models.Feeding.objects.create(
            child=self.child,
            start=timezone.localtime() - timezone.timedelta(minutes=30),
            end=timezone.localtime(),
            type="formula",
            method="bottle",
            amount=2,
        )
        self.assertEqual(feeding, models.Feeding.objects.first())
        self.assertEqual(str(feeding), "Feeding")
        self.assertEqual(feeding.duration, feeding.end - feeding.start)

    def test_formula_and_solid_food_not_from_the_breast(self):
        start = timezone.localtime() - timezone.timedelta(minutes=30)
        for feeding_type in ("formula", "solid food"):
            for method in ("left breast", "right breast", "both breasts"):
                with self.subTest(type=feeding_type, method=method):
                    feeding = models.Feeding(
                        child=self.child,
                        start=start,
                        end=start + timezone.timedelta(minutes=10),
                        type=feeding_type,
                        method=method,
                    )
                    with self.assertRaises(ValidationError) as error:
                        feeding.full_clean()
                    self.assertIn("method", error.exception.message_dict)
        for feeding_type in ("breast milk", "fortified breast milk"):
            with self.subTest(type=feeding_type):
                models.Feeding(
                    child=self.child,
                    start=start,
                    end=start + timezone.timedelta(minutes=10),
                    type=feeding_type,
                    method="left breast",
                ).full_clean()

    def test_method_both_breasts(self):
        feeding = models.Feeding.objects.create(
            child=self.child,
            start=timezone.localtime() - timezone.timedelta(minutes=30),
            end=timezone.localtime(),
            type="breast milk",
            method="both breasts",
        )
        self.assertEqual(feeding, models.Feeding.objects.first())
        self.assertEqual(str(feeding), "Feeding")
        self.assertEqual(feeding.method, "both breasts")


class FeedingParentTestCase(TestCase):
    def setUp(self):
        call_command("migrate", verbosity=0)
        self.child = models.Child.objects.create(
            first_name="Alex", birth_date=timezone.localdate()
        )
        self.robin = models.Parent.objects.create(first_name="Robin")
        self.t = timezone.localtime() - timezone.timedelta(hours=1)

    def test_parent_only_for_breast_methods(self):
        f = models.Feeding(
            child=self.child,
            start=self.t,
            end=self.t + timezone.timedelta(minutes=10),
            type="breast milk",
            method="left breast",
            parent=self.robin,
        )
        f.full_clean()
        f.method = "bottle"
        with self.assertRaises(ValidationError):
            f.full_clean()


class HeadCircumferenceTestCase(TestCase):
    def setUp(self):
        call_command("migrate", verbosity=0)
        self.child = models.Child.objects.create(
            first_name="First", last_name="Last", birth_date=timezone.localdate()
        )
        self.hc = models.HeadCircumference.objects.create(
            child=self.child,
            date=timezone.localdate(),
            head_circumference=13.25,
        )

    def test_weight_create(self):
        self.assertEqual(self.hc, models.HeadCircumference.objects.first())
        self.assertEqual(str(self.hc), "Head Circumference")
        self.assertEqual(self.hc.head_circumference, 13.25)


class HeightTestCase(TestCase):
    def setUp(self):
        call_command("migrate", verbosity=0)
        self.child = models.Child.objects.create(
            first_name="First", last_name="Last", birth_date=timezone.localdate()
        )
        self.height = models.Height.objects.create(
            child=self.child,
            date=timezone.localdate(),
            height=34.5,
        )

    def test_weight_create(self):
        self.assertEqual(self.height, models.Height.objects.first())
        self.assertEqual(str(self.height), "Height")
        self.assertEqual(self.height.height, 34.5)


class NoteTestCase(TestCase):
    def setUp(self):
        call_command("migrate", verbosity=0)
        self.child = models.Child.objects.create(
            first_name="First", last_name="Last", birth_date=timezone.localdate()
        )

    def test_note_create(self):
        note = models.Note.objects.create(
            child=self.child, note="Note", time=timezone.localtime()
        )
        self.assertEqual(note, models.Note.objects.first())
        self.assertEqual(str(note), "Note")


class PumpingTestCase(TestCase):
    def setUp(self):
        call_command("migrate", verbosity=0)
        self.child = models.Child.objects.create(
            first_name="First", last_name="Last", birth_date=timezone.localdate()
        )
        start = timezone.localtime() - timezone.timedelta(days=1)
        end = start + timezone.timedelta(minutes=14)
        self.pumping = models.Pumping.objects.create(
            child=self.child,
            start=start,
            end=end,
            amount=98.6,
        )

    def test_pumping_create(self):
        self.assertEqual(self.pumping, models.Pumping.objects.first())
        self.assertEqual(str(self.pumping), "Pumping")
        self.assertEqual(self.pumping.amount, 98.6)


class SleepTestCase(TestCase):
    def setUp(self):
        call_command("migrate", verbosity=0)
        self.child = models.Child.objects.create(
            first_name="First", last_name="Last", birth_date=timezone.localdate()
        )

    def test_sleep_create(self):
        sleep = models.Sleep.objects.create(
            child=self.child,
            start=timezone.localtime() - timezone.timedelta(minutes=30),
            end=timezone.localtime(),
        )
        self.assertEqual(sleep, models.Sleep.objects.first())
        self.assertEqual(str(sleep), "Sleep")
        self.assertEqual(sleep.duration, sleep.end - sleep.start)

    def test_sleep_nap(self):
        models.Sleep.settings.nap_start_min = datetime.time(0, 0, 0)
        models.Sleep.settings.nap_start_max = datetime.time(23, 59, 59)
        sleep = models.Sleep.objects.create(
            child=self.child,
            start=timezone.now(),
            end=(timezone.now() + timezone.timedelta(hours=2)),
        )
        self.assertTrue(sleep.nap)

    def test_sleep_not_nap(self):
        models.Sleep.settings.nap_start_min = datetime.time(0, 0, 0)
        models.Sleep.settings.nap_start_max = datetime.time(0, 0, 0)
        sleep = models.Sleep.objects.create(
            child=self.child,
            start=timezone.now(),
            end=(timezone.now() + timezone.timedelta(hours=8)),
        )
        self.assertFalse(sleep.nap)

        sleep = models.Sleep.objects.create(
            child=self.child,
            start=timezone.now(),
            end=(timezone.now() + timezone.timedelta(hours=8)),
            nap=True,
        )
        self.assertTrue(sleep.nap)


class TagTestCase(TestCase):
    def setUp(self):
        call_command("migrate", verbosity=0)
        self.child = models.Child.objects.create(
            first_name="First", last_name="Last", birth_date=timezone.localdate()
        )

    def test_create_tag(self):
        tag1 = models.Tag.objects.create(name="Tag 1")
        self.assertEqual(tag1, models.Tag.objects.first())

        tag2 = models.Tag.objects.create(name="Tag 2")
        self.assertEqual(tag2, models.Tag.objects.filter(name="Tag 2").get())

    def test_tag_complementary_color(self):
        light_tag = models.Tag.objects.create(name="Light Tag", color="#ffffff")
        self.assertEqual(light_tag.complementary_color, models.Tag.DARK_COLOR)

        dark_tag = models.Tag.objects.create(name="Dark Tag", color="#000000")
        self.assertEqual(dark_tag.complementary_color, models.Tag.LIGHT_COLOR)

    def test_model_tagging(self):
        temp = models.Temperature.objects.create(
            child=self.child,
            time=timezone.localtime() - timezone.timedelta(days=1),
            temperature=98.6,
        )
        temp.tags.add("Tag 1")
        self.assertEqual(
            temp.tags.all().get(), models.Tag.objects.filter(name="Tag 1").get()
        )


class TemperatureTestCase(TestCase):
    def setUp(self):
        call_command("migrate", verbosity=0)
        self.child = models.Child.objects.create(
            first_name="First", last_name="Last", birth_date=timezone.localdate()
        )
        self.temp = models.Temperature.objects.create(
            child=self.child,
            time=timezone.localtime() - timezone.timedelta(days=1),
            temperature=98.6,
        )

    def test_temperature_create(self):
        self.assertEqual(self.temp, models.Temperature.objects.first())
        self.assertEqual(str(self.temp), "Temperature")
        self.assertEqual(self.temp.temperature, 98.6)


class TimerTestCase(TestCase):
    def setUp(self):
        call_command("migrate", verbosity=0)
        child = models.Child.objects.create(
            first_name="First", last_name="Last", birth_date=timezone.localdate()
        )
        self.user = get_user_model().objects.first()
        self.named = models.Timer.objects.create(
            name="Named", user=self.user, child=child
        )
        self.unnamed = models.Timer.objects.create(user=self.user)

    def test_timer_create(self):
        self.assertEqual(self.named, models.Timer.objects.get(name="Named"))
        self.assertEqual(str(self.named), "Named")
        self.assertEqual(self.unnamed, models.Timer.objects.get(name=None))
        self.assertEqual(str(self.unnamed), "Timer #{}".format(self.unnamed.id))

    def test_timer_title_with_child(self):
        self.assertEqual(self.named.title_with_child, str(self.named))

        models.Child.objects.create(
            first_name="Child", last_name="Two", birth_date=timezone.localdate()
        )
        self.assertEqual(
            self.named.title_with_child,
            "{} ({})".format(str(self.named), str(self.named.child)),
        )

    def test_timer_user_username(self):
        self.assertEqual(self.named.user_username, self.user.get_username())
        self.user.first_name = "User"
        self.user.last_name = "Name"
        self.user.save()
        self.assertEqual(self.named.user_username, self.user.get_full_name())

    def test_timer_restart(self):
        self.named.restart()
        self.assertGreaterEqual(timezone.localtime(), self.named.start)

    def test_timer_duration(self):
        timer = models.Timer.objects.create(user=get_user_model().objects.first())
        timer.start = timezone.localtime() - timezone.timedelta(minutes=30)
        timer.save()
        timer.refresh_from_db()

        self.assertEqual(
            timer.duration().seconds, timezone.timedelta(minutes=30).seconds
        )


class TummyTimeTestCase(TestCase):
    def setUp(self):
        call_command("migrate", verbosity=0)
        self.child = models.Child.objects.create(
            first_name="First", last_name="Last", birth_date=timezone.localdate()
        )

    def test_tummytime_create(self):
        tummy_time = models.TummyTime.objects.create(
            child=self.child,
            start=timezone.localtime() - timezone.timedelta(minutes=30),
            end=timezone.localtime(),
        )
        self.assertEqual(tummy_time, models.TummyTime.objects.first())
        self.assertEqual(str(tummy_time), "Tummy Time")
        self.assertEqual(tummy_time.duration, tummy_time.end - tummy_time.start)


class WeightTestCase(TestCase):
    def setUp(self):
        call_command("migrate", verbosity=0)
        self.child = models.Child.objects.create(
            first_name="First", last_name="Last", birth_date=timezone.localdate()
        )
        self.weight = models.Weight.objects.create(
            child=self.child,
            date=timezone.localdate(),
            weight=23,
        )

    def test_weight_create(self):
        self.assertEqual(self.weight, models.Weight.objects.first())
        self.assertEqual(str(self.weight), "Weight")
        self.assertEqual(self.weight.weight, 23)


class MedicationTestCase(TestCase):
    def setUp(self):
        call_command("migrate", verbosity=0)
        self.child = models.Child.objects.create(
            first_name="First", last_name="Last", birth_date=timezone.localdate()
        )
        self.medication = models.Medication.objects.create(
            child=self.child,
            name="Tylenol",
            dosage=5.0,
            dosage_unit="ml",
            time=timezone.localtime() - timezone.timedelta(hours=1),
            next_dose_interval=timezone.timedelta(hours=4),
        )

    def test_medication_create(self):
        self.assertEqual(self.medication, models.Medication.objects.first())
        self.assertEqual(str(self.medication), "Medication")
        self.assertEqual(self.medication.name, "Tylenol")
        self.assertEqual(self.medication.dosage, 5.0)
        self.assertEqual(self.medication.dosage_unit, "ml")

    def test_medication_with_interval(self):
        self.assertEqual(
            self.medication.next_dose_interval, timezone.timedelta(hours=4)
        )

    def test_medication_without_dosage(self):
        # Dosage is optional
        medication = models.Medication.objects.create(
            child=self.child,
            name="Vitamin D",
            time=timezone.localtime(),
        )
        self.assertIsNone(medication.dosage)
        self.assertEqual(medication.dosage_unit, "")

    def test_medication_with_tags(self):
        self.medication.tags.add("fever", "morning")
        self.assertEqual(self.medication.tags.count(), 2)
        self.assertTrue(self.medication.tags.filter(name="fever").exists())

    def test_medication_validation_future_time(self):
        from django.core.exceptions import ValidationError

        future_time = timezone.localtime() + timezone.timedelta(hours=1)
        medication = models.Medication(
            child=self.child,
            name="Future Medication",
            dosage=5.0,
            dosage_unit="ml",
            time=future_time,
        )
        with self.assertRaises(ValidationError):
            medication.full_clean()


class ParentTestCase(TestCase):
    def setUp(self):
        call_command("migrate", verbosity=0)
        self.alex = models.Child.objects.create(
            first_name="Alex", birth_date=timezone.localdate()
        )
        self.sam = models.Child.objects.create(
            first_name="Sam", birth_date=timezone.localdate()
        )

    def test_parent_create_and_slug(self):
        parent = models.Parent.objects.create(first_name="Jamie", last_name="Doe")
        self.assertEqual(str(parent), "Jamie Doe")
        self.assertEqual(parent.slug, "jamie-doe")

    def test_children_link_both_ways(self):
        robin = models.Parent.objects.create(first_name="Robin")
        robin.children.add(self.alex, self.sam)
        self.assertEqual(set(self.alex.parents.all()), {robin})

    def test_parent_for_child(self):
        self.assertIsNone(models.parent_for_child(self.alex))
        robin = models.Parent.objects.create(first_name="Robin")
        robin.children.add(self.alex)
        self.assertEqual(models.parent_for_child(self.alex), robin)
        casey = models.Parent.objects.create(first_name="Casey")
        casey.children.add(self.alex)
        self.assertIsNone(models.parent_for_child(self.alex))  # ambiguous
        self.assertIsNone(models.parent_for_child(None))


class ParentPumpingTestCase(TestCase):
    def setUp(self):
        call_command("migrate", verbosity=0)
        self.robin = models.Parent.objects.create(first_name="Robin")
        self.start = timezone.localtime() - timezone.timedelta(hours=3)
        self.end = self.start + timezone.timedelta(minutes=20)

    def make(self, **kwargs):
        data = {"start": self.start, "end": self.end, "amount": 120.0}
        data.update(kwargs)
        return models.Pumping(**data)

    def test_parent_pumping_is_valid(self):
        p = self.make(parent=self.robin)
        p.full_clean()
        p.save()
        self.assertIsNone(p.child)
        self.assertEqual(list(self.robin.pumping.all()), [p])

    def test_parent_is_required(self):
        child = models.Child.objects.create(
            first_name="Alex", birth_date=timezone.localdate()
        )
        with self.assertRaises(ValidationError):
            self.make(child=child).full_clean()

    def test_legacy_child_only_pumping_stays_valid_once_saved(self):
        # A pre-existing (already saved) child-only row keeps passing
        # full_clean() without a parent, so an unrelated edit to it doesn't
        # force a migration to the parent model.
        child = models.Child.objects.create(
            first_name="Alex", birth_date=timezone.localdate()
        )
        legacy = self.make(child=child)
        legacy.save()  # bypasses clean(), as a pre-parent-model row would
        legacy.full_clean()

    def test_stash_amount_bounds(self):
        self.make(parent=self.robin, stash_amount=120.0).full_clean()
        self.make(parent=self.robin, stash_amount=60.0).full_clean()
        for bad in (0.0, -5.0, 120.5):
            with self.assertRaises(ValidationError):
                self.make(parent=self.robin, stash_amount=bad).full_clean()

    def test_parent_sessions_may_not_overlap(self):
        self.make(parent=self.robin).save()
        clash = self.make(
            parent=self.robin,
            start=self.start + timezone.timedelta(minutes=5),
            end=self.end + timezone.timedelta(minutes=5),
        )
        with self.assertRaises(ValidationError):
            clash.full_clean()

    def test_legacy_rows_only_overlap_within_their_child(self):
        alex, sam = (
            models.Child.objects.create(
                first_name=name, birth_date=timezone.localdate()
            )
            for name in ("Alex", "Sam")
        )
        self.make(child=alex).save()
        legacy = self.make(child=sam)
        legacy.save()
        legacy.full_clean()
        clash = self.make(child=sam)
        clash.save()
        with self.assertRaises(ValidationError):
            clash.full_clean()

    def test_delete_parent_with_pumping_is_protected(self):
        self.make(parent=self.robin).save()
        with self.assertRaises(ProtectedError):
            self.robin.delete()


class FeedingStashTestCase(TestCase):
    def setUp(self):
        call_command("migrate", verbosity=0)
        self.child = models.Child.objects.create(
            first_name="Sam", birth_date=timezone.localdate()
        )
        self.t = timezone.localtime() - timezone.timedelta(hours=1)

    def feeding(self, **kwargs):
        data = dict(
            child=self.child,
            start=self.t,
            end=self.t,
            type="breast milk",
            method="bottle",
            amount=60.0,
        )
        data.update(kwargs)
        return models.Feeding(**data)

    def test_breast_milk_bottle_may_use_stash(self):
        self.feeding(stash_amount=60.0).full_clean()
        self.feeding(type="fortified breast milk", stash_amount=40.0).full_clean()

    def test_parent_fed_and_self_fed_breast_milk_may_use_stash(self):
        self.feeding(method="parent fed", stash_amount=60.0).full_clean()
        self.feeding(method="self fed", stash_amount=60.0).full_clean()

    def test_stash_amount_rejected_for_formula(self):
        with self.assertRaises(ValidationError):
            self.feeding(type="formula", stash_amount=60.0).full_clean()

    def test_stash_amount_rejected_for_breastfeeding(self):
        with self.assertRaises(ValidationError):
            self.feeding(method="both breasts", stash_amount=60.0).full_clean()

    def test_stash_amount_bounds(self):
        for bad in (0.0, 61.0):
            with self.assertRaises(ValidationError):
                self.feeding(stash_amount=bad).full_clean()

    def test_linked_discard_roundtrip(self):
        f = self.feeding(stash_amount=60.0)
        f.save()
        f.set_linked_discard(15.0, "Spilled")
        self.assertEqual(f.linked_discard().amount, 15.0)
        adj = f.stash_adjustments.get()
        self.assertEqual(
            (adj.time, adj.signed_amount, adj.reason),
            (f.start, -15.0, "Spilled"),
        )
        f.set_linked_discard(20.0, "Left over")
        updated = f.stash_adjustments.get()
        self.assertEqual(updated.amount, 20.0)  # updated, not duplicated
        self.assertEqual(updated.reason, "Left over")
        f.set_linked_discard(None)
        self.assertFalse(f.stash_adjustments.exists())

    def test_feeding_delete_cascades_adjustments(self):
        f = self.feeding(stash_amount=60.0)
        f.save()
        f.set_linked_discard(10.0, "Left over")
        f.delete()
        self.assertFalse(models.StashAdjustment.objects.exists())

    def test_linked_discard_falls_back_to_single_parent(self):
        # self.child has no linked parent, so parent_for_child() can't
        # resolve one; with exactly one Parent in the system, the discard
        # still goes to them, same as a manual entry would.
        robin = models.Parent.objects.create(first_name="Robin")
        f = self.feeding(stash_amount=60.0)
        f.save()
        f.set_linked_discard(15.0, "Spilled")
        self.assertEqual(f.linked_discard().parent, robin)


class StashAdjustmentKindsTestCase(TestCase):
    def setUp(self):
        call_command("migrate", verbosity=0)
        self.child = models.Child.objects.create(
            first_name="Alex", birth_date=timezone.localdate()
        )
        self.t = timezone.localtime() - timezone.timedelta(hours=1)

    def test_signed_amounts_and_str(self):
        added = models.StashAdjustment.objects.create(
            time=self.t, amount=250, kind="added"
        )
        gone = models.StashAdjustment.objects.create(
            time=self.t, amount=20, kind="discarded", reason="Spilled"
        )
        plain = models.StashAdjustment.objects.create(
            time=self.t, amount=20, kind="discarded"
        )
        self.assertEqual((added.signed_amount, gone.signed_amount), (250, -20))
        self.assertEqual(str(gone), "Discarded: 20.0 (Spilled)")
        self.assertEqual(str(plain), "Discarded: 20.0")
        self.assertEqual(str(added), "Added: 250.0")

    def test_amount_must_be_positive(self):
        a = models.StashAdjustment(time=self.t, amount=-10, kind="discarded")
        with self.assertRaises(ValidationError):
            a.full_clean()

    def test_reason_free_text_both_kinds(self):
        models.StashAdjustment(
            time=self.t, amount=10, kind="added", reason="Donor milk"
        ).full_clean()
        models.StashAdjustment(
            time=self.t, amount=10, kind="discarded", reason="Spilled"
        ).full_clean()
        models.StashAdjustment(
            time=self.t, amount=10, kind="discarded"
        ).full_clean()  # reason optional
        with self.assertRaises(ValidationError) as error:
            models.StashAdjustment(
                time=self.t, amount=10, kind="discarded", reason="x" * 256
            ).full_clean()
        self.assertIn("reason", error.exception.message_dict)

    def make_feeding(self, **kwargs):
        data = dict(
            child=self.child,
            start=self.t,
            end=self.t,
            type="breast milk",
            method="bottle",
            amount=60.0,
        )
        data.update(kwargs)
        feeding = models.Feeding(**data)
        feeding.save()
        return feeding

    def test_linked_feeding_without_stash_amount_is_invalid(self):
        feeding = self.make_feeding(stash_amount=None)
        a = models.StashAdjustment(
            time=feeding.start, amount=10, kind="discarded", feeding=feeding
        )
        with self.assertRaises(ValidationError):
            a.full_clean()

    def test_one_discard_per_feeding(self):
        f = self.make_feeding(stash_amount=60)
        f.set_linked_discard(15, "Left over")
        self.assertEqual(
            (f.linked_discard().amount, f.linked_discard().reason),
            (15, "Left over"),
        )
        f.set_linked_discard(20, "Spilled")
        self.assertEqual(f.stash_adjustments.count(), 1)
        dup = models.StashAdjustment(time=self.t, amount=5, kind="discarded", feeding=f)
        with self.assertRaises(ValidationError):
            dup.full_clean()
        f.set_linked_discard(None)
        self.assertFalse(f.stash_adjustments.exists())

    def test_added_cannot_link_a_feeding(self):
        f = self.make_feeding(stash_amount=60)
        with self.assertRaises(ValidationError):
            models.StashAdjustment(
                time=self.t, amount=5, kind="added", feeding=f
            ).full_clean()

    def test_updating_existing_linked_adjustment_is_valid(self):
        feeding = self.make_feeding(stash_amount=60.0)
        adjustment = models.StashAdjustment.objects.create(
            time=feeding.start, amount=10, kind="discarded", feeding=feeding
        )
        adjustment.amount = 20
        adjustment.full_clean()  # excludes itself from the duplicate check


class StashSettingsTestCase(TestCase):
    def setUp(self):
        call_command("migrate", verbosity=0)

    def test_defaults(self):
        s = models.Pumping.stash_settings
        self.assertTrue(s.pumping_to_stash_default)
        self.assertTrue(s.bottle_from_stash_default)
        self.assertEqual((s.stash_warn_age_hours, s.stash_max_age_hours), (48, 72))
