from django.contrib import admin

from .models import InventoryItem, StockMovement, Supplier


@admin.register(Supplier)
class SupplierAdmin(admin.ModelAdmin):
    list_display = ("code", "name", "organization", "phone", "is_active")
    list_filter = ("organization", "is_active")
    search_fields = ("code", "name", "phone", "email")


@admin.register(InventoryItem)
class InventoryItemAdmin(admin.ModelAdmin):
    list_display = ("code", "name", "organization", "branch", "current_stock", "reorder_level", "is_active")
    list_filter = ("organization", "branch", "is_active")
    search_fields = ("code", "name")


@admin.register(StockMovement)
class StockMovementAdmin(admin.ModelAdmin):
    list_display = ("created_at", "organization", "item", "kind", "quantity_delta", "created_by")
    list_filter = ("organization", "kind")
    readonly_fields = ("organization", "item", "kind", "quantity_delta", "reason", "reference", "created_by", "created_at")

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
