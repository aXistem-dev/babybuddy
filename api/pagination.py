# -*- coding: utf-8 -*-
from rest_framework.pagination import LimitOffsetPagination

ACTIVITY_TYPE_ACTIONS = ("add", "change", "delete")


def activity_type_permissions(user):
    """
    The activity type management actions a user may take, so that clients can
    offer them without working out the permissions themselves.
    """
    return {
        action: user.has_perm("core.{}_activitytype".format(action))
        for action in ACTIVITY_TYPE_ACTIONS
    }


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
            "types.",
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
