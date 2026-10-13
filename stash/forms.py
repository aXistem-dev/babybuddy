# -*- coding: utf-8 -*-
from django import forms

from babybuddy.widgets import DateTimeInput
from core.forms import CoreModelForm, TaggableModelForm
from core.widgets import PillRadioSelect

from . import models


class StashAdjustmentForm(CoreModelForm, TaggableModelForm):
    fieldsets = [
        {"fields": ["kind", "time", "amount"], "layout": "required"},
        {"fields": ["notes", "tags"], "layout": "advanced"},
    ]

    class Meta:
        model = models.StashAdjustment
        fields = ["kind", "time", "amount", "notes", "tags"]
        widgets = {
            "kind": PillRadioSelect(),
            "time": DateTimeInput(),
            "notes": forms.Textarea(attrs={"rows": 5}),
        }
