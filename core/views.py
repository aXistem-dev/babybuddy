# -*- coding: utf-8 -*-
from django.contrib import messages
from django.contrib.messages.views import SuccessMessageMixin
from django.db.models import Count
from django.db.models.functions import Lower
from django.forms import Form, ValidationError
from django.http import HttpResponseRedirect
from django.urls import reverse, reverse_lazy
from django.utils import timezone
from django.utils.translation import gettext as _
from django.views.generic.base import RedirectView, TemplateView, View
from django.views.generic.detail import DetailView
from django.views.generic.edit import CreateView, UpdateView, DeleteView, FormView

from babybuddy.mixins import LoginRequiredMixin, PermissionRequiredMixin
from babybuddy.views import BabyBuddyFilterView, BabyBuddyPaginatedView
from core import filters, forms, models, stash, timeline


def _prepare_timeline_context_data(context, date, child=None, user=None):
    date = timezone.datetime.strptime(date, "%Y-%m-%d")
    date = timezone.localtime(timezone.make_aware(date))
    context["timeline_objects"] = timeline.get_objects(date, child, user)
    context["date"] = date
    context["date_previous"] = date - timezone.timedelta(days=1)
    if date.date() < timezone.localdate():
        context["date_next"] = date + timezone.timedelta(days=1)
    pass


class CoreFormMixin:
    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        if issubclass(self.get_form_class(), forms.CoreModelForm):
            kwargs["user"] = self.request.user
        return kwargs

    def form_valid(self, form):
        try:
            return super().form_valid(form)
        except ValidationError as error:
            form.add_error(None, error)
            return self.form_invalid(form)


class CoreAddView(
    CoreFormMixin, PermissionRequiredMixin, SuccessMessageMixin, CreateView
):
    def get_success_message(self, cleaned_data):
        cleaned_data["model"] = self.model._meta.verbose_name.title()
        if cleaned_data.get("child"):
            self.success_message = _("%(model)s entry for %(child)s added!")
        else:
            self.success_message = _("%(model)s entry added!")
        return self.success_message % cleaned_data

    def get_form_kwargs(self):
        """
        Check for and add "child", "timer", "parent", "kind", "amount" and
        "reason" from request query parameters.
          - "child" may provide a slug for a Child instance.
          - "timer" may provided an ID for a Timer instance.
          - "parent" may provide a slug for a Parent instance.
          - "kind" may provide a StashAdjustment kind.
          - "amount" may provide a StashAdjustment amount.
          - "reason" may provide a StashAdjustment reason.

        These arguments are used in some add views to pre-fill initial data in
        the form fields.

        :return: Updated keyword arguments.
        """
        kwargs = super(CoreAddView, self).get_form_kwargs()
        if issubclass(self.get_form_class(), forms.CoreModelForm):
            for parameter in ["child", "timer", "parent", "kind", "amount", "reason"]:
                if parameter in self.request.GET:
                    kwargs[parameter] = self.request.GET[parameter]
        return kwargs


class CoreUpdateView(
    CoreFormMixin, PermissionRequiredMixin, SuccessMessageMixin, UpdateView
):
    def get_success_message(self, cleaned_data):
        cleaned_data["model"] = self.model._meta.verbose_name.title()
        if cleaned_data.get("child"):
            self.success_message = _("%(model)s entry for %(child)s updated.")
        else:
            self.success_message = _("%(model)s entry updated.")
        return self.success_message % cleaned_data


class CoreDeleteView(PermissionRequiredMixin, SuccessMessageMixin, DeleteView):
    def get_success_message(self, cleaned_data):
        return _("%(model)s entry deleted.") % {
            "model": self.model._meta.verbose_name.title()
        }


class BMIList(PermissionRequiredMixin, BabyBuddyPaginatedView, BabyBuddyFilterView):
    model = models.BMI
    template_name = "core/bmi_list.html"
    permission_required = ("core.view_bmi",)
    filterset_class = filters.BMIFilter


