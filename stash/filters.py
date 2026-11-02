# -*- coding: utf-8 -*-
from core.filters import TagFilter

from . import models


class StashAdjustmentFilter(TagFilter):
    class Meta:
        model = models.StashAdjustment
        fields = ["kind"]
