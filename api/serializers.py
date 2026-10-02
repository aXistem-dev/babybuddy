# -*- coding: utf-8 -*-
import secrets
from copy import deepcopy
from rest_framework import serializers
from rest_framework.exceptions import ValidationError

from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from taggit.serializers import TagListSerializerField, TaggitSerializer

from core import models, stash
from babybuddy import models as babybuddy_models
from webhooks import models as webhooks_models


class CoreModelSerializer(serializers.HyperlinkedModelSerializer):
    """
    Provide the child link (used by most core models) and run model clean()
    methods during POST operations.
    """

    child = serializers.PrimaryKeyRelatedField(queryset=models.Child.objects.all())

    def validate(self, attrs):
        # Ensure that all instance data is available for partial updates to
        # support clean methods that compare multiple fields.
        if self.partial:
            new_instance = deepcopy(self.instance)
            for attr, value in attrs.items():
                setattr(new_instance, attr, value)
        else:
            new_instance = self.Meta.model(**attrs)
        new_instance.clean()
        return attrs


class CoreModelWithDurationSerializer(CoreModelSerializer):
    """
    Specific serializer base for models with a "start" and "end" field.
    """

    child = serializers.PrimaryKeyRelatedField(
        allow_null=True,
        help_text="Required unless a Timer value is provided.",
        queryset=models.Child.objects.all(),
        required=False,
    )

    timer = serializers.PrimaryKeyRelatedField(
        allow_null=True,
        help_text="May be used in place of the Start, End, and/or Child values.",
        queryset=models.Timer.objects.all(),
        required=False,
        write_only=True,
    )

    required_fields = ("child", "start", "end")

    class Meta:
        abstract = True
        extra_kwargs = {
            "start": {
                "help_text": "Required unless a Timer value is provided.",
                "required": False,
            },
            "end": {
                "help_text": "Required unless a Timer value is provided.",
                "required": False,
            },
        }

    def validate(self, attrs):
        # Check for a special "timer" data argument that can be used in place
        # of "start" and "end" fields as well as "child" if it is set on the
        # Timer entry.
        timer = None
        if "timer" in attrs:
            # Remove the "timer" attribute (super validation would fail as it
            # is not a true field on the model).
            timer = attrs.pop("timer")
            if timer is None:
                raise ValidationError({"timer": "This field may not be null."})
            if not timer.can_be_consumed_by(self.context["request"].user):
                raise PermissionDenied("You do not have permission to consume timers.")

            if timer.child:
                attrs["child"] = timer.child

            # Overwrites values provided directly!
            attrs["start"] = timer.start
            attrs["end"] = timezone.now()

        # The "child", "start", and "end" field should all be set at this
        # point. If one is not, model validation will fail because they are
        # required fields at the model level.
        if not self.partial:
            errors = {}
            for field in self.required_fields:
                if field not in attrs or not attrs[field]:
                    errors[field] = "This field is required."
            if len(errors) > 0:
                raise ValidationError(errors)

        attrs = super().validate(attrs)

        self.timer = timer
        return attrs

    @transaction.atomic
    def save(self, **kwargs):
        timer = getattr(self, "timer", None)
        if timer is not None:
            try:
                timer = models.Timer.objects.select_for_update().get(pk=timer.pk)
            except models.Timer.DoesNotExist:
                raise ValidationError({"timer": "This timer no longer exists."})
            # The timer may have changed owner since validation.
            if not timer.can_be_consumed_by(self.context["request"].user):
                raise PermissionDenied("You do not have permission to consume timers.")
        instance = super().save(**kwargs)
        if timer is not None:
            timer.stop()
        return instance


class TaggableSerializer(TaggitSerializer, serializers.HyperlinkedModelSerializer):
    tags = TagListSerializerField(required=False)

    def validate_tags(self, tags):
        current = self.instance.tags.names() if self.instance else ()
        models.Tag.check_assignment_permissions(
            self.context["request"].user, tags, current
        )
        return tags


class BMISerializer(CoreModelSerializer, TaggableSerializer):
    class Meta:
        model = models.BMI
        fields = ("id", "child", "bmi", "date", "notes", "tags")
        extra_kwargs = {
            "core.BMI.bmi": {"label": "BMI"},
        }


