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


from .models import Account, AccountingPeriod, JournalEntry, JournalLine, LedgerConfiguration


@admin.register(Account)
class AccountAdmin(admin.ModelAdmin):
    list_display = ("code", "name", "organization", "account_type", "normal_balance", "is_active")
    list_filter = ("organization", "account_type", "is_active")
    search_fields = ("code", "name")


@admin.register(AccountingPeriod)
class AccountingPeriodAdmin(admin.ModelAdmin):
    list_display = ("code", "name", "organization", "starts_on", "ends_on", "status")
    list_filter = ("organization", "status")
    search_fields = ("code", "name")


class JournalLineInline(admin.TabularInline):
    model = JournalLine
    extra = 0
    can_delete = False
    readonly_fields = ("entry", "account", "line_number", "description", "debit", "credit")
    fields = readonly_fields


@admin.register(JournalEntry)
class JournalEntryAdmin(admin.ModelAdmin):
    list_display = ("reference", "organization", "entry_date", "description", "status", "posted_at")
    list_filter = ("organization", "status", "entry_date")
    search_fields = ("reference", "description", "source_type", "source_id")
    readonly_fields = (
        "organization", "branch", "period", "reference", "entry_date", "description",
        "source_type", "source_id", "idempotency_key", "status", "created_by",
        "posted_by", "posted_at", "reversal_of", "created_at", "updated_at",
    )
    inlines = [JournalLineInline]

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(LedgerConfiguration)
class LedgerConfigurationAdmin(admin.ModelAdmin):
    list_display = ("organization", "is_enabled", "enable_farmer_collection_posting", "enable_customer_sales_posting")
    list_filter = ("is_enabled", "enable_farmer_collection_posting", "enable_customer_sales_posting")
