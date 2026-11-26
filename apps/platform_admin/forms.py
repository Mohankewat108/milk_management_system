from django import forms
from django.contrib.auth import get_user_model

from apps.organizations.models import Organization
from apps.platform_admin.models import SubscriptionPlan

User = get_user_model()


class PlatformOrganizationCreateForm(forms.ModelForm):
    subscription_plan = forms.ModelChoiceField(
        queryset=SubscriptionPlan.objects.none(),
        label="Subscription plan",
        help_text="Choose the plan attached to this dairy. Its 14-day trial starts today.",
    )
    invitation_method = forms.ChoiceField(
        choices=(
            ("email", "Email invitation (owner has email)"),
            ("manual", "Manual account (owner has no email)"),
        ),
        initial="email",
        required=False,
        label="Account setup method",
    )
    owner_first_name = forms.CharField(max_length=150, label="Owner first name")
    owner_last_name = forms.CharField(max_length=150, required=False, label="Owner last name")
    manual_username = forms.CharField(max_length=150, required=False, label="Login username")
    manual_password = forms.CharField(
        required=False,
        label="Temporary password",
        widget=forms.PasswordInput(render_value=True),
        help_text="Set a strong temporary password and give it directly to the farm owner.",
    )
    owner_email = forms.EmailField(
        label="Farm owner's email",
        required=False,
        help_text=(
            "We will send a secure invitation to this address. "
            "The owner will set their own password."
        ),
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["subscription_plan"].queryset = SubscriptionPlan.objects.filter(
            is_active=True
        ).order_by("monthly_price")

    class Meta:
        model = Organization
        fields = (
            "name",
            "legal_name",
            "registration_number",
            "business_type",
            "email",
            "phone",
            "country",
            "currency",
            "timezone",
            "address",
        )
        widgets = {"address": forms.Textarea(attrs={"rows": 3})}

    def clean(self):
        cleaned = super().clean()
        method = cleaned.get("invitation_method") or "email"
        email = cleaned.get("owner_email", "").strip().lower()
        username = cleaned.get("manual_username", "").strip()
        password = cleaned.get("manual_password", "")
        if method == "email" and not email:
            self.add_error(
                "owner_email", "Enter the owner's email address for an email invitation."
            )
        if method == "manual":
            if not username:
                self.add_error("manual_username", "Enter a login username for the farm owner.")
            elif User.objects.filter(username__iexact=username).exists():
                self.add_error("manual_username", "This username is already in use.")
            if len(password) < 12:
                self.add_error(
                    "manual_password", "Temporary password must be at least 12 characters."
                )
        return cleaned

    def clean_name(self):
        name = self.cleaned_data["name"].strip()
        if not name:
            raise forms.ValidationError("Enter a dairy farm or business name.")
        return name

    def clean_owner_email(self):
        return self.cleaned_data.get("owner_email", "").strip().lower()

    def clean_currency(self):
        return self.cleaned_data["currency"].strip().upper()
