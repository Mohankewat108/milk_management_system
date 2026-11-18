from django import forms

from apps.organizations.models import Branch
from .models import PricingConfiguration, QualityConfiguration


class PricingConfigurationForm(forms.ModelForm):
    class Meta:
        model = PricingConfiguration
        fields = ("branch", "snf_rate", "fat_rate", "lactose_rate", "effective_from", "effective_to", "notes")
        widgets = {
            "effective_from": forms.DateInput(attrs={"type": "date"}),
            "effective_to": forms.DateInput(attrs={"type": "date"}),
            "notes": forms.TextInput(attrs={"placeholder": "Reason for this rate change (optional)"}),
        }
        help_texts = {
            "branch": "Leave blank to apply this exact rate schedule to every customer and every branch in this dairy.",
            "snf_rate": "Coefficient multiplied by the measured SNF value.",
            "fat_rate": "Coefficient multiplied by the measured fat value.",
            "lactose_rate": "Coefficient multiplied by the measured lactose value.",
            "effective_from": "The first local business date on which this schedule is used.",
            "effective_to": "Last included date. Leave blank for an open-ended schedule.",
        }

    def __init__(self, *args, organization, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["branch"].required = False
        self.fields["branch"].queryset = Branch.objects.filter(organization=organization, is_active=True, deleted_at__isnull=True)
        self.fields["branch"].empty_label = "All customers and all branches (recommended)"
        for field in ("snf_rate", "fat_rate", "lactose_rate"):
            self.fields[field].min_value = 0

    def clean(self):
        cleaned = super().clean()
        start, end = cleaned.get("effective_from"), cleaned.get("effective_to")
        if start and end and end < start:
            self.add_error("effective_to", "End date must be on or after start date.")
        return cleaned


class QualityConfigurationForm(forms.ModelForm):
    class Meta:
        model = QualityConfiguration
        fields = (
            "branch", "snf_min", "snf_max", "fat_min", "fat_max",
            "lactose_min", "lactose_max", "effective_from", "effective_to",
        )
        widgets = {
            "effective_from": forms.DateInput(attrs={"type": "date"}),
            "effective_to": forms.DateInput(attrs={"type": "date"}),
        }

    def __init__(self, *args, organization, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["branch"].required = False
        self.fields["branch"].queryset = Branch.objects.filter(organization=organization, is_active=True, deleted_at__isnull=True)

    def clean(self):
        cleaned = super().clean()
        for name in ("snf", "fat", "lactose"):
            low, high = cleaned.get(f"{name}_min"), cleaned.get(f"{name}_max")
            if low is not None and high is not None and low > high:
                self.add_error(f"{name}_max", "Maximum must be greater than or equal to minimum.")
        start, end = cleaned.get("effective_from"), cleaned.get("effective_to")
        if start and end and end < start:
            self.add_error("effective_to", "End date must be on or after start date.")
        return cleaned
