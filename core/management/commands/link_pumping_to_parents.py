# -*- coding: utf-8 -*-
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from core import models


class Command(BaseCommand):
    help = "Move pumping entries that are not linked to a parent onto a parent."

    def add_arguments(self, parser):
        parser.add_argument("--parent", required=True, help="Parent slug")
        parser.add_argument(
            "--child",
            action="append",
            default=[],
            help="Only this child's entries (repeatable)",
        )
        parser.add_argument("--dry-run", action="store_true")

    @transaction.atomic
    def handle(self, *args, **options):
        parent = models.Parent.objects.filter(slug=options["parent"]).first()
        if parent is None:
            raise CommandError("No parent with slug %s" % options["parent"])
        rows = models.Pumping.objects.filter(parent__isnull=True)
        if options["child"]:
            rows = rows.filter(child__slug__in=options["child"])
        children = models.Child.objects.filter(pumping__in=rows).distinct()
        moved = list(rows)
        overlapping = self.count_overlapping(moved, list(parent.pumping.all()))
        if not options["dry_run"]:
            parent.children.add(*children)
            rows.update(parent=parent, child=None)
        self.stdout.write(
            "%s %d pumping entries to %s"
            % ("Would move" if options["dry_run"] else "Moved", len(moved), parent)
        )
        if overlapping:
            self.stdout.write(
                "%d of them %s another pumping entry of %s; check for duplicates."
                % (overlapping, "overlaps" if overlapping == 1 else "overlap", parent)
            )

    @staticmethod
    def count_overlapping(moved, existing):
        """How many moved entries overlap another entry the parent ends up with."""
        entries = existing + moved
        return sum(
            any(
                other.pk != entry.pk
                and other.start < entry.end
                and other.end > entry.start
                for other in entries
            )
            for entry in moved
        )
