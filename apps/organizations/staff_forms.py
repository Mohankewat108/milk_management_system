from django import forms

from .models import Branch, Membership, OrganizationPermission

STAFF_ROLE_CHOICES = [
    (Membership.Role.DAIRY_MANAGER, "Dairy manager"),
    (Membership.Role.BRANCH_MANAGER, "Branch manager"),
    (Membership.Role.COLLECTION_OPERATOR, "Milk collection operator"),
    (Membership.Role.QUALITY_OFFICER, "Quality officer"),
    (Membership.Role.ACCOUNTANT, "Accountant"),
    (Membership.Role.INVENTORY_MANAGER, "Inventory manager"),
    (Membership.Role.SUPPORT, "Customer support"),
]


class StaffMembershipForm(forms.Form):
    email = forms.EmailField()
    first_name = forms.CharField(max_length=150)
    last_name = forms.CharField(max_length=150, required=False)
    role = forms.ChoiceField(choices=STAFF_ROLE_CHOICES)
    branches = forms.ModelMultipleChoiceField(
        queryset=Branch.objects.none(),
        required=False,
        label="Assigned branches (required)",
        help_text=(
            "On staff edit, their current branch assignments are preselected. "
            "Select the branches this staff member can access."
        ),
    )
    permissions = forms.ModelMultipleChoiceField(
        queryset=OrganizationPermission.objects.none(),
        required=False,
        widget=forms.CheckboxSelectMultiple,
        help_text=(
            "Choose only the capabilities this person needs. "
            "Branch access is always restricted to assigned branches."
        ),
    )

    def __init__(self, *args, organization, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["branches"].queryset = Branch.objects.filter(
            organization=organization, is_active=True, deleted_at__isnull=True
        )
        self.fields["permissions"].queryset = OrganizationPermission.objects.all()

    def clean_email(self):
        return self.cleaned_data["email"].strip().lower()

    def clean(self):
        cleaned = super().clean()
        if not cleaned.get("branches"):
            self.add_error("branches", "Assign at least one active branch to this staff role.")
        if cleaned.get("role") == Membership.Role.DAIRY_MANAGER and not cleaned.get("permissions"):
            self.add_error("permissions", "Select at least one permission for the dairy manager.")
        return cleaned


class StaffAccessUpdateForm(forms.Form):
    role = forms.ChoiceField(choices=STAFF_ROLE_CHOICES)
    branches = forms.ModelMultipleChoiceField(queryset=Branch.objects.none())
    permissions = forms.ModelMultipleChoiceField(
        queryset=OrganizationPermission.objects.none(),
        required=False,
        widget=forms.CheckboxSelectMultiple,
        help_text=(
            "Choose the capabilities this person needs. "
            "Branch access remains limited to these assigned branches."
        ),
    )

    def __init__(self, *args, organization, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["branches"].queryset = Branch.objects.filter(
            organization=organization, is_active=True, deleted_at__isnull=True
        )
        self.fields["permissions"].queryset = OrganizationPermission.objects.all()

    def clean(self):
        cleaned = super().clean()
        if not cleaned.get("branches"):
            self.add_error("branches", "Assign at least one active branch to this staff member.")
        if cleaned.get("role") == Membership.Role.DAIRY_MANAGER and not cleaned.get("permissions"):
            self.add_error("permissions", "Select at least one permission for the dairy manager.")
        return cleaned
