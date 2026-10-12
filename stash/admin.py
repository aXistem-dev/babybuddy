# -*- coding: utf-8 -*-
from django.contrib import admin

from import_export import fields, resources
from import_export.admin import ImportExportMixin, ExportActionMixin

from . import models


class StashAdjustmentImportExportResource(resources.ModelResource):
    id = fields.Field(attribute="id")

    class Meta:
        model = models.StashAdjustment
        clean_model_instances = True


@admin.register(models.StashAdjustment)
class StashAdjustmentAdmin(ImportExportMixin, ExportActionMixin, admin.ModelAdmin):
    list_display = ("time", "kind", "amount")
    list_filter = ("kind", "tags")
    search_fields = ("amount", "notes")
    resource_class = StashAdjustmentImportExportResource
