from django.contrib import admin

from .models import Customer, Farmer


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
