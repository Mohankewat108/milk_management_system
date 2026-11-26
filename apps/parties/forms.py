import secrets

from django import forms
from django.contrib.auth import get_user_model
from django.db.models import Q

from apps.organizations.models import Branch
from apps.organizations.permissions import accessible_branch_ids

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
        branches = Branch.objects.filter(
            organization=organization, is_active=True, deleted_at__isnull=True
        )
        if membership is not None:
            allowed_branch_ids = accessible_branch_ids(membership)
            if allowed_branch_ids is not None:
                branches = branches.filter(pk__in=allowed_branch_ids)
        self.fields["branch"].queryset = branches
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
            "is_active",
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
        if not self.instance.pk:
            self.fields["code"].required = False
            self.fields[
                "code"
            ].help_text = "Leave blank to generate a unique Farmer ID automatically."
            self.fields["code"].widget.attrs["placeholder"] = "Auto-generated if left blank"

    def clean_code(self):
        code = (self.cleaned_data.get("code") or "").strip()
        if not code and not self.instance.pk:
            for _ in range(10):
                candidate = f"FRM-{secrets.token_hex(4).upper()}"
                if not Farmer.objects.filter(
                    organization=self.organization, code=candidate
                ).exists():
                    code = candidate
                    break
            if not code:
                raise forms.ValidationError(
                    "Could not generate a unique Farmer ID. Please try again."
                )
        existing = Farmer.objects.filter(organization=self.organization, code=code)
        if self.instance.pk:
            existing = existing.exclude(pk=self.instance.pk)
        if code and existing.exists():
            raise forms.ValidationError("This farmer code is already used in this organisation.")
        return code
