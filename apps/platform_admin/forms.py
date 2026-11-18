from django import forms
from django.contrib.auth import get_user_model

from apps.organizations.models import Organization


User = get_user_model()


class PlatformOrganizationCreateForm(forms.ModelForm):
    owner = forms.ModelChoiceField(
        queryset=User.objects.filter(is_active=True).order_by("email"),
        help_text="Select the account that will own and administer this dairy workspace.",
    )

    class Meta:
        model = Organization
        fields = (
            "owner", "name", "legal_name", "registration_number", "business_type",
            "email", "phone", "country", "currency", "timezone", "address",
        )
        widgets = {
            "address": forms.Textarea(attrs={"rows": 3}),
        }

    def clean_name(self):
        name = self.cleaned_data["name"].strip()
        if not name:
            raise forms.ValidationError("Enter a dairy farm or business name.")
        return name

    def clean_currency(self):
        return self.cleaned_data["currency"].strip().upper()
