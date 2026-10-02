# -*- coding: utf-8 -*-
import datetime

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.core.management import call_command
from django.db.models import ProtectedError
from django.test import SimpleTestCase, TestCase
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


class EventTestCase(TestCase):
    def setUp(self):
        call_command("migrate", verbosity=0)
        self.child = models.Child.objects.create(
            first_name="First", last_name="Last", birth_date=timezone.localdate()
        )
        self.event_type = models.EventType.objects.create(name="Tooth brushing")

    def test_event_create(self):
        event = models.Event.objects.create(
            child=self.child,
            type=self.event_type,
            time=timezone.localtime() - timezone.timedelta(hours=1),
            notes="Soft brush.",
        )
        self.assertEqual(event, models.Event.objects.first())
        self.assertEqual(str(event), "Event")
        self.assertEqual(event.child, self.child)
        self.assertEqual(event.type, self.event_type)
        self.assertEqual(list(self.child.events.all()), [event])
        self.assertEqual(list(self.event_type.events.all()), [event])

    def test_event_time_defaults_to_now(self):
        before = timezone.now()
        event = models.Event.objects.create(child=self.child, type=self.event_type)
        self.assertGreaterEqual(event.time, before)
        self.assertLessEqual(event.time, timezone.now())

    def test_event_time_can_not_be_in_the_future(self):
        event = models.Event(
            child=self.child,
            type=self.event_type,
            time=timezone.localtime() + timezone.timedelta(hours=1),
        )
        with self.assertRaises(ValidationError) as context:
            event.clean()
        self.assertIn("time", context.exception.message_dict)

    def test_event_type_in_use_is_protected(self):
        models.Event.objects.create(child=self.child, type=self.event_type)
        with self.assertRaises(ProtectedError):
            self.event_type.delete()
        self.assertTrue(models.EventType.objects.filter(pk=self.event_type.pk).exists())

    def test_events_are_deleted_with_their_child(self):
        models.Event.objects.create(child=self.child, type=self.event_type)
        self.child.delete()
        self.assertEqual(models.Event.objects.count(), 0)
        self.assertTrue(models.EventType.objects.filter(pk=self.event_type.pk).exists())


class EventTypeTestCase(TestCase):
    def setUp(self):
        call_command("migrate", verbosity=0)

    def test_event_type_create(self):
        event_type = models.EventType.objects.create(name="Sunscreen")
        self.assertEqual(event_type, models.EventType.objects.first())
        self.assertEqual(str(event_type), "Sunscreen")
        self.assertEqual(event_type.slug, "sunscreen")

    def test_event_type_slug_is_kept_on_rename(self):
        event_type = models.EventType.objects.create(name="Nail trim")
        event_type.name = "Nail trim (hands)"
        event_type.full_clean()
        event_type.save()
        event_type.refresh_from_db()
        self.assertEqual(event_type.name, "Nail trim (hands)")
        self.assertEqual(event_type.slug, "nail-trim")

    def test_event_type_slug_is_kept_on_rename_to_a_taken_slug(self):
        models.EventType.objects.create(name="Tooth brushing")
        event_type = models.EventType.objects.create(name="Shower")
        # "Tooth brushing!" would slugify to the slug of "Tooth brushing", but
        # the slug does not change on a rename, so there is no conflict.
        event_type.name = "Tooth brushing!"
        event_type.full_clean()
        event_type.save()
        self.assertEqual(event_type.slug, "shower")

    def test_event_type_name_max_length(self):
        event_type = models.EventType(name="x" * 101)
        with self.assertRaises(ValidationError) as context:
            event_type.full_clean()
        self.assertIn("name", context.exception.message_dict)

    def test_event_type_slug_fits_its_field(self):
        # NFKC normalization can make a slug longer than the name.
        event_type = models.EventType(name="\ufb00" * 100)
        event_type.full_clean()
        event_type.save()
        self.assertEqual(event_type.slug, "ff" * 50)

    def test_event_type_ordering(self):
        models.EventType.objects.create(name="Tooth brushing")
        models.EventType.objects.create(name="nail trim")
        models.EventType.objects.create(name="Sunscreen")
        self.assertEqual(
            list(models.EventType.objects.values_list("name", flat=True)),
            ["nail trim", "Sunscreen", "Tooth brushing"],
        )

    def test_event_type_clean_rejects_a_conflicting_slug(self):
        models.EventType.objects.create(name="Tooth brushing")
        with self.assertRaises(ValidationError) as context:
            models.EventType(name="tooth brushing!").clean()
        self.assertIn("name", context.exception.message_dict)

    def test_event_type_clean_rejects_an_empty_slug(self):
        with self.assertRaises(ValidationError) as context:
            models.EventType(name="!!!").clean()
        self.assertIn("name", context.exception.message_dict)

    def test_event_type_clean_accepts_its_own_slug(self):
        event_type = models.EventType.objects.create(name="Tooth brushing")
        event_type.name = "TOOTH BRUSHING"
        try:
            event_type.full_clean()
        except ValidationError as error:
            self.fail("clean() rejected an unchanged slug: {}".format(error))
        event_type.save()
        self.assertEqual(event_type.slug, "tooth-brushing")

    def test_event_type_emoji(self):
        event_type = models.EventType.objects.create(name="Nail trim")
        self.assertEqual(event_type.emoji, "")
        self.assertEqual(event_type.display_name, "Nail trim")
        event_type.emoji = "\u2702\ufe0f"
        event_type.full_clean()
        event_type.save()
        event_type.refresh_from_db()
        self.assertEqual(event_type.emoji, "\u2702\ufe0f")
        self.assertEqual(event_type.display_name, "\u2702\ufe0f Nail trim")
        # The name alone is still what a type is shown as elsewhere.
        self.assertEqual(str(event_type), "Nail trim")

    def test_event_type_invalid_emoji(self):
        for emoji in ("nail", "\u2702\ufe0f\U0001faa5", "\U0001f642" * 17):
            with self.subTest(emoji=emoji):
                event_type = models.EventType(name="Nail trim", emoji=emoji)
                with self.assertRaises(ValidationError) as context:
                    event_type.full_clean()
                self.assertIn("emoji", context.exception.message_dict)


