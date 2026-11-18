from django import forms

from apps.organizations.models import Branch
from apps.parties.models import Customer, Farmer


class CollectionEntryForm(forms.Form):
    branch = forms.ModelChoiceField(queryset=Branch.objects.none())
    party_type = forms.ChoiceField(choices=(("farmer", "Farmer"), ("customer", "Customer")))
    farmer = forms.ModelChoiceField(queryset=Farmer.objects.none(), required=False)
    customer = forms.ModelChoiceField(queryset=Customer.objects.none(), required=False)
    collected_at = forms.DateTimeField(widget=forms.DateTimeInput(attrs={"type": "datetime-local"}))
    quantity_litres = forms.DecimalField(max_digits=12, decimal_places=3, min_value=0.001)
    snf = forms.DecimalField(max_digits=7, decimal_places=3, min_value=0)
    fat = forms.DecimalField(max_digits=7, decimal_places=3, min_value=0)
    lactose = forms.DecimalField(max_digits=7, decimal_places=3, min_value=0)
    notes = forms.CharField(required=False, widget=forms.Textarea(attrs={"rows": 3}))

    def __init__(self, *args, organization, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["branch"].queryset = Branch.objects.filter(organization=organization, is_active=True)
        self.fields["farmer"].queryset = Farmer.objects.filter(organization=organization, is_active=True)
        self.fields["customer"].queryset = Customer.objects.filter(organization=organization, is_active=True)

    def clean(self):
        cleaned = super().clean()
        kind = cleaned.get("party_type")
        farmer, customer = cleaned.get("farmer"), cleaned.get("customer")
        if kind == "farmer" and (farmer is None or customer is not None):
            raise forms.ValidationError("Choose one farmer and no customer.")
        if kind == "customer" and (customer is None or farmer is not None):
            raise forms.ValidationError("Choose one customer and no farmer.")
        return cleaned
