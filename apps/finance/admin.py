from django.contrib import admin

from .models import Expense, Payment


@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = ("reference", "organization", "direction", "amount", "currency", "status", "paid_at")
    list_filter = ("organization", "direction", "status", "method")
    search_fields = ("reference", "transaction_reference")


@admin.register(Expense)
class ExpenseAdmin(admin.ModelAdmin):
    list_display = ("reference", "organization", "branch", "category", "amount", "currency", "status", "expense_date")
    list_filter = ("organization", "status", "category", "method")
    search_fields = ("reference", "description", "supplier_name")
    readonly_fields = ("organization", "branch", "reference", "category", "description",
                       "supplier_name", "amount", "currency", "expense_date", "method",
                       "recorded_by", "approved_by", "approved_at", "created_at", "updated_at")
