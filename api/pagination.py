# -*- coding: utf-8 -*-
from rest_framework.pagination import LimitOffsetPagination

ACTIVITY_TYPE_ACTIONS = ("add", "change", "delete", "delete_with_activities")


def can_delete_activity_type_with_activities(user):
    """
    Whether a user may delete an activity type together with its activities.
    """
    return user.has_perm("core.delete_activitytype") and user.has_perm(
        "core.delete_activity"
    )


def activity_type_permissions(user):
    """
    The activity type management actions a user may take, so that clients can
    offer them without working out the permissions themselves.
    """
    permissions = {
        action: user.has_perm("core.{}_activitytype".format(action))
        for action in ("add", "change", "delete")
    }
    permissions["delete_with_activities"] = can_delete_activity_type_with_activities(
        user
    )
    return permissions


def with_activity_type_permissions(data, user):
    """
    Add the "permissions" key to a paginated list response, before "results".
    """
    data = dict(data)
    results = data.pop("results")
    data["permissions"] = activity_type_permissions(user)
    data["results"] = results
    return data


class ActivityTypePagination(LimitOffsetPagination):
    """
    The default pagination with a "permissions" object on every page, which
    tells the client whether the user may add, change and delete activity
    types.
    """

    def get_paginated_response(self, data):
        response = super().get_paginated_response(data)
        response.data = with_activity_type_permissions(response.data, self.request.user)
        return response

    def get_paginated_response_schema(self, schema):
        schema = super().get_paginated_response_schema(schema)
        properties = dict(schema["properties"])
        results = properties.pop("results")
        properties["permissions"] = {
            "type": "object",
            "description": "Whether the user may add, change and delete activity "
            "types, and delete a type together with its activities.",
            "required": list(ACTIVITY_TYPE_ACTIONS),
            "properties": {
                action: {"type": "boolean", "example": True}
                for action in ACTIVITY_TYPE_ACTIONS
            },
        }
        properties["results"] = results
        schema["properties"] = properties
        schema["required"] = schema["required"] + ["permissions"]
        return schema
