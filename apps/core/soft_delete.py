"""Tenant-scoped soft deletion for operational master and eligible transaction records.

Financial ledgers and stock movements are deliberately immutable: completed payments,
approved expenses, milk collections and stock movements must be corrected by their
existing reversal/adjustment workflows rather than being hidden or erased.
"""
from django.core.exceptions import ValidationError
from django.utils import timezone

from apps.collections.models import MilkCollection
from apps.finance.models import Expense, Payment
from apps.inventory.models import InventoryItem, Supplier
from apps.organizations.models import Branch
from apps.parties.models import Customer, Farmer
from apps.pricing.models import PricingConfiguration


MODEL_REGISTRY = {
    "customer": (Customer, "Customer"),
    "farmer": (Farmer, "Farmer"),
    "branch": (Branch, "Branch"),
    "supplier": (Supplier, "Supplier"),
    "inventory_item": (InventoryItem, "Inventory item"),
    "payment": (Payment, "Payment"),
    "expense": (Expense, "Expense"),
    "pricing": (PricingConfiguration, "Pricing schedule"),
}


def get_registered_model(key):
    try:
        return MODEL_REGISTRY[key][0]
    except KeyError as exc:
        raise ValidationError("Unsupported record type.") from exc


def soft_delete_record(*, key, record, actor):
    if record.deleted_at:
        raise ValidationError("This record is already in Trash.")

    if isinstance(record, Payment) and record.status not in {
        Payment.Status.PENDING, Payment.Status.FAILED,
    }:
        raise ValidationError("Completed or reversed payments cannot be deleted. Use the finance reversal workflow.")
    if isinstance(record, PricingConfiguration):
        if record.is_approved or record.collections.exists():
            raise ValidationError("Approved or referenced rate schedules are retained for historical pricing and cannot be deleted.")
    if isinstance(record, Expense) and record.status == Expense.Status.APPROVED:
        raise ValidationError("Approved expenses are retained for audit and cannot be deleted.")
    if isinstance(record, InventoryItem):
        if record.current_stock != 0:
            raise ValidationError("An inventory item must have zero stock before it can be moved to Trash.")
        if record.movements.exists():
            raise ValidationError("This item has stock movement history. Deactivate it instead of deleting its history.")
    if isinstance(record, Branch):
        if (
            record.milk_collections.exists() or record.payments.exists() or record.customers.exists() or record.farmers.exists()
            or record.expenses.exists() or record.inventory_items.exists()
        ):
            raise ValidationError("This branch has operational history. Deactivate it instead of deleting its history.")

    record.deleted_at = timezone.now()
    record.deleted_by = actor
    record.save(update_fields=["deleted_at", "deleted_by", "updated_at"])


def restore_record(*, record):
    if not record.deleted_at:
        raise ValidationError("This record is not in Trash.")
    record.deleted_at = None
    record.deleted_by = None
    record.save(update_fields=["deleted_at", "deleted_by", "updated_at"])


def display_record(record):
    return (
        getattr(record, "full_name", None)
        or getattr(record, "name", None)
        or getattr(record, "reference", None)
        or getattr(record, "code", None)
        or str(record.pk)
    )
