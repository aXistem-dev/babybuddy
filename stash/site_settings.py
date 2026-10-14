# -*- coding: utf-8 -*-
from django.utils.translation import gettext_lazy as _

import dbsettings


class StashSettings(dbsettings.Group):
    stash_warn_age_hours = dbsettings.PositiveIntegerValue(
        default=48,
        description=_("Stored milk expires soon after (hours)"),
        help_text=_("Stored milk is marked as expiring soon at this age."),
    )
    stash_max_age_hours = dbsettings.PositiveIntegerValue(
        default=72,
        description=_("Stored milk expires after (hours)"),
        help_text=_("Stored milk is marked as expired at this age."),
    )