class ValidateEmojiTestCase(SimpleTestCase):
    def assertValid(self, value):
        try:
            models.validate_emoji(value)
        except ValidationError as error:
            self.fail("{!r} was rejected: {}".format(value, error))

    def assertInvalid(self, value):
        with self.assertRaises(ValidationError) as context:
            models.validate_emoji(value)
        self.assertEqual(context.exception.messages, ["Enter a single emoji."])

    def test_accepted(self):
        cases = {
            "empty": "",
            "plain": "\U0001f642",
            "plain (newer)": "\U0001faa5",
            "variation selector": "\u2702\ufe0f",
            "text style": "\u2702",
            "skin tone": "\U0001f44d\U0001f3fd",
            "family": "\U0001f468\u200d\U0001f469\u200d\U0001f467\u200d\U0001f466",
            "profession with skin tone": "\U0001f9d1\U0001f3fd\u200d\u2695\ufe0f",
            "flag": "\U0001f1ea\U0001f1fa",
            "keycap": "1\ufe0f\u20e3",
            "keycap hash": "#\ufe0f\u20e3",
            "subdivision flag": (
                "\U0001f3f4\U000e0067\U000e0062\U000e0073\U000e0063\U000e0074"
                "\U000e007f"
            ),
            "copyright": "\u00a9\ufe0f",
            "wavy dash": "\u3030",
            "left right arrow": "\u2194\ufe0f",
            "south west arrow": "\u2199\ufe0f",
            "arrow curving left": "\u21a9\ufe0f",
            "arrow curving right": "\u21aa",
            "circled M": "\u24c2\ufe0f",
            "small black square": "\u25aa\ufe0f",
            "small white square": "\u25ab\ufe0f",
            "play button": "\u25b6\ufe0f",
            "reverse button": "\u25c0\ufe0f",
            "white medium square": "\u25fb\ufe0f",
            "black medium small square": "\u25fe",
            "arrow curving up": "\u2934\ufe0f",
            "arrow curving down": "\u2935\ufe0f",
            "16 code points": "\u200d".join(["\U0001f468"] * 8) + "\ufe0f",
        }
        for name, value in cases.items():
            with self.subTest(name):
                self.assertValid(value)

    def test_refused(self):
        cases = {
            "two emoji": "\U0001f642\U0001f642",
            "two emoji with selectors": "\u2702\ufe0f\U0001faa5",
            "two flags": "\U0001f1ea\U0001f1fa\U0001f1ef\U0001f1f5",
            "letter": "a",
            "arrow without emoji form": "\u2190",
            "geometric shape without emoji form": "\u25a0",
            "circled letter without emoji form": "\u24b6",
            "text": "nail trim",
            "digit": "1",
            "keycap without selector": "1\u20e3",
            "space": " ",
            "emoji and space": "\U0001f642 ",
            "space and emoji": " \U0001f642",
            "newline": "\n",
            "one regional indicator": "\U0001f1ea",
            "lone skin tone": "\U0001f3fd",
            "two skin tones": "\U0001f44d\U0001f3fd\U0001f3fd",
            "two selectors": "\u2702\ufe0f\ufe0f",
            "lone joiner": "\u200d",
            "trailing joiner": "\U0001f642\u200d",
            "joined text": "\U0001f642\u200da",
            "unfinished tag sequence": "\U0001f3f4\U000e0067\U000e0062",
            "over 16 code points": "\u200d".join(["\U0001f468"] * 9),
        }
        for name, value in cases.items():
            with self.subTest(name):
                self.assertInvalid(value)


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
