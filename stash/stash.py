# -*- coding: utf-8 -*-
"""
The milk stash is worked out, never stored. Pumping marked `to_stash` puts
milk in when it ends, a bottle marked `from_stash` takes milk out when it
starts, and stash adjustments add or discard milk by hand. Editing or deleting
any of them corrects every figure.

Milk leaves the stash oldest first. Milk taken out of an empty stash is a
shortfall that the next milk put in makes up first, so the lots left always add
up to the balance whenever it isn't below zero.

Every movement and every lot carries its source, the record it comes from:
{"type": "pumping" | "feeding" | "stash_adjustment", "id": ...}.
"""

from collections import namedtuple
from datetime import timedelta

from django.utils import timezone

from core.models import Feeding, Pumping

from .models import StashAdjustment

# Lots smaller than this (a rounding remainder) count as empty.
MIN_LOT_AMOUNT = 0.01
STATUSES = ("ok", "warn", "expired")

Move = namedtuple("Move", ("time", "amount", "source"))


def source(source_type, pk):
    return {"type": source_type, "id": pk}


def movements(at=None):
    """
    Every movement of milk up to `at`, oldest first, as Moves with milk taken
    out negative. Milk put in comes before milk taken out at the same time.
    """
    pumping = Pumping.objects.filter(to_stash=True)
    feedings = Feeding.objects.filter(from_stash=True, amount__gt=0)
    adjustments = StashAdjustment.objects.all()
    if at is not None:
        pumping = pumping.filter(end__lte=at)
        feedings = feedings.filter(start__lte=at)
        adjustments = adjustments.filter(time__lte=at)
    moves = [
        Move(end, amount, source("pumping", pk))
        for pk, end, amount in pumping.values_list("id", "end", "amount")
    ]
    moves += [
        Move(start, -amount, source("feeding", pk))
        for pk, start, amount in feedings.values_list("id", "start", "amount")
    ]
    moves += [
        Move(a.time, a.signed_amount, source("stash_adjustment", a.id))
        for a in adjustments.only("id", "time", "amount", "kind")
    ]
    moves.sort(key=lambda move: (move.time, move.amount < 0))
    return moves


def lots(moves):
    """
    The milk still in the stash after `moves`, oldest first, as
    [time, amount, source]: each lot is what is left of one movement in.
    """
    stored = []
    shortfall = 0
    for time, amount, move_source in moves:
        if amount > 0:
            kept = amount - shortfall
            shortfall = max(-kept, 0)
            if kept > 0:
                stored.append([time, kept, move_source])
            continue
        need = -amount
        for lot in stored:
            used = min(lot[1], need)
            lot[1] -= used
            need -= used
            if need <= 0:
                break
        stored = [lot for lot in stored if lot[1] > 0]
        shortfall += need
    return [lot for lot in stored if lot[1] >= MIN_LOT_AMOUNT]


def lot_status(time, at, warn_hours, max_hours):
    age = at - time
    if age >= timedelta(hours=max_hours):
        return "expired"
    if age >= timedelta(hours=warn_hours):
        return "warn"
    return "ok"


def summary(at=None):
    """
    The stash at `at` (now by default): the balance, which may be below zero
    when more was taken out than was put in, the lots oldest first with when
    they expire, and how much of it has expired.
    """
    at = at or timezone.now()
    warn_hours = StashAdjustment.settings.stash_warn_age_hours
    max_hours = StashAdjustment.settings.stash_max_age_hours
    moves = movements(at)
    stash_lots = []
    for time, amount, lot_source in lots(moves):
        stash_lots.append(
            {
                "time": time,
                "amount": round(amount, 2),
                "warn_at": time + timedelta(hours=warn_hours),
                "expires_at": time + timedelta(hours=max_hours),
                "status": lot_status(time, at, warn_hours, max_hours),
                "source": lot_source,
            }
        )
    expired = sum(lot["amount"] for lot in stash_lots if lot["status"] == "expired")
    return {
        "balance": round(sum(move.amount for move in moves), 2),
        "status": max(
            (lot["status"] for lot in stash_lots), key=STATUSES.index, default="ok"
        ),
        "warn_age_hours": warn_hours,
        "max_age_hours": max_hours,
        "expired_amount": round(expired, 2),
        "lots": stash_lots,
    }


def history(limit=10, at=None):
    """
    The last `limit` movements up to `at` (now by default), newest first, each
    with its kind: "pumping" or "added" put milk in, "bottle" or "discarded"
    took it out.
    """
    kinds = {"pumping": "pumping", "feeding": "bottle"}
    recent = []
    for move in reversed(movements(at or timezone.now())[-limit:]):
        kind = kinds.get(move.source["type"])
        if kind is None:
            kind = "added" if move.amount > 0 else "discarded"
        recent.append(
            {
                "time": move.time,
                "amount": round(move.amount, 2),
                "kind": kind,
                "source": move.source,
            }
        )
    return recent


def in_use():
    """Whether the stash was ever used: anything stored or adjusted."""
    return (
        Pumping.objects.filter(to_stash=True).exists()
        or StashAdjustment.objects.exists()
    )
