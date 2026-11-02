# -*- coding: utf-8 -*-
from django.urls import path

from . import views

app_name = "stash"

urlpatterns = [
    path("stash/", views.Stash.as_view(), name="stash"),
    path(
        "stash/adjustments/",
        views.StashAdjustmentList.as_view(),
        name="stashadjustment-list",
    ),
    path(
        "stash/adjustments/add/",
        views.StashAdjustmentAdd.as_view(),
        name="stashadjustment-add",
    ),
    path(
        "stash/adjustments/<int:pk>/",
        views.StashAdjustmentUpdate.as_view(),
        name="stashadjustment-update",
    ),
    path(
        "stash/adjustments/<int:pk>/delete/",
        views.StashAdjustmentDelete.as_view(),
        name="stashadjustment-delete",
    ),
]
