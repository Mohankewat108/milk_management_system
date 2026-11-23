from django import forms
from django.contrib.auth import get_user_model
from django.db.models import Q

from apps.organizations.models import Branch

from .models import Customer, Farmer

User = get_user_model()


def _available_portal_users(instance):
    users = User.objects.filter(is_active=True, is_superuser=False).filter(
        customer_profile__isnull=True,
        farmer_profile__isnull=True,
    )
    if instance.pk and instance.user_id:
        users = User.objects.filter(Q(pk=instance.user_id) | Q(pk__in=users.values("pk")))
    return users.order_by("email")


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
            "user",
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
        self.fields["user"].required = False
        self.fields["user"].label = "Portal login account"
        self.fields[
            "user"
        ].help_text = (
            "Link an existing account so this customer can sign in to the customer portal."
        )
        self.fields["user"].queryset = _available_portal_users(self.instance)

    def clean_code(self):
        code = self.cleaned_data["code"].strip()
        existing = Customer.objects.filter(organization=self.organization, code=code)
        if self.instance.pk:
            existing = existing.exclude(pk=self.instance.pk)
        if existing.exists():
            raise forms.ValidationError("This customer code is already used in this organisation.")
        return code


class FarmerForm(forms.ModelForm):
    send_invitation = forms.BooleanField(
        required=False,
        initial=False,
        label="Send portal invitation to this farmer",
        help_text=(
            "Send a secure email link so the farmer can set a password "
            "and activate their farmer portal account."
        ),
    )

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

    def clean(self):
        cleaned_data = super().clean()
        if cleaned_data.get("send_invitation") and not cleaned_data.get("email"):
            self.add_error(
                "email",
                "An email address is required when sending a portal invitation.",
            )
        return cleaned_data

    def clean_code(self):
        code = self.cleaned_data["code"].strip()
        existing = Farmer.objects.filter(organization=self.organization, code=code)
        if self.instance.pk:
            existing = existing.exclude(pk=self.instance.pk)
        if existing.exists():
            raise forms.ValidationError("This farmer code is already used in this organisation.")
        return code
