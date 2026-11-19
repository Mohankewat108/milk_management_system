from django import forms

from apps.organizations.models import Branch

from .models import Customer, Farmer


class CustomerForm(forms.ModelForm):
    class Meta:
        model = Customer
        fields = (
            "branch",
            "code",
            "full_name",
            "phone",
            "email",
            "address",
            "city",
            "village",
            "ward",
        )

    def __init__(self, *args, organization, membership=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.organization = organization
        self.fields["branch"].queryset = Branch.objects.filter(
            organization=organization, is_active=True, deleted_at__isnull=True
        )
        self.fields["branch"].required = bool(
            membership and membership.role not in {"owner", "admin"}
        )

    def clean_code(self):
        code = self.cleaned_data["code"].strip()
        existing = Customer.objects.filter(organization=self.organization, code=code)
        if self.instance.pk:
            existing = existing.exclude(pk=self.instance.pk)
        if existing.exists():
            raise forms.ValidationError("This customer code is already used in this organisation.")
        return code


class FarmerForm(forms.ModelForm):
    class Meta:
        model = Farmer
        fields = (
            "branch",
            "code",
            "full_name",
            "phone",
            "email",
            "address",
            "bank_account_name",
            "bank_account_number",
            "bank_name",
        )

    def __init__(self, *args, organization, membership=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.organization = organization
        self.fields["branch"].queryset = Branch.objects.filter(
            organization=organization, is_active=True, deleted_at__isnull=True
        )
        self.fields["branch"].required = bool(
            membership and membership.role not in {"owner", "admin"}
        )

    def clean_code(self):
        code = self.cleaned_data["code"].strip()
        existing = Farmer.objects.filter(organization=self.organization, code=code)
        if self.instance.pk:
            existing = existing.exclude(pk=self.instance.pk)
        if existing.exists():
            raise forms.ValidationError("This farmer code is already used in this organisation.")
        return code