class BMIAdd(CoreAddView):
    model = models.BMI
    permission_required = ("core.add_bmi",)
    form_class = forms.BMIForm
    success_url = reverse_lazy("core:bmi-list")


class BMIUpdate(CoreUpdateView):
    model = models.BMI
    permission_required = ("core.change_bmi",)
    form_class = forms.BMIForm
    success_url = reverse_lazy("core:bmi-list")


class BMIDelete(CoreDeleteView):
    model = models.BMI
    permission_required = ("core.delete_bmi",)
    success_url = reverse_lazy("core:bmi-list")


class ChildList(PermissionRequiredMixin, BabyBuddyPaginatedView, BabyBuddyFilterView):
    model = models.Child
    template_name = "core/child_list.html"
    permission_required = ("core.view_child",)
    filterset_fields = ("first_name", "last_name")


class ChildAdd(CoreAddView):
    model = models.Child
    permission_required = ("core.add_child",)
    form_class = forms.ChildForm
    success_url = reverse_lazy("core:child-list")
    success_message = _("%(first_name)s %(last_name)s added!")


class ChildDetail(PermissionRequiredMixin, DetailView):
    model = models.Child
    permission_required = ("core.view_child",)

    def get_context_data(self, **kwargs):
        context = super(ChildDetail, self).get_context_data(**kwargs)
        date = self.request.GET.get("date", str(timezone.localdate()))
        _prepare_timeline_context_data(context, date, self.object, self.request.user)
        return context


class ChildUpdate(CoreUpdateView):
    model = models.Child
    permission_required = ("core.change_child",)
    form_class = forms.ChildForm
    success_url = reverse_lazy("core:child-list")


class ChildDelete(CoreUpdateView):
    model = models.Child
    form_class = forms.ChildDeleteForm
    template_name = "core/child_confirm_delete.html"
    permission_required = ("core.delete_child",)
    success_url = reverse_lazy("core:child-list")

    def get_success_message(self, cleaned_data):
        """This class cannot use `CoreDeleteView` because of the confirmation
        step required so the success message must be overridden."""
        success_message = _("%(model)s entry deleted.") % {
            "model": self.model._meta.verbose_name.title()
        }
        return success_message % cleaned_data


class DiaperChangeList(
    PermissionRequiredMixin, BabyBuddyPaginatedView, BabyBuddyFilterView
):
    model = models.DiaperChange
    template_name = "core/diaperchange_list.html"
    permission_required = ("core.view_diaperchange",)
    filterset_class = filters.DiaperChangeFilter


class DiaperChangeAdd(CoreAddView):
    model = models.DiaperChange
    permission_required = ("core.add_diaperchange",)
    form_class = forms.DiaperChangeForm
    success_url = reverse_lazy("core:diaperchange-list")


class DiaperChangeUpdate(CoreUpdateView):
    model = models.DiaperChange
    permission_required = ("core.change_diaperchange",)
    form_class = forms.DiaperChangeForm
    success_url = reverse_lazy("core:diaperchange-list")


class DiaperChangeDelete(CoreDeleteView):
    model = models.DiaperChange
    permission_required = ("core.delete_diaperchange",)
    success_url = reverse_lazy("core:diaperchange-list")


class FeedingList(PermissionRequiredMixin, BabyBuddyPaginatedView, BabyBuddyFilterView):
    model = models.Feeding
    template_name = "core/feeding_list.html"
    permission_required = ("core.view_feeding",)
    filterset_class = filters.FeedingFilter
    queryset = models.Feeding.objects.select_related("child", "parent")


class FeedingAdd(CoreAddView):
    model = models.Feeding
    permission_required = ("core.add_feeding",)
    form_class = forms.FeedingForm
    success_url = reverse_lazy("core:feeding-list")


class BottleFeedingAdd(CoreAddView):
    model = models.Feeding
    permission_required = ("core.add_feeding",)
    form_class = forms.BottleFeedingForm
    success_url = reverse_lazy("core:feeding-list")


