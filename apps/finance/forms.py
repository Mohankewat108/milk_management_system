from django import forms

from apps.organizations.models import Branch
from apps.parties.models import Customer, Farmer
from .models import Expense, Payment


class PaymentEntryForm(forms.Form):
    branch = forms.ModelChoiceField(queryset=Branch.objects.none())
    direction = forms.ChoiceField(choices=Payment.Direction.choices)
    party_type = forms.ChoiceField(choices=(("customer", "Customer"), ("farmer", "Farmer")))
    customer = forms.ModelChoiceField(queryset=Customer.objects.none(), required=False)
    farmer = forms.ModelChoiceField(queryset=Farmer.objects.none(), required=False)
    amount = forms.DecimalField(max_digits=14, decimal_places=2, min_value=0.01)
    method = forms.ChoiceField(choices=Payment.Method.choices)
    transaction_reference = forms.CharField(max_length=120, required=False)
    notes = forms.CharField(required=False, widget=forms.Textarea(attrs={"rows": 3}))

    def __init__(self, *args, organization, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["branch"].queryset = Branch.objects.filter(organization=organization, is_active=True)
        self.fields["customer"].queryset = Customer.objects.filter(organization=organization, is_active=True)
        self.fields["farmer"].queryset = Farmer.objects.filter(organization=organization, is_active=True)

    def clean(self):
        cleaned = super().clean()
        kind = cleaned.get("party_type")
        customer, farmer = cleaned.get("customer"), cleaned.get("farmer")
        direction = cleaned.get("direction")
        if kind == "customer" and (customer is None or farmer is not None):
            raise forms.ValidationError("Select exactly one customer.")
        if kind == "farmer" and (farmer is None or customer is not None):
            raise forms.ValidationError("Select exactly one farmer.")
        if kind == "customer" and direction != Payment.Direction.INCOMING:
            raise forms.ValidationError("Customer payments must be incoming.")
        if kind == "farmer" and direction != Payment.Direction.OUTGOING:
            raise forms.ValidationError("Farmer payments must be outgoing.")
        return cleaned


class ExpenseEntryForm(forms.ModelForm):
    class Meta:
        model = Expense
        fields = ("branch", "category", "description", "supplier_name", "amount", "expense_date", "method", "notes")
        widgets = {"expense_date": forms.DateInput(attrs={"type": "date"})}

    def __init__(self, *args, organization, membership, **kwargs):
        super().__init__(*args, **kwargs)
        branches = Branch.objects.filter(organization=organization, is_active=True)
        assignments = membership.branch_assignments.values_list("branch_id", flat=True)
        if membership.role not in {"owner", "admin"}:
            branches = branches.filter(pk__in=assignments)
        self.fields["branch"].queryset = branches


class PaymentEditForm(forms.ModelForm):
    class Meta:
        model = Payment
        fields = ("branch", "amount", "method", "transaction_reference", "notes")

    def __init__(self, *args, organization, membership, **kwargs):
        super().__init__(*args, **kwargs)
        branches = Branch.objects.filter(organization=organization, is_active=True, deleted_at__isnull=True)
        if membership.role not in {"owner", "admin"}:
            branches = branches.filter(pk__in=membership.branch_assignments.values_list("branch_id", flat=True))
        self.fields["branch"].queryset = branches
