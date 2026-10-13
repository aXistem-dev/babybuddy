# -*- coding: utf-8 -*-
from django.apps import AppConfig
from django.conf import settings
from django.db.models.signals import post_migrate
from django.utils.translation import gettext_lazy as _


def add_read_only_group_permissions(sender, **kwargs):
    """
    Let read only users see the stash, as they see everything in `core`.
    Caregivers get nothing here, as with pumping: a caregiver can still mark a
    bottle as taken from the stash, and keeping the stash stays with the
    parents.
    """
    from django.contrib.auth.models import Group, Permission

    permission = Permission.objects.filter(
        content_type__app_label="stash", codename="view_stashadjustment"
    ).first()
    group = Group.objects.filter(
        name=settings.BABY_BUDDY["READ_ONLY_GROUP_NAME"]
    ).first()
    if permission is not None and group is not None:
        group.permissions.add(permission)


class StashConfig(AppConfig):
    name = "stash"
    verbose_name = _("Milk stash")

    def ready(self):
        # No `sender` filter, for the same reason as in `core.apps`: the
        # permissions and the groups only exist part way through the
        # `post_migrate` sequence, and adding them again is harmless.
        post_migrate.connect(
            add_read_only_group_permissions,
            dispatch_uid="stash.add_read_only_group_permissions",
        )