class FeedingUpdate(CoreUpdateView):
    model = models.Feeding
    permission_required = ("core.change_feeding",)
    form_class = forms.FeedingForm
    success_url = reverse_lazy("core:feeding-list")


class FeedingDelete(CoreDeleteView):
    model = models.Feeding
    permission_required = ("core.delete_feeding",)
    success_url = reverse_lazy("core:feeding-list")


class HeadCircumferenceList(
    PermissionRequiredMixin, BabyBuddyPaginatedView, BabyBuddyFilterView
):
    model = models.HeadCircumference
    template_name = "core/head_circumference_list.html"
    permission_required = ("core.view_headcircumference",)
    filterset_class = filters.HeadCircumferenceFilter


class HeadCircumferenceAdd(CoreAddView):
    model = models.HeadCircumference
    template_name = "core/head_circumference_form.html"
    permission_required = ("core.add_headcircumference",)
    form_class = forms.HeadCircumferenceForm
    success_url = reverse_lazy("core:head-circumference-list")


class HeadCircumferenceUpdate(CoreUpdateView):
    model = models.HeadCircumference
    template_name = "core/head_circumference_form.html"
    permission_required = ("core.change_headcircumference",)
    form_class = forms.HeadCircumferenceForm
    success_url = reverse_lazy("core:head-circumference-list")


class HeadCircumferenceDelete(CoreDeleteView):
    model = models.HeadCircumference
    template_name = "core/head_circumference_confirm_delete.html"
    permission_required = ("core.delete_headcircumference",)
    success_url = reverse_lazy("core:head-circumference-list")


class HeightList(PermissionRequiredMixin, BabyBuddyPaginatedView, BabyBuddyFilterView):
    model = models.Height
    template_name = "core/height_list.html"
    permission_required = ("core.view_height",)
    filterset_class = filters.HeightFilter


class HeightAdd(CoreAddView):
    model = models.Height
    permission_required = ("core.add_height",)
    form_class = forms.HeightForm
    success_url = reverse_lazy("core:height-list")


class HeightUpdate(CoreUpdateView):
    model = models.Height
    permission_required = ("core.change_height",)
    form_class = forms.HeightForm
    success_url = reverse_lazy("core:height-list")


class HeightDelete(CoreDeleteView):
    model = models.Height
    permission_required = ("core.delete_height",)
    success_url = reverse_lazy("core:height-list")


class MedicationList(
    PermissionRequiredMixin, BabyBuddyPaginatedView, BabyBuddyFilterView
):
    model = models.Medication
    template_name = "core/medication_list.html"
    permission_required = ("core.view_medication",)
    filterset_class = filters.MedicationFilter


class MedicationAdd(CoreAddView):
    model = models.Medication
    permission_required = ("core.add_medication",)
    form_class = forms.MedicationForm
    success_url = reverse_lazy("core:medication-list")


class MedicationUpdate(CoreUpdateView):
    model = models.Medication
    permission_required = ("core.change_medication",)
    form_class = forms.MedicationForm
    success_url = reverse_lazy("core:medication-list")


class MedicationDelete(CoreDeleteView):
    model = models.Medication
    permission_required = ("core.delete_medication",)
    success_url = reverse_lazy("core:medication-list")


class NoteList(PermissionRequiredMixin, BabyBuddyPaginatedView, BabyBuddyFilterView):
    model = models.Note
    template_name = "core/note_list.html"
    permission_required = ("core.view_note",)
    filterset_class = filters.NoteFilter


class NoteAdd(CoreAddView):
    model = models.Note
    permission_required = ("core.add_note",)
    form_class = forms.NoteForm
    success_url = reverse_lazy("core:note-list")


class NoteUpdate(CoreUpdateView):
    model = models.Note
    permission_required = ("core.change_note",)
    form_class = forms.NoteForm
    success_url = reverse_lazy("core:note-list")


