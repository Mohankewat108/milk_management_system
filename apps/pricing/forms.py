from django import forms

from apps.organizations.models import Branch
from .models import PricingConfiguration


class PricingConfigurationForm(forms.ModelForm):
    class Meta:
        model = PricingConfiguration
        fields = ("branch", "snf_rate", "fat_rate", "lactose_rate", "effective_from", "effective_to")
        widgets = {
            "effective_from": forms.DateInput(attrs={"type": "date"}),
            "effective_to": forms.DateInput(attrs={"type": "date"}),
        }

    def __init__(self, *args, organization, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["branch"].required = False
        self.fields["branch"].queryset = Branch.objects.filter(
            organization=organization, is_active=True
        )