def check_milk_parent(serializer, attrs):
    """Refuse a parent who doesn't produce breast milk, unless the entry
    already had that parent (an edit that leaves it unchanged)."""
    parent = attrs.get("parent")
    current = getattr(serializer.instance, "parent_id", None)
    if parent and not parent.produces_milk and parent.pk != current:
        raise ValidationError({"parent": _("This parent doesn't produce breast milk.")})


class StashDefaultsMixin:
    """Fill in a stash_amount the client did not send at all: a default on
    create, or a value that keeps following/fitting the entry on update."""

    def apply_stash_default(self, attrs):
        return attrs

    def reconcile_stash_amount(self, attrs):
        return attrs

    def _follow_or_clamp_stash_amount(self, attrs):
        """A stash-unaware update that changes `amount`: see
        core.stash.follow_or_clamp_stash_amount."""
        if "amount" in attrs:
            attrs["stash_amount"] = stash.follow_or_clamp_stash_amount(
                self.instance.stash_amount, self.instance.amount, attrs["amount"]
            )
        return attrs

    def validate(self, attrs):
        if self.instance is not None and "stash_amount" not in self.initial_data:
            attrs = self.reconcile_stash_amount(attrs)
        attrs = super().validate(attrs)
        if self.instance is None and "stash_amount" not in self.initial_data:
            attrs = self.apply_stash_default(attrs)
            self.Meta.model(**{k: v for k, v in attrs.items() if k != "tags"}).clean()
        return attrs


class PumpingSerializer(
    StashDefaultsMixin, CoreModelWithDurationSerializer, TaggableSerializer
):
    required_fields = ("start", "end")
    parent = serializers.PrimaryKeyRelatedField(
        allow_null=True, queryset=models.Parent.objects.all(), required=False
    )

    class Meta(CoreModelWithDurationSerializer.Meta):
        model = models.Pumping
        fields = (
            "id",
            "child",
            "parent",
            "amount",
            "stash_amount",
            "start",
            "end",
            "duration",
            "notes",
            "tags",
            "timer",
        )

    def validate(self, attrs):
        check_milk_parent(self, attrs)
        if self.instance is None and not attrs.get("parent"):
            child = attrs.get("child") or getattr(attrs.get("timer"), "child", None)
            parent = models.parent_for_child(child) or models.single_parent()
            if child is not None and parent is None:
                raise ValidationError(
                    {
                        "parent": _(
                            "This child has no single linked parent; send `parent`."
                        )
                    }
                )
            if parent is not None:
                attrs["parent"] = parent
        # super().validate() (CoreModelWithDurationSerializer) may itself set
        # attrs["child"] from a supplied timer's child, so the parent-owned
        # invariant below has to be enforced after it runs, not before.
        attrs = super().validate(attrs)
        if self.instance is None or self.instance.parent_id or attrs.get("parent"):
            # A brand new row, or an update on a row that has (or is gaining)
            # a parent, never keeps a child: whether it arrived directly in
            # the request or was resolved from a timer just above, pumping
            # belongs to the parent and the legacy field stays NULL.
            attrs["child"] = None
        return attrs

    def apply_stash_default(self, attrs):
        if stash.settings().pumping_to_stash_default and attrs.get("amount"):
            attrs["stash_amount"] = attrs.get("amount")
        return attrs

    def reconcile_stash_amount(self, attrs):
        return self._follow_or_clamp_stash_amount(attrs)


class ChildSerializer(serializers.HyperlinkedModelSerializer):
    class Meta:
        model = models.Child
        fields = (
            "id",
            "first_name",
            "last_name",
            "birth_date",
            "birth_time",
            "due_date",
            "slug",
            "picture",
        )
        lookup_field = "slug"


class DiaperChangeSerializer(CoreModelSerializer, TaggableSerializer):
    class Meta:
        model = models.DiaperChange
        fields = (
            "id",
            "child",
            "time",
            "wet",
            "solid",
            "color",
            "amount",
            "notes",
            "tags",
        )


