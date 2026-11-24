from django.contrib import admin

from .models import Customer, Farmer, FarmerNfcCard


@admin.register(Customer)
class CustomerAdmin(admin.ModelAdmin):
    list_display = ("code", "full_name", "organization", "branch", "phone", "is_active")
    list_filter = ("organization", "is_active")
    search_fields = ("code", "full_name", "phone", "email")


@admin.register(Farmer)
class FarmerAdmin(admin.ModelAdmin):
    list_display = ("code", "full_name", "organization", "branch", "phone", "is_active")
    list_filter = ("organization", "is_active")
    search_fields = ("code", "full_name", "phone", "email")


@admin.register(FarmerNfcCard)
class FarmerNfcCardAdmin(admin.ModelAdmin):
    list_display = ("card_uid", "farmer", "status", "issued_at", "revoked_at")
    list_filter = ("status",)
    search_fields = ("card_uid", "farmer__code", "farmer__full_name", "farmer__phone")
