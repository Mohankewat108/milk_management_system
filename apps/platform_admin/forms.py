from django import forms
from django.contrib.auth import get_user_model

from apps.organizations.models import Organization


User = get_user_model()


class PlatformOrganizationCreateForm(forms.ModelForm):
    owner_first_name = forms.CharField(max_length=150, label="Owner first name")
    owner_last_name = forms.CharField(max_length=150, required=False, label="Owner last name")
    owner_email = forms.EmailField(
        label="Farm owner's email",
        help_text="We will send a secure invitation to this address. The owner will set their own password.",
    )

    class Meta:
        model = Organization
        fields = (
            "name", "legal_name", "registration_number", "business_type",
            "email", "phone", "country", "currency", "timezone", "address",
        )
        widgets = {"address": forms.Textarea(attrs={"rows": 3})}

    def clean_name(self):
        name = self.cleaned_data["name"].strip()
        if not name:
            raise forms.ValidationError("Enter a dairy farm or business name.")
        return name

    def clean_owner_email(self):
        return self.cleaned_data["owner_email"].strip().lower()

    def clean_currency(self):
        return self.cleaned_data["currency"].strip().upper()
