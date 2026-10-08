# -*- coding: utf-8 -*-
"""The milk stash is derived, never stored. Every figure is recomputed from
Pumping.stash_amount (in), Feeding.stash_amount (out) and StashAdjustment rows, so
editing or deleting any of them corrects every total automatically."""

from dataclasses import dataclass
from datetime import datetime, timedelta

from django.db.models import Sum
from django.utils import timezone
from django.utils.translation import gettext as _

from core import models

EPSILON = 1e-9
MIN_LOT_AMOUNT = 0.01  # lots smaller than this are treated as empty
STATUS_ORDER = {"ok": 0, "warn": 1, "expired": 2}


@dataclass(frozen=True)
class StashEvent:
    time: datetime
    amount: float
    kind: str
    obj: object


@dataclass
class StashLot:
    time: datetime
    amount: float
    # Whose milk it is: the pumping's parent, or an "added" entry's.
    parent_id: int = None

    def age_hours(self, at=None):
        return ((at or timezone.now()) - self.time).total_seconds() / 3600


def settings():
    return models.Pumping.stash_settings


def stash_use_by_child(start=None, end=None):
    """Ml taken from the stash per baby: feedings with a `stash_amount` set,
    grouped by child in one aggregate query. Discards are never attributed to
    a baby, since a `StashAdjustment` has no child.
    :returns: a dict of child id -> ml, for children with any use in the
    window.
    """
    feedings = models.Feeding.objects.filter(stash_amount__isnull=False)
    if start:
        feedings = feedings.filter(start__gte=start)
    if end:
        feedings = feedings.filter(start__lte=end)
    totals = feedings.values("child_id").annotate(total=Sum("stash_amount"))
    return {row["child_id"]: round(row["total"], 2) for row in totals}


def stash_has_activity():
    return (
        models.Pumping.objects.filter(stash_amount__isnull=False).exists()
        or models.StashAdjustment.objects.exists()
    )


def follow_or_clamp_stash_amount(stash_amount, old_amount, new_amount):
    """The stash amount to keep when an edit changes `amount` but leaves the
    stash amount alone: an entry that was fully stashed follows the new amount,
    and one that would exceed the new amount shrinks to it. A partial stash
    amount that still fits (or no stash amount) is kept as it is."""
    if stash_amount is None or new_amount is None:
        return stash_amount
    if stash_amount == old_amount or stash_amount > new_amount:
        return new_amount
    return stash_amount


def stash_events(start=None, end=None):
    pumping = models.Pumping.objects.filter(stash_amount__isnull=False).select_related(
        "parent", "child"
    )
    feedings = models.Feeding.objects.filter(stash_amount__isnull=False).select_related(
        "child"
    )
    adjustments = models.StashAdjustment.objects.select_related("parent", "feeding")
    if start:
        pumping = pumping.filter(end__gte=start)
        feedings = feedings.filter(start__gte=start)
        adjustments = adjustments.filter(time__gte=start)
    if end:
        pumping = pumping.filter(end__lte=end)
        feedings = feedings.filter(start__lte=end)
        adjustments = adjustments.filter(time__lte=end)
    events = [StashEvent(p.end, p.stash_amount, "pumping", p) for p in pumping]
    events += [StashEvent(f.start, -f.stash_amount, "feeding", f) for f in feedings]
    events += [StashEvent(a.time, a.signed_amount, a.kind, a) for a in adjustments]
    events.sort(key=lambda e: (e.time, e.amount < 0))  # in before out at an equal time
    return events


def _stash_balance_from_events(events):
    """Compute balance from a list of events."""
    return round(sum(e.amount for e in events), 2)


def _negative_since_from_events(events):
    """When the balance last dropped below zero, or None while it is not
    below zero. A new dip after the balance recovered gets a new time."""
    running = 0
    since = None
    for event in events:
        was_negative = round(running, 2) < 0
        running += event.amount
        is_negative = round(running, 2) < 0
        if is_negative and not was_negative:
            since = event.time
        elif not is_negative:
            since = None
    return since


def _event_parent_id(event):
    """The parent a stash event belongs to: a pumping's parent, or the parent
    set on a stash entry. Bottles have none."""
    if event.kind == "feeding":
        return None
    return event.obj.parent_id


def _take_oldest(lots, need, parent_id=None):
    """Take `need` ml from the oldest lots, only `parent_id`'s when given.
    Returns how much could not be taken."""
    for lot in lots:
        if need <= EPSILON:
            break
        if parent_id is not None and lot.parent_id != parent_id:
            continue
        used = min(lot.amount, need)
        lot.amount -= used
        need -= used
    lots[:] = [lot for lot in lots if lot.amount > EPSILON]
    return need


