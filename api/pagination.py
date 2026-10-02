# -*- coding: utf-8 -*-
from rest_framework.pagination import LimitOffsetPagination

EVENT_TYPE_ACTIONS = ("add", "change", "delete", "delete_with_events")


def can_delete_event_type_with_events(user):
    """
    Whether a user may delete an event type together with all of its events.
    """
    return user.has_perm("core.delete_eventtype") and user.has_perm("core.delete_event")


def event_type_permissions(user):
    """
    The event type management actions a user may take, so that clients can
    offer them without working out the permissions themselves.
    """
    permissions = {
        action: user.has_perm("core.{}_eventtype".format(action))
        for action in ("add", "change", "delete")
    }
    permissions["delete_with_events"] = can_delete_event_type_with_events(user)
    return permissions


def with_event_type_permissions(data, user):
    """
    Add the "permissions" key to a paginated list response, before "results".
    """
    data = dict(data)
    results = data.pop("results")
    data["permissions"] = event_type_permissions(user)
    data["results"] = results
    return data


class EventTypePagination(LimitOffsetPagination):
    """
    The default pagination with a "permissions" object on every page, which
    tells the client whether the user may add, change and delete event types.
    """

    def get_paginated_response(self, data):
        response = super().get_paginated_response(data)
        response.data = with_event_type_permissions(response.data, self.request.user)
        return response

    def get_paginated_response_schema(self, schema):
        schema = super().get_paginated_response_schema(schema)
        properties = dict(schema["properties"])
        results = properties.pop("results")
        properties["permissions"] = {
            "type": "object",
            "description": "Whether the user may add, change and delete event "
            "types, and delete a type together with its events.",
            "required": list(EVENT_TYPE_ACTIONS),
            "properties": {
                action: {"type": "boolean", "example": True}
                for action in EVENT_TYPE_ACTIONS
            },
        }
        properties["results"] = results
        schema["properties"] = properties
        schema["required"] = schema["required"] + ["permissions"]
        return schema
