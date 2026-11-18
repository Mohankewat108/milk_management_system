from django import forms

from apps.organizations.models import Branch
from .models import Customer, Farmer


class CustomerForm(forms.ModelForm):
    class Meta:
        model = Customer
        fields = ("branch", "code", "full_name", "phone", "email", "address", "city", "village", "ward")

    def __init__(self, *args, organization, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["branch"].queryset = Branch.objects.filter(organization=organization, is_active=True)
        self.fields["branch"].required = False


class FarmerForm(forms.ModelForm):
    class Meta:
        model = Farmer
        fields = ("branch", "code", "full_name", "phone", "email", "address",
                  "bank_account_name", "bank_account_number", "bank_name")

    def __init__(self, *args, organization, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["branch"].queryset = Branch.objects.filter(organization=organization, is_active=True)
        self.fields["branch"].required = False
