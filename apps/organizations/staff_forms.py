from django import forms

from .models import Branch, Membership


class StaffMembershipForm(forms.Form):
    email = forms.EmailField()
    first_name = forms.CharField(max_length=150)
    last_name = forms.CharField(max_length=150, required=False)
    role = forms.ChoiceField(choices=[
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

    def clean_email(self):
        return self.cleaned_data["email"].strip().lower()

    def clean(self):
        cleaned = super().clean()
        if not cleaned.get("branches"):
            self.add_error("branches", "Assign at least one branch to this staff role.")
        return cleaned
