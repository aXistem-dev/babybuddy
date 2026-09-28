# -*- coding: utf-8 -*-
from datetime import time

from django.utils.translation import gettext_lazy as _

import dbsettings

from django.forms.fields import BooleanField
from core.fields import NapStartMaxTimeField, NapStartMinTimeField
from .widgets import TimeInput
from django.forms.widgets import CheckboxInput


class NapStartMaxTimeValue(dbsettings.TimeValue):
    field = NapStartMaxTimeField


class NapStartMinTimeValue(dbsettings.TimeValue):
    field = NapStartMinTimeField


class NapSettings(dbsettings.Group):
    nap_start_min = NapStartMinTimeValue(
        default=time(6),
        description=_("Default minimum nap start time"),
        help_text=_(
            "The minimum default time that a sleep entry is consider a nap. If set the nap property will be preselected if the start time is within the bounds."
        ),
        widget=TimeInput,
    )
    nap_start_max = NapStartMaxTimeValue(
        default=time(18),
        description=_("Default maximum nap start time"),
        help_text=_(
            "The maximum default time that a sleep entry is consider a nap. If set the nap property will be preselected if the start time is within the bounds."
        ),
        widget=TimeInput,
    )


class FeedingDiffEndValue(dbsettings.BooleanValue):
    field = BooleanField


class FeedingSettings(dbsettings.Group):
    feeding_diff_end = FeedingDiffEndValue(
        required=False,
        default=False,
        description=_("Time diff between feedings based on end"),
        help_text=_(
            "Use feeding end instead of start time for displaying time between feedings"
        ),
        widget=CheckboxInput,
    )


class StashBooleanValue(dbsettings.BooleanValue):
    field = BooleanField


class StashSettings(dbsettings.Group):
    pumping_to_stash_default = StashBooleanValue(
        required=False,
        default=True,
        widget=CheckboxInput,
        description=_("Store pumped milk in the stash by default"),
        help_text=_(
            'Pre-selects "Store in stash" on new pumping entries; also applies to '
            "pumping created through the API without a stash amount."
        ),
    )
    bottle_from_stash_default = StashBooleanValue(
        required=False,
        default=True,
        widget=CheckboxInput,
        description=_("Take breast milk bottles from the stash by default"),
        help_text=_(
            'Pre-selects "Taken from stash" on new breast milk bottles once the '
            "stash has been used; API-created bottles without a stash amount "
            "follow the same rule."
        ),
    )
    stash_warn_age_hours = dbsettings.PositiveIntegerValue(
        default=48,
        description=_("Warn about stashed milk after (hours)"),
        help_text=_("Milk older than this is marked to use first."),
    )
    stash_max_age_hours = dbsettings.PositiveIntegerValue(
        default=72,
        description=_("Throw stashed milk away after (hours)"),
        help_text=_("Milk older than this is marked expired."),
    )