class FeedingSerializer(
    StashDefaultsMixin, CoreModelWithDurationSerializer, TaggableSerializer
):
    parent = serializers.PrimaryKeyRelatedField(
        allow_null=True, queryset=models.Parent.objects.all(), required=False
    )
    stash_discarded = serializers.FloatField(
        allow_null=True, required=False, min_value=0.1
    )
    stash_discard_reason = serializers.CharField(
        allow_blank=True,
        max_length=models.StashAdjustment._meta.get_field("reason").max_length,
        required=False,
    )

    class Meta(CoreModelWithDurationSerializer.Meta):
        model = models.Feeding
        fields = (
            "id",
            "child",
            "parent",
            "start",
            "end",
            "timer",
            "duration",
            "type",
            "method",
            "amount",
            "stash_amount",
            "stash_discarded",
            "stash_discard_reason",
            "notes",
            "tags",
        )

    def validate(self, attrs):
        self._discarded = attrs.pop("stash_discarded", serializers.empty)
        self._discard_reason = attrs.pop("stash_discard_reason", serializers.empty)
        method = attrs.get("method", getattr(self.instance, "method", None))
        if method not in models.Feeding.BREAST_METHODS:
            # A parent only belongs on a breastfeed: drop one sent (or kept)
            # on any other method rather than letting model clean() reject
            # it, mirroring how a bottle silently drops a stray `child` on
            # pumping.
            attrs["parent"] = None
        check_milk_parent(self, attrs)
        attrs = super().validate(attrs)
        if (
            self.instance is None
            and method in models.Feeding.BREAST_METHODS
            and "parent" not in self.initial_data
        ):
            # Create only, and only when `parent` was not sent at all (an
            # explicit `"parent": null` opts out, same as `stash_amount` in
            # StashDefaultsMixin): resolve from the child (direct or
            # timer-supplied), same as pumping, but without pumping's
            # "ambiguous parent" error -- a child with several linked
            # parents just gets no auto-fill.
            parent = (
                models.parent_for_child(attrs.get("child")) or models.single_parent()
            )
            if parent is not None:
                attrs["parent"] = parent
        stash_amount = attrs.get(
            "stash_amount", getattr(self.instance, "stash_amount", None)
        )
        if stash_amount is None and self._discarded not in (serializers.empty, None):
            raise ValidationError(
                {
                    "stash_discarded": _(
                        "Discarding milk needs milk taken from the stash."
                    )
                }
            )
        if stash_amount is None:
            # Nothing taken from the stash any more: any linked discard goes
            # with it (see save()), so a reason sent alongside has nothing to
            # attach to.
            self._discard_reason = serializers.empty
        if (
            self._discard_reason is not serializers.empty
            and self._discarded is serializers.empty
            and not (self.instance and self.instance.linked_discard())
        ):
            raise ValidationError(
                {
                    "stash_discard_reason": _(
                        "Send stash_discarded with the amount discarded."
                    )
                }
            )
        return attrs

    def apply_stash_default(self, attrs):
        if (
            attrs.get("type") in models.Feeding.STASH_TYPES
            and attrs.get("method") in models.Feeding.STASH_METHODS
            and attrs.get("amount")
            and stash.settings().bottle_from_stash_default
            and stash.stash_has_activity()
        ):
            attrs["stash_amount"] = attrs["amount"]
        return attrs

    def reconcile_stash_amount(self, attrs):
        type_ = attrs.get("type", self.instance.type)
        method = attrs.get("method", self.instance.method)
        if (
            type_ not in models.Feeding.STASH_TYPES
            or method not in models.Feeding.STASH_METHODS
        ):
            attrs["stash_amount"] = None
            return attrs
        return self._follow_or_clamp_stash_amount(attrs)

    def save(self, **kwargs):
        stash_amount_was_set = (
            self.instance is not None and self.instance.stash_amount is not None
        )
        start_changed = self.instance is not None and "start" in self.validated_data
        with transaction.atomic():
            instance = super().save(**kwargs)
            touched = False
            discarded_given = (
                getattr(self, "_discarded", serializers.empty) is not serializers.empty
            )
            reason_given = (
                getattr(self, "_discard_reason", serializers.empty)
                is not serializers.empty
            )
            if instance.stash_amount is not None and (
                discarded_given or reason_given or start_changed
            ):
                # A changed start also moves the linked discard, whose time
                # always follows the feeding's.
                existing = instance.linked_discard()
                amount = (
                    self._discarded
                    if discarded_given
                    else (existing.amount if existing else None)
                )
                reason = (
                    self._discard_reason
                    if reason_given
                    else (existing.reason if existing else "")
                )
                instance.set_linked_discard(amount, reason or "")
                touched = True
            if instance.stash_amount is None and stash_amount_was_set:
                instance.stash_adjustments.all().delete()
                touched = True
            if touched:
                # `instance` may carry a prefetched (now stale) cache of
                # stash_adjustments from the queryset that fetched it for this
                # update; drop it so to_representation() re-reads what was
                # just written instead of the pre-mutation snapshot.
                cache = getattr(instance, "_prefetched_objects_cache", None)
                if cache is not None:
                    cache.pop("stash_adjustments", None)
        return instance

    def to_representation(self, instance):
        data = super().to_representation(instance)
        discard = None if instance.stash_amount is None else instance.linked_discard()
        data["stash_discarded"] = discard.amount if discard else None
        data["stash_discard_reason"] = discard.reason if discard else ""
        return data