class NoteDelete(CoreDeleteView):
    model = models.Note
    permission_required = ("core.delete_note",)
    success_url = reverse_lazy("core:note-list")


class ParentList(PermissionRequiredMixin, BabyBuddyPaginatedView, BabyBuddyFilterView):
    model = models.Parent
    template_name = "core/parent_list.html"
    permission_required = ("core.view_parent",)
    filterset_fields = ("first_name", "last_name")


class ParentAdd(CoreAddView):
    model = models.Parent
    permission_required = ("core.add_parent",)
    form_class = forms.ParentForm
    success_url = reverse_lazy("core:parent-list")


class ParentDetail(PermissionRequiredMixin, DetailView):
    model = models.Parent
    permission_required = ("core.view_parent",)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["pumping"] = self.object.pumping.order_by("-start")[:20]
        context["adjustments"] = self.object.stash_adjustments.order_by("-time")[:20]
        context["breastfeeding"] = self._breastfeeding_summary()
        return context

    def _breastfeeding_summary(self):
        feedings = self.object.breastfeedings.order_by("-start")
        today_start = timezone.localtime().replace(
            hour=0, minute=0, second=0, microsecond=0
        )
        week_start = today_start - timezone.timedelta(days=7)

        def totals(queryset):
            # Every feeding is a session, but overlapping feedings (e.g. two
            # babies fed together) count their shared time only once.
            count = 0
            seconds = 0
            covered_until = None
            for feeding in queryset.order_by("start"):
                count += 1
                start = feeding.start
                if covered_until is not None:
                    start = max(start, covered_until)
                if feeding.end > start:
                    seconds += (feeding.end - start).total_seconds()
                if covered_until is None or feeding.end > covered_until:
                    covered_until = feeding.end
            return {"count": count, "minutes": round(seconds / 60)}

        last = feedings.first()
        return {
            "today": totals(feedings.filter(start__gte=today_start)),
            "week": totals(feedings.filter(start__gte=week_start)),
            "last_method": last.get_method_display() if last else None,
        }


class ParentUpdate(CoreUpdateView):
    model = models.Parent
    permission_required = ("core.change_parent",)
    form_class = forms.ParentForm
    success_url = reverse_lazy("core:parent-list")


class ParentDelete(CoreDeleteView):
    model = models.Parent
    permission_required = ("core.delete_parent",)
    success_url = reverse_lazy("core:parent-list")

    def form_valid(self, form):
        if self.object.pumping.exists() or self.object.stash_adjustments.exists():
            messages.error(
                self.request,
                _(
                    "%(name)s still has pumping or stash entries; "
                    "move or delete them first."
                )
                % {"name": self.object},
            )
            return HttpResponseRedirect(reverse("core:parent", args=[self.object.slug]))
        return super().form_valid(form)


class PumpingList(PermissionRequiredMixin, BabyBuddyPaginatedView, BabyBuddyFilterView):
    model = models.Pumping
    template_name = "core/pumping_list.html"
    permission_required = ("core.view_pumping",)
    filterset_class = filters.PumpingFilter

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["unassigned"] = models.Pumping.objects.filter(
            parent__isnull=True
        ).count()
        return context


class PumpingAdd(CoreAddView):
    model = models.Pumping
    permission_required = ("core.add_pumping",)
    form_class = forms.PumpingForm
    success_url = reverse_lazy("core:pumping-list")
    success_message = _("%(model)s entry added!")


class PumpingUpdate(CoreUpdateView):
    model = models.Pumping
    permission_required = ("core.change_pumping",)
    form_class = forms.PumpingForm
    success_url = reverse_lazy("core:pumping-list")
    success_message = _("%(model)s entry for %(child)s updated.")


class PumpingDelete(CoreDeleteView):
    model = models.Pumping
    permission_required = ("core.delete_pumping",)
    success_url = reverse_lazy("core:pumping-list")


# Holds the `negative_since` of the dip below zero whose warning this browser
# dismissed, so the warning returns for the next dip.
STASH_WARNING_COOKIE = "stash_negative_warning_dismissed"