def _stash_lots_from_events(events):
    """Compute FIFO lots from a list of events.

    Every outflow takes the oldest milk first. A discard with a parent takes
    that parent's oldest milk first, and only then anyone's; one logged at a
    bottle follows the bottle and takes anyone's oldest. Milk that left an
    empty stash is a shortfall that later inflows repay first, so the lots
    always add up to the (non-negative) balance."""
    lots = []
    shortfall = 0
    for event in events:
        if event.amount > 0:
            amount = event.amount - shortfall
            shortfall = max(-amount, 0)
            if amount > EPSILON:
                lots.append(StashLot(event.time, amount, _event_parent_id(event)))
            continue
        need = -event.amount
        parent_id = _event_parent_id(event)
        if (
            event.kind == "discarded"
            and parent_id is not None
            and event.obj.feeding_id is None
        ):
            need = _take_oldest(lots, need, parent_id)
        need = _take_oldest(lots, need)
        if need > EPSILON:
            shortfall += need
    return [lot for lot in lots if lot.amount >= MIN_LOT_AMOUNT]


def stash_balance(at=None):
    return _stash_balance_from_events(stash_events(end=at))


def stash_lots(at=None):
    """Milk still in the stash, oldest first. Every outflow uses the oldest milk first."""
    return _stash_lots_from_events(stash_events(end=at))


def lot_status(age_hours, warn, max_):
    if age_hours >= max_:
        return "expired"
    if age_hours >= warn:
        return "warn"
    return "ok"


def stash_summary(at=None):
    at = at or timezone.now()
    s = settings()
    warn, max_ = s.stash_warn_age_hours, s.stash_max_age_hours

    # Fetch events once and derive both balance and lots
    events = stash_events(end=at)
    balance = _stash_balance_from_events(events)
    negative_since = _negative_since_from_events(events)
    fifo_lots = _stash_lots_from_events(events)

    lots = []
    oldest_expired_seen = False
    for lot in fifo_lots:
        # Use unrounded age for status classification, rounded for display
        age_exact = lot.age_hours(at)
        age_rounded = round(age_exact, 1)
        lot_status_ = lot_status(age_exact, warn, max_)
        # FIFO removes milk from the oldest lot first, so a per-lot
        # "Throw away" link only makes sense on the oldest expired one.
        is_oldest_expired = lot_status_ == "expired" and not oldest_expired_seen
        oldest_expired_seen = oldest_expired_seen or lot_status_ == "expired"
        lots.append(
            {
                "time": lot.time,
                "amount": round(lot.amount, 2),
                "parent": lot.parent_id,
                # Kept unrounded so a "Throw away" link empties the lot
                # exactly, instead of leaving a sliver behind.
                "throw_away_amount": lot.amount,
                "age_hours": age_rounded,
                "warn_at": lot.time + timedelta(hours=warn),
                "expires_at": lot.time + timedelta(hours=max_),
                "status": lot_status_,
                "is_oldest_expired": is_oldest_expired,
            }
        )
    status = max((l["status"] for l in lots), key=STATUS_ORDER.get, default="ok")
    # The stash is in use (see stash_has_activity); stored or adjusted milk
    # among the events already fetched saves the query.
    bottle_from_stash = s.bottle_from_stash_default and (
        any(e.kind != "feeding" for e in events) or stash_has_activity()
    )
    return {
        "balance": balance,
        # Identifies the current dip below zero, so a dismissed warning comes
        # back for the next one.
        "negative_since": negative_since,
        "status": status,
        "warn_age_hours": warn,
        "max_age_hours": max_,
        "oldest": lots[0]["time"] if lots else None,
        "oldest_age_hours": lots[0]["age_hours"] if lots else None,
        "lots": lots,
        # Clients (iOS) pre-set their switches from these, like the web forms
        # do: a bottle only starts as taken from the stash once it is in use.
        "defaults": {
            "pumping_to_stash": s.pumping_to_stash_default,
            "bottle_from_stash": bottle_from_stash,
        },
    }


def expired_amount(summary):
    """The millilitres in a stash summary's expired lots, unrounded so a
    "Throw away all expired milk" link empties them exactly."""
    return sum(
        lot["throw_away_amount"]
        for lot in summary["lots"]
        if lot["status"] == "expired"
    )


def throw_away_reason(summary):
    """The reason pre-filled when expired milk is thrown away."""
    return _("Older than %(hours)s h") % {"hours": summary["max_age_hours"]}
