from django.contrib import admin

from .models import Payment


@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = ("reference", "organization", "direction", "amount", "currency", "status", "paid_at")
    list_filter = ("organization", "direction", "status", "method")
    search_fields = ("reference", "transaction_reference")
