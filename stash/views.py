# -*- coding: utf-8 -*-
from django.urls import reverse_lazy
from django.views.generic.base import TemplateView

from babybuddy.mixins import PermissionRequiredMixin
from babybuddy.views import BabyBuddyFilterView, BabyBuddyPaginatedView
from core.views import CoreAddView, CoreDeleteView, CoreUpdateView

from . import filters, forms, models, stash


class Stash(PermissionRequiredMixin, TemplateView):
    template_name = "stash/stash.html"
    permission_required = ("stash.view_stashadjustment",)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["summary"] = stash.summary()
        return context


class StashAdjustmentList(
    PermissionRequiredMixin, BabyBuddyPaginatedView, BabyBuddyFilterView
):
    model = models.StashAdjustment
    template_name = "stash/stashadjustment_list.html"
    permission_required = ("stash.view_stashadjustment",)
    filterset_class = filters.StashAdjustmentFilter


class StashAdjustmentAdd(CoreAddView):
    model = models.StashAdjustment
    permission_required = ("stash.add_stashadjustment",)
    form_class = forms.StashAdjustmentForm
    success_url = reverse_lazy("stash:stash")

    def get_initial(self):
        """Pre-fill the kind, amount and notes from the query, as the stash
        page does to throw away expired milk."""
        initial = super().get_initial()
        for field in ("kind", "amount", "notes"):
            if field in self.request.GET:
                initial[field] = self.request.GET[field]
        return initial


class StashAdjustmentUpdate(CoreUpdateView):
    model = models.StashAdjustment
    permission_required = ("stash.change_stashadjustment",)
    form_class = forms.StashAdjustmentForm
    success_url = reverse_lazy("stash:stashadjustment-list")


class StashAdjustmentDelete(CoreDeleteView):
    model = models.StashAdjustment
    permission_required = ("stash.delete_stashadjustment",)
    success_url = reverse_lazy("stash:stashadjustment-list")