STASH_SETTINGS = {
    "pumping_to_stash": "pumping_to_stash_default",
    "bottle_from_stash": "bottle_from_stash_default",
    "warn_age_hours": "stash_warn_age_hours",
    "max_age_hours": "stash_max_age_hours",
}


def can_edit_stash_settings(user):
    """Whoever may change them on Site > Settings: staff with dbsettings'
    permission for the pumping settings."""
    return user.is_staff and user.has_perm("core.can_edit_pumping_settings")


def stash_settings_data(user):
    current = stash.settings()
    data = {field: getattr(current, attr) for field, attr in STASH_SETTINGS.items()}
    data["can_edit"] = can_edit_stash_settings(user)
    return data


class StashSettingsSerializer(serializers.Serializer):
    """The milk stash's site settings (Site > Settings > Milk stash)."""

    pumping_to_stash = serializers.BooleanField(required=False)
    bottle_from_stash = serializers.BooleanField(required=False)
    warn_age_hours = serializers.IntegerField(min_value=0, required=False)
    max_age_hours = serializers.IntegerField(min_value=0, required=False)

    def validate(self, attrs):
        if "warn_age_hours" not in attrs and "max_age_hours" not in attrs:
            # Leave the ages alone, even if they don't fit together on the web.
            return attrs
        current = stash.settings()
        warn = attrs.get("warn_age_hours", current.stash_warn_age_hours)
        max_ = attrs.get("max_age_hours", current.stash_max_age_hours)
        if warn >= max_:
            raise ValidationError(
                {
                    "warn_age_hours": _(
                        '"Expiring soon after" has to be less than "Expires after".'
                    )
                }
            )
        return attrs

    def save(self):
        current = stash.settings()
        for field, attr in STASH_SETTINGS.items():
            if field in self.validated_data:
                setattr(current, attr, self.validated_data[field])


class ParentSerializer(serializers.HyperlinkedModelSerializer):
    children = serializers.PrimaryKeyRelatedField(
        many=True, queryset=models.Child.objects.all(), required=False
    )

    class Meta:
        model = models.Parent
        fields = (
            "id",
            "first_name",
            "last_name",
            "slug",
            "picture",
            "produces_milk",
            "children",
        )
        lookup_field = "slug"


