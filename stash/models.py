# -*- coding: utf-8 -*-
from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from taggit.managers import TaggableManager

from core.models import Tagged, validate_time

from .site_settings import StashSettings


class StashAdjustment(models.Model):
    """
    Milk added to the stash or discarded from it by hand. Pumping and bottles
    move milk through their own `to_stash` and `from_stash` fields; these are
    for everything else, such as milk already in the freezer or milk that went
    off.
    """

    model_name = "stash_adjustment"
    time = models.DateTimeField(
        blank=False, default=timezone.localtime, null=False, verbose_name=_("Time")
    )
    amount = models.FloatField(blank=False, null=False, verbose_name=_("Amount"))
    kind = models.CharField(
        choices=[
            ("added", _("Added")),
            ("discarded", _("Discarded")),
        ],
        max_length=255,
        verbose_name=_("Kind"),
    )
    notes = models.TextField(blank=True, null=True, verbose_name=_("Notes"))
    tags = TaggableManager(blank=True, through=Tagged)

    settings = StashSettings(_("Milk stash"))

    objects = models.Manager()

    class Meta:
        default_permissions = ("view", "add", "change", "delete")
        ordering = ["-time"]
        verbose_name = _("Stash adjustment")
        verbose_name_plural = _("Stash adjustments")

    def __str__(self):
        return str(_("Stash adjustment"))

    @property
    def signed_amount(self):
        """The amount as it changes the stash: negative when discarded."""
        return -self.amount if self.kind == "discarded" else self.amount

    def clean(self):
        validate_time(self.time, "time")
        if self.amount is not None and self.amount <= 0:
            raise ValidationError(
                {"amount": _("The amount must be more than zero.")},
                code="amount_invalid",
            )
