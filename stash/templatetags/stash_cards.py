# -*- coding: utf-8 -*-
from django import template

from stash import stash

register = template.Library()


@register.inclusion_tag("cards/stash.html", takes_context=True)
def card_stash(context):
    """
    The milk stash: its balance and whether any milk is expiring. Shown only
    once the stash has been used, so it stays off the dashboard otherwise.
    :returns: a dictionary with the stash summary.
    """
    used = stash.in_use()
    return {
        "type": "pumping",
        "summary": stash.summary() if used else None,
        "empty": not used,
        "hide_empty": True,
    }
