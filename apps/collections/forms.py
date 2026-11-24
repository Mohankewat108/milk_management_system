import secrets

from django import forms

from apps.organizations.models import Branch
from apps.parties.models import Customer, Farmer


class CollectionEntryForm(forms.Form):
    idempotency_key = forms.CharField(
        max_length=64, initial=lambda: secrets.token_urlsafe(32), widget=forms.HiddenInput
    )
    branch = forms.ModelChoiceField(queryset=Branch.objects.none())
    party_type = forms.ChoiceField(choices=(("farmer", "Farmer"), ("customer", "Customer")))
    farmer = forms.ModelChoiceField(queryset=Farmer.objects.none(), required=False)
    customer = forms.ModelChoiceField(queryset=Customer.objects.none(), required=False)
    collected_at = forms.DateTimeField(widget=forms.DateTimeInput(attrs={"type": "datetime-local"}))
    quantity_litres = forms.DecimalField(max_digits=12, decimal_places=3, min_value=0.001)
    snf = forms.DecimalField(max_digits=7, decimal_places=3, min_value=0)
    fat = forms.DecimalField(max_digits=7, decimal_places=3, min_value=0)
    lactose = forms.DecimalField(max_digits=7, decimal_places=3, min_value=0)
    lactometer_reading = forms.DecimalField(
        max_digits=8,
        decimal_places=3,
        min_value=0,
        required=False,
        help_text="Optional. Record the actual instrument reading and use a consistent unit.",
    )
    milk_temperature_c = forms.DecimalField(max_digits=6, decimal_places=2, required=False)
    sample_reference = forms.CharField(max_length=64, required=False)
    quality_test_method = forms.CharField(max_length=80, required=False)
    notes = forms.CharField(required=False, widget=forms.Textarea(attrs={"rows": 3}))

    def __init__(self, *args, organization, membership=None, **kwargs):
        super().__init__(*args, **kwargs)
        branches = Branch.objects.filter(
            organization=organization, is_active=True, deleted_at__isnull=True
        )
        farmers = Farmer.objects.filter(
            organization=organization, is_active=True, deleted_at__isnull=True
        )
        customers = Customer.objects.filter(
            organization=organization, is_active=True, deleted_at__isnull=True
        )

        # Match the same branch visibility rules used by the collection service.
        if membership is not None:
            from apps.organizations.permissions import accessible_branch_ids

            branch_ids = accessible_branch_ids(membership)
            if branch_ids is not None:
                branches = branches.filter(pk__in=branch_ids)
                farmers = farmers.filter(branch_id__in=branch_ids)
                customers = customers.filter(branch_id__in=branch_ids)

        self.fields["branch"].queryset = branches.order_by("name")
        self.fields["farmer"].queryset = farmers.order_by("full_name")
        self.fields["customer"].queryset = customers.order_by("full_name")
        self.fields["party_type"].widget.attrs.update(
            {"class": "collection-party-type", "data-collection-party-type": "true"}
        )
        self.fields["farmer"].widget.attrs.update(
            {"class": "collection-party-select", "data-collection-party": "farmer"}
        )
        self.fields["customer"].widget.attrs.update(
            {"class": "collection-party-select", "data-collection-party": "customer"}
        )

    def clean(self):
        cleaned = super().clean()
        kind = cleaned.get("party_type")
        farmer, customer = cleaned.get("farmer"), cleaned.get("customer")
        if kind == "farmer" and (farmer is None or customer is not None):
            raise forms.ValidationError("Choose one farmer and no customer.")
        if kind == "customer" and (customer is None or farmer is not None):
            raise forms.ValidationError("Choose one customer and no farmer.")

        branch = cleaned.get("branch")
        party = farmer if kind == "farmer" else customer
        if branch and party and party.branch_id and party.branch_id != branch.pk:
            raise forms.ValidationError(
                "The selected farmer/customer belongs to a different branch. "
                "Choose the party's branch or select a party assigned to this branch."
            )
        return cleaned


class CollectionEditForm(forms.Form):
    """Edit operational measurements while retaining historical pricing."""

    quantity_litres = forms.DecimalField(max_digits=12, decimal_places=3, min_value=0.001)
    snf = forms.DecimalField(max_digits=7, decimal_places=3, min_value=0)
    fat = forms.DecimalField(max_digits=7, decimal_places=3, min_value=0)
    lactose = forms.DecimalField(max_digits=7, decimal_places=3, min_value=0)
    lactometer_reading = forms.DecimalField(
        max_digits=8, decimal_places=3, min_value=0, required=False
    )
    milk_temperature_c = forms.DecimalField(max_digits=6, decimal_places=2, required=False)
    sample_reference = forms.CharField(max_length=64, required=False)
    quality_test_method = forms.CharField(max_length=80, required=False)
    notes = forms.CharField(required=False, widget=forms.Textarea(attrs={"rows": 3}))

    def __init__(self, *args, instance, **kwargs):
        self.instance = instance
        initial = {
            "quantity_litres": instance.quantity_litres,
            "snf": instance.snf,
            "fat": instance.fat,
            "lactose": instance.lactose,
            "lactometer_reading": instance.lactometer_reading,
            "milk_temperature_c": instance.milk_temperature_c,
            "sample_reference": instance.sample_reference,
            "quality_test_method": instance.quality_test_method,
            "notes": instance.notes,
        }
        initial.update(kwargs.pop("initial", {}))
        super().__init__(*args, initial=initial, **kwargs)
