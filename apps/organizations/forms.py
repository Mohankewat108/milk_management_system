from django import forms

from .models import Branch, Organization


class OrganizationRegistrationForm(forms.ModelForm):
    class Meta:
        model = Organization
        fields = ("name", "legal_name", "phone", "email", "country", "address")


class BranchForm(forms.ModelForm):
    class Meta:
        model = Branch
        fields = ("code", "name", "address", "phone")
