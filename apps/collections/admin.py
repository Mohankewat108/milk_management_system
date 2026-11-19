from django.contrib import admin

from .models import MilkCollection


@admin.register(MilkCollection)
class MilkCollectionAdmin(admin.ModelAdmin):
    list_display = (
        "reference",
        "organization",
        "branch",
        "collected_at",
        "quantity_litres",
        "milk_rate",
        "total_amount",
        "status",
    )
    list_filter = ("organization", "branch", "status")
    search_fields = ("reference", "farmer__full_name", "customer__full_name")
    readonly_fields = (
        "organization",
        "branch",
        "reference",
        "farmer",
        "customer",
        "recorded_by",
        "collected_at",
        "quantity_litres",
        "snf",
        "fat",
        "lactose",
        "milk_rate",
        "total_amount",
        "pricing",
        "pricing_snapshot",
        "created_at",
        "updated_at",
    )
