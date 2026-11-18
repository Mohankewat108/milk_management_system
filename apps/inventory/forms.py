from django import forms

from apps.organizations.models import Branch
from .models import InventoryItem, StockMovement, Supplier


class SupplierForm(forms.ModelForm):
    class Meta:
        model = Supplier
        fields = ("code", "name", "contact_name", "phone", "email", "address", "tax_number")

    def __init__(self, *args, organization, **kwargs):
        super().__init__(*args, **kwargs)
        self.organization = organization

    def clean_code(self):
        code = self.cleaned_data["code"].strip()
        existing = Supplier.objects.filter(organization=self.organization, code=code)
        if self.instance.pk:
            existing = existing.exclude(pk=self.instance.pk)
        if existing.exists():
            raise forms.ValidationError("This supplier code is already used in this organisation.")
        return code


class InventoryItemForm(forms.ModelForm):
    class Meta:
        model = InventoryItem
        fields = ("branch", "supplier", "code", "name", "category", "unit", "reorder_level", "purchase_price")

    def __init__(self, *args, organization, membership, **kwargs):
        super().__init__(*args, **kwargs)
        self.organization = organization
        branches = Branch.objects.filter(organization=organization, is_active=True)
        assignments = membership.branch_assignments.values_list("branch_id", flat=True)
        if membership.role not in {"owner", "admin"}:
            branches = branches.filter(pk__in=assignments)
        self.fields["branch"].queryset = branches
        self.fields["supplier"].queryset = Supplier.objects.filter(organization=organization, is_active=True)
        self.fields["supplier"].required = False

    def clean_code(self):
        code = self.cleaned_data["code"].strip()
        existing = InventoryItem.objects.filter(organization=self.organization, code=code)
        if self.instance.pk:
            existing = existing.exclude(pk=self.instance.pk)
        if existing.exists():
            raise forms.ValidationError("This item code is already used in this organisation.")
        return code


class StockMovementForm(forms.Form):
    item = forms.ModelChoiceField(queryset=InventoryItem.objects.none())
    kind = forms.ChoiceField(choices=[
        choice for choice in StockMovement.Kind.choices
        if choice[0] != StockMovement.Kind.ADJUSTMENT
    ])
    quantity = forms.DecimalField(max_digits=14, decimal_places=3, min_value=0.001)
    reason = forms.CharField(max_length=240)
    reference = forms.CharField(max_length=100, required=False)

    def __init__(self, *args, organization, membership, **kwargs):
        super().__init__(*args, **kwargs)
        items = InventoryItem.objects.filter(organization=organization, is_active=True).select_related("branch")
        assignments = membership.branch_assignments.values_list("branch_id", flat=True)
        if membership.role not in {"owner", "admin"}:
            items = items.filter(branch_id__in=assignments)
        self.fields["item"].queryset = items
