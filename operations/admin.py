from django.contrib import admin

# Register your models here.
from django.contrib import admin

from .models import (
    Customer,
    Expense,
    Farmer,
    InventoryItem,
    MilkCollection,
    Payment,
    PricingConfiguration,
    StaffMember,
    StockMovement,
    Supplier,
    SupportTicket,
)


@admin.register(Customer)
class CustomerAdmin(admin.ModelAdmin):
    list_display = ('organisation', 'name', 'phone_number', 'branch', 'is_active')
    list_filter = ('organisation', 'is_active')
    search_fields = ('name', 'phone_number')


admin.site.register(Farmer)
admin.site.register(StaffMember)
admin.site.register(PricingConfiguration)
admin.site.register(MilkCollection)
admin.site.register(Payment)
admin.site.register(Expense)
admin.site.register(Supplier)
admin.site.register(InventoryItem)
admin.site.register(StockMovement)
admin.site.register(SupportTicket)