class StashAdjustmentSerializer(CoreModelSerializer, TaggableSerializer):
    parent = serializers.PrimaryKeyRelatedField(
        allow_null=True, queryset=models.Parent.objects.all(), required=False
    )
    feeding = serializers.PrimaryKeyRelatedField(
        allow_null=True, queryset=models.Feeding.objects.all(), required=False
    )
    signed_amount = serializers.FloatField(read_only=True)

    class Meta:
        model = models.StashAdjustment
        fields = (
            "id",
            "time",
            "amount",
            "kind",
            "reason",
            "signed_amount",
            "parent",
            "feeding",
            "notes",
            "tags",
        )

    def validate(self, attrs):
        check_milk_parent(self, attrs)
        if (
            self.instance is None
            and attrs.get("kind") == models.StashAdjustment.ADDED
            and "parent" not in self.initial_data
        ):
            # Create only, for added milk only, and only when `parent` was not
            # sent at all (an explicit `"parent": null` opts out): with a
            # single milk-producing parent there is nobody else the milk can
            # belong to. A discard is never filled in: without a parent it
            # takes the oldest milk of anyone.
            parent = models.single_parent()
            if parent:
                attrs["parent"] = parent
        return super().validate(attrs)

    def get_fields(self):
        # CoreModelSerializer declares a required "child" field; adjustments
        # have none. Popping it here (rather than shadowing it with a class
        # attribute) keeps this a normal Serializer field from the outside,
        # since a plain `child = None` also satisfies `hasattr(self, "child")`
        # and DRF's OPTIONS metadata treats that as "this is a ListSerializer,
        # recurse into `.child`" and crashes on the None.
        fields = super().get_fields()
        fields.pop("child", None)
        return fields


class HeadCircumferenceSerializer(CoreModelSerializer, TaggableSerializer):
    class Meta:
        model = models.HeadCircumference
        fields = ("id", "child", "head_circumference", "date", "notes", "tags")


class HeightSerializer(CoreModelSerializer, TaggableSerializer):
    class Meta:
        model = models.Height
        fields = ("id", "child", "height", "date", "notes", "tags")


class MedicationSerializer(CoreModelSerializer, TaggableSerializer):
    class Meta:
        model = models.Medication
        fields = (
            "id",
            "child",
            "name",
            "dosage",
            "dosage_unit",
            "time",
            "next_dose_interval",
            "notes",
            "tags",
        )


class NoteSerializer(CoreModelSerializer, TaggableSerializer):
    class Meta:
        model = models.Note
        fields = ("id", "child", "note", "image", "time", "tags")


class SleepSerializer(CoreModelWithDurationSerializer, TaggableSerializer):
    nap = serializers.BooleanField(allow_null=True, default=None, required=False)

    class Meta(CoreModelWithDurationSerializer.Meta):
        model = models.Sleep
        fields = (
            "id",
            "child",
            "start",
            "end",
            "timer",
            "duration",
            "nap",
            "notes",
            "tags",
        )


class TagSerializer(serializers.HyperlinkedModelSerializer):
    class Meta:
        model = models.Tag
        fields = ("slug", "name", "color", "last_used")
        extra_kwargs = {
            "slug": {"required": False, "read_only": True},
            "color": {"required": False},
            "last_used": {"required": False, "read_only": True},
        }


class TemperatureSerializer(CoreModelSerializer, TaggableSerializer):
    class Meta:
        model = models.Temperature
        fields = ("id", "child", "temperature", "time", "notes", "tags")


class TimerSerializer(CoreModelSerializer):
    child = serializers.PrimaryKeyRelatedField(
        allow_null=True,
        allow_empty=True,
        queryset=models.Child.objects.all(),
        required=False,
    )
    user = serializers.PrimaryKeyRelatedField(
        allow_null=True,
        allow_empty=True,
        queryset=get_user_model().objects.all(),
        required=False,
    )
    duration = serializers.DurationField(read_only=True, required=False)

    class Meta:
        model = models.Timer
        fields = ("id", "child", "name", "start", "duration", "user")

    def validate(self, attrs):
        attrs = super(TimerSerializer, self).validate(attrs)
        request_user = self.context["request"].user

        if self.instance is None:
            # Set user to current user if no value is provided.
            if "user" not in attrs or attrs["user"] is None:
                attrs["user"] = request_user
        elif "user" in attrs:
            # The owner may consume the timer, so taking over another user's
            # timer requires the same permission as consuming it.
            attrs["user"] = attrs["user"] or request_user
            if attrs["user"] != self.instance.user and not request_user.has_perm(
                "core.delete_timer"
            ):
                raise PermissionDenied(
                    "You do not have permission to change the user of a timer."
                )

        return attrs

    @transaction.atomic
    def update(self, instance, validated_data):
        # Work on the stored timer, whose owner may have changed since
        # validation, so the check uses it and a stale owner is never saved back.
        instance = models.Timer.objects.select_for_update().get(pk=instance.pk)
        user = validated_data.get("user", instance.user)
        if user != instance.user and not self.context["request"].user.has_perm(
            "core.delete_timer"
        ):
            raise PermissionDenied(
                "You do not have permission to change the user of a timer."
            )
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()
        return instance