def _stash_warning_token(summary):
    since = summary["negative_since"]
    return since.isoformat() if since else None


class StashView(PermissionRequiredMixin, TemplateView):
    template_name = "core/stash.html"
    permission_required = ("core.view_pumping",)

    def get(self, request, *args, **kwargs):
        response = super().get(request, *args, **kwargs)
        summary = response.context_data["summary"]
        if (
            summary["negative_since"] is None
            and STASH_WARNING_COOKIE in request.COOKIES
        ):
            # Back at or above zero: forget the dismissal.
            response.delete_cookie(STASH_WARNING_COOKIE)
        return response

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["summary"] = stash.stash_summary()
        token = _stash_warning_token(context["summary"])
        context["show_negative_warning"] = bool(token) and (
            self.request.COOKIES.get(STASH_WARNING_COOKIE) != token
        )
        context["expired_amount"] = stash.expired_amount(context["summary"])
        context["throw_away_reason"] = stash.throw_away_reason(context["summary"])
        context["children"] = models.Child.objects.order_by("first_name")

        events = stash.stash_events()
        selected_child = None
        child_slug = self.request.GET.get("child")
        if child_slug:
            selected_child = context["children"].filter(slug=child_slug).first()
            # An unknown slug is not an error: it just shows every movement.
            if selected_child:
                events = [
                    e
                    for e in events
                    if e.kind == "feeding" and e.obj.child_id == selected_child.id
                ]
        context["selected_child"] = selected_child
        context["events"] = list(reversed(events))[:30]
        return context


class StashWarningDismiss(LoginRequiredMixin, View):
    """
    Hides the negative-stash warning in this browser until the stash is back
    at or above zero. GET is not supported.
    """

    def post(self, request, *args, **kwargs):
        response = HttpResponseRedirect(reverse("core:stash"))
        token = _stash_warning_token(stash.stash_summary())
        if token:
            response.set_cookie(
                STASH_WARNING_COOKIE,
                token,
                max_age=365 * 24 * 60 * 60,
                secure=request.is_secure(),
                httponly=True,
                samesite="Lax",
            )
        return response


class StashAdjustmentList(
    PermissionRequiredMixin, BabyBuddyPaginatedView, BabyBuddyFilterView
):
    model = models.StashAdjustment
    template_name = "core/stashadjustment_list.html"
    permission_required = ("core.view_stashadjustment",)
    filterset_fields = ("kind", "parent")


class StashAdjustmentAdd(CoreAddView):
    model = models.StashAdjustment
    permission_required = ("core.add_stashadjustment",)
    form_class = forms.StashAdjustmentForm
    success_url = reverse_lazy("core:stashadjustment-list")


class StashAdjustmentUpdate(CoreUpdateView):
    model = models.StashAdjustment
    permission_required = ("core.change_stashadjustment",)
    form_class = forms.StashAdjustmentForm
    success_url = reverse_lazy("core:stashadjustment-list")


class StashAdjustmentDelete(CoreDeleteView):
    model = models.StashAdjustment
    permission_required = ("core.delete_stashadjustment",)
    success_url = reverse_lazy("core:stashadjustment-list")


class SleepList(PermissionRequiredMixin, BabyBuddyPaginatedView, BabyBuddyFilterView):
    model = models.Sleep
    template_name = "core/sleep_list.html"
    permission_required = ("core.view_sleep",)
    filterset_class = filters.SleepFilter


class SleepAdd(CoreAddView):
    model = models.Sleep
    permission_required = ("core.add_sleep",)
    form_class = forms.SleepForm
    success_url = reverse_lazy("core:sleep-list")


class SleepUpdate(CoreUpdateView):
    model = models.Sleep
    permission_required = ("core.change_sleep",)
    form_class = forms.SleepForm
    success_url = reverse_lazy("core:sleep-list")


