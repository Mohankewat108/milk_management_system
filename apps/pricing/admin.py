from django.contrib import admin

from .models import PricingConfiguration


@admin.register(PricingConfiguration)
class PricingConfigurationAdmin(admin.ModelAdmin):
    list_display = ("organization", "branch", "version", "effective_from", "effective_to", "is_approved")
    list_filter = ("is_approved", "organization")
    readonly_fields = ("created_at", "updated_at")