class TummyTimeSerializer(CoreModelWithDurationSerializer, TaggableSerializer):
    class Meta(CoreModelWithDurationSerializer.Meta):
        model = models.TummyTime
        fields = (
            "id",
            "child",
            "start",
            "end",
            "timer",
            "duration",
            "milestone",
            "notes",
            "tags",
        )


class WeightSerializer(CoreModelSerializer, TaggableSerializer):
    class Meta:
        model = models.Weight
        fields = ("id", "child", "weight", "date", "notes", "tags")


class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = get_user_model()
        fields = (
            "id",
            "username",
            "first_name",
            "last_name",
            "email",
            "is_staff",
        )
        extra_kwargs = {k: {"read_only": True} for k in fields}


class ProfileSerializer(serializers.ModelSerializer):
    user = UserSerializer(many=False)
    api_key = serializers.SerializerMethodField("get_api_key")

    def get_api_key(self, value):
        return self.instance.api_key().key

    class Meta:
        model = babybuddy_models.Settings
        fields = (
            "user",
            "language",
            "timezone",
            "api_key",
        )
        extra_kwargs = {k: {"read_only": True} for k in fields}


class WebhookEndpointSerializer(serializers.ModelSerializer):
    """
    A webhook endpoint as another application sets it up for itself.

    The secret can be written and is never read back. An application that
    chose its own sends it here; one that did not is given the generated
    secret once, in the response to the request that created the endpoint.
    """

    # DRF leaves the model's URLValidator out of a URLField and puts its own
    # in, which also allows ftp. Nothing is ever sent to ftp, so the model's
    # own validators apply here as they do in the admin area.
    url = serializers.URLField(
        max_length=1000,
        validators=webhooks_models.WebhookEndpoint._meta.get_field("url").validators,
    )

    class Meta:
        model = webhooks_models.WebhookEndpoint
        fields = ("id", "name", "url", "secret", "active", "created", "last_delivery")
        read_only_fields = ("created", "last_delivery")
        extra_kwargs = {"secret": {"write_only": True, "min_length": 16}}


class CaregiverSerializer(serializers.ModelSerializer):
    """
    A caregiver account, created and managed without the admin area.

    Only the fields a caregiver account needs are here. The role cannot be
    changed through them: there is no staff or superuser flag and no groups
    field, so an account made here stays a caregiver whatever is sent later.

    The account is used through its API key, which is returned once, when the
    account is created. It has no password unless an email address is given,
    in which case it is created with one nobody knows so that the reset flow
    can reach it and its owner can set a real one.
    """

    access_expires = serializers.DateTimeField(
        source="settings.access_expires", required=False, allow_null=True
    )

    class Meta:
        model = get_user_model()
        fields = (
            "id",
            "username",
            "email",
            "first_name",
            "last_name",
            "is_active",
            "access_expires",
        )

    def create(self, validated_data):
        expires = validated_data.pop("settings", {}).get("access_expires")
        # Django's reset form skips accounts whose password is unusable, so an
        # address on its own would never receive anything. With one the account
        # gets a usable password that nobody knows; without one it gets none.
        password = secrets.token_urlsafe(32) if validated_data.get("email") else None
        with transaction.atomic():
            user = get_user_model().objects.create_user(
                password=password, **validated_data
            )
            user.groups.add(
                Group.objects.get(name=settings.BABY_BUDDY["CAREGIVER_GROUP_NAME"])
            )
            user.settings.access_expires = expires
            user.settings.save()
        return user

    def update(self, instance, validated_data):
        user_settings = validated_data.pop("settings", {})
        with transaction.atomic():
            user = super().update(instance, validated_data)
            if user.email and not user.has_usable_password():
                # The address is what the reset flow needs, so an account that
                # gains one has to gain a usable password with it.
                user.set_password(secrets.token_urlsafe(32))
                user.save(update_fields=["password"])
            if "access_expires" in user_settings:
                user.settings.access_expires = user_settings["access_expires"]
                user.settings.save()
        return user