class SleepDelete(CoreDeleteView):
    model = models.Sleep
    permission_required = ("core.delete_sleep",)
    success_url = reverse_lazy("core:sleep-list")


class TagAdminList(
    PermissionRequiredMixin, BabyBuddyPaginatedView, BabyBuddyFilterView
):
    model = models.Tag
    template_name = "core/tag_list.html"
    permission_required = ("core.view_tag",)
    filterset_class = filters.TagFilter

    def get_queryset(self):
        return (
            super()
            .get_queryset()
            .annotate(Count("core_tagged_items"))
            .order_by(Lower("name"))
        )


class TagAdminDetail(PermissionRequiredMixin, DetailView):
    model = models.Tag
    permission_required = ("core.view_tag",)

    def get_queryset(self):
        qs = super().get_queryset()
        qs = qs.annotate(
            Count("feeding"),
            Count("diaperchange"),
            Count("pumping"),
            Count("sleep"),
            Count("tummytime"),
            Count("bmi"),
            Count("headcircumference"),
            Count("height"),
            Count("temperature"),
            Count("weight"),
        )
        return qs


class TagAdminAdd(CoreAddView):
    model = models.Tag
    permission_required = ("core.add_tag",)
    form_class = forms.TagAdminForm
    success_url = reverse_lazy("core:tag-list")


class TagAdminUpdate(CoreUpdateView):
    model = models.Tag
    permission_required = ("core.change_tag",)
    form_class = forms.TagAdminForm
    success_url = reverse_lazy("core:tag-list")


class TagAdminDelete(CoreDeleteView):
    model = models.Tag
    permission_required = ("core.delete_tag",)
    success_url = reverse_lazy("core:tag-list")

    def get_queryset(self):
        qs = super().get_queryset()
        return qs.annotate(Count("core_tagged_items"))


class TemperatureList(
    PermissionRequiredMixin, BabyBuddyPaginatedView, BabyBuddyFilterView
):
    model = models.Temperature
    template_name = "core/temperature_list.html"
    permission_required = ("core.view_temperature",)
    filterset_class = filters.TemperatureFilter


class TemperatureAdd(CoreAddView):
    model = models.Temperature
    permission_required = ("core.add_temperature",)
    form_class = forms.TemperatureForm
    success_url = reverse_lazy("core:temperature-list")
    success_message = _("%(model)s reading added!")


class TemperatureUpdate(CoreUpdateView):
    model = models.Temperature
    permission_required = ("core.change_temperature",)
    form_class = forms.TemperatureForm
    success_url = reverse_lazy("core:temperature-list")
    success_message = _("%(model)s reading for %(child)s updated.")


class TemperatureDelete(CoreDeleteView):
    model = models.Temperature
    permission_required = ("core.delete_temperature",)
    success_url = reverse_lazy("core:temperature-list")


