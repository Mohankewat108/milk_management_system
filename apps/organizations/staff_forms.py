from django import forms

from .models import Branch, Membership


class StaffMembershipForm(forms.Form):
    username = forms.CharField(max_length=150)
    email = forms.EmailField()
    first_name = forms.CharField(max_length=150)
    last_name = forms.CharField(max_length=150, required=False)
    role = forms.ChoiceField(choices=[
        (Membership.Role.ADMIN, "Organisation admin"),
        (Membership.Role.BRANCH_MANAGER, "Branch manager"),
        (Membership.Role.COLLECTION_OPERATOR, "Milk collection operator"),
        (Membership.Role.QUALITY_OFFICER, "Quality officer"),
        (Membership.Role.ACCOUNTANT, "Accountant"),
        (Membership.Role.INVENTORY_MANAGER, "Inventory manager"),
        (Membership.Role.SUPPORT, "Customer support"),
    ])
    branches = forms.ModelMultipleChoiceField(queryset=Branch.objects.none(), required=False)

    def __init__(self, *args, organization, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["branches"].queryset = Branch.objects.filter(
            organization=organization, is_active=True
        )

    def clean(self):
        cleaned = super().clean()
        role = cleaned.get("role")
        branches = cleaned.get("branches")
        if role not in {Membership.Role.OWNER, Membership.Role.ADMIN} and not branches:
            self.add_error("branches", "Assign at least one branch to this staff role.")
        return cleaned