class Timeline(LoginRequiredMixin, TemplateView):
    template_name = "timeline/timeline.html"

    # Show the overall timeline or a child timeline if one Child instance.
    def get(self, request, *args, **kwargs):
        children = models.Child.objects.count()
        if children == 1:
            return HttpResponseRedirect(
                reverse("core:child", args={models.Child.objects.first().slug})
            )
        return super(Timeline, self).get(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super(Timeline, self).get_context_data(**kwargs)
        date = self.request.GET.get("date", str(timezone.localdate()))
        _prepare_timeline_context_data(context, date, user=self.request.user)
        return context


class TimerList(PermissionRequiredMixin, BabyBuddyPaginatedView, BabyBuddyFilterView):
    model = models.Timer
    template_name = "core/timer_list.html"
    permission_required = ("core.view_timer",)
    filterset_fields = ("user",)


class TimerDetail(PermissionRequiredMixin, DetailView):
    model = models.Timer
    permission_required = ("core.view_timer",)


class TimerAdd(PermissionRequiredMixin, CreateView):
    model = models.Timer
    permission_required = ("core.add_timer",)
    form_class = forms.TimerForm

    def get_form_kwargs(self):
        kwargs = super(TimerAdd, self).get_form_kwargs()
        kwargs.update({"user": self.request.user})
        return kwargs

    def get_success_url(self):
        return reverse("core:timer-detail", kwargs={"pk": self.object.pk})


class TimerUpdate(CoreUpdateView):
    model = models.Timer
    permission_required = ("core.change_timer",)
    form_class = forms.TimerForm
    success_url = reverse_lazy("core:timer-list")

    def get_form_kwargs(self):
        kwargs = super(TimerUpdate, self).get_form_kwargs()
        kwargs.update({"user": self.request.user})
        return kwargs

    def get_success_url(self):
        instance = self.get_object()
        return reverse("core:timer-detail", kwargs={"pk": instance.pk})


class TimerAddQuick(PermissionRequiredMixin, RedirectView):
    http_method_names = ["post"]
    permission_required = ("core.add_timer",)

    def post(self, request, *args, **kwargs):
        instance = models.Timer.objects.create(user=request.user)
        # Find child from child pk in POST
        child_id = request.POST.get("child", False)
        child = models.Child.objects.get(pk=child_id) if child_id else None
        if child:
            instance.child = child
        # Add child relationship if there is only Child instance.
        elif models.Child.count() == 1:
            instance.child = models.Child.objects.first()
        instance.save()
        self.url = request.GET.get(
            "next", reverse("core:timer-detail", args={instance.id})
        )
        return super(TimerAddQuick, self).get(request, *args, **kwargs)


class TimerRestart(PermissionRequiredMixin, RedirectView):
    http_method_names = ["post"]
    permission_required = ("core.change_timer",)

    def post(self, request, *args, **kwargs):
        instance = models.Timer.objects.get(id=kwargs["pk"])
        instance.restart()
        messages.success(request, "{} restarted.".format(instance))
        return super(TimerRestart, self).get(request, *args, **kwargs)

    def get_redirect_url(self, *args, **kwargs):
        return reverse("core:timer-detail", kwargs={"pk": kwargs["pk"]})


class TimerDelete(CoreDeleteView):
    model = models.Timer
    permission_required = ("core.delete_timer",)
    success_url = reverse_lazy("core:timer-list")


class TummyTimeList(
    PermissionRequiredMixin, BabyBuddyPaginatedView, BabyBuddyFilterView
):
    model = models.TummyTime
    template_name = "core/tummytime_list.html"
    permission_required = ("core.view_tummytime",)
    filterset_class = filters.TummyTimeFilter


class TummyTimeAdd(CoreAddView):
    model = models.TummyTime
    permission_required = ("core.add_tummytime",)
    form_class = forms.TummyTimeForm
    success_url = reverse_lazy("core:tummytime-list")


class TummyTimeUpdate(CoreUpdateView):
    model = models.TummyTime
    permission_required = ("core.change_tummytime",)
    form_class = forms.TummyTimeForm
    success_url = reverse_lazy("core:tummytime-list")


class TummyTimeDelete(CoreDeleteView):
    model = models.TummyTime
    permission_required = ("core.delete_tummytime",)
    success_url = reverse_lazy("core:tummytime-list")


class WeightList(PermissionRequiredMixin, BabyBuddyPaginatedView, BabyBuddyFilterView):
    model = models.Weight
    template_name = "core/weight_list.html"
    permission_required = ("core.view_weight",)
    filterset_class = filters.WeightFilter


class WeightAdd(CoreAddView):
    model = models.Weight
    permission_required = ("core.add_weight",)
    form_class = forms.WeightForm
    success_url = reverse_lazy("core:weight-list")


class WeightUpdate(CoreUpdateView):
    model = models.Weight
    permission_required = ("core.change_weight",)
    form_class = forms.WeightForm
    success_url = reverse_lazy("core:weight-list")


class WeightDelete(CoreDeleteView):
    model = models.Weight
    permission_required = ("core.delete_weight",)
    success_url = reverse_lazy("core:weight-list")
