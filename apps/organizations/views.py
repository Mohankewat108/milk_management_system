from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render
from django.views.decorators.http import require_http_methods

from apps.audit.services import record_event
from .decorators import organization_access
from .forms import BranchForm, OrganizationRegistrationForm
from .models import Membership
from .selectors import memberships_for_user
from .services import register_organization


@login_required
def workspace(request):
    memberships = memberships_for_user(request.user)
    if memberships.count() == 1:
        return redirect("business:dashboard", organization_slug=memberships.first().organization.slug)
    return render(request, "organizations/workspace.html", {"memberships": memberships})


@login_required
@require_http_methods(["GET", "POST"])
def register_business(request):
    form = OrganizationRegistrationForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        data = form.cleaned_data
        organization = register_organization(
            user=request.user,
            name=data["name"],
            legal_name=data.get("legal_name", ""),
            phone=data.get("phone", ""),
            email=data.get("email", ""),
            country=data.get("country", "Nepal"),
            address=data.get("address", ""),
        )
        record_event(actor=request.user, organization=organization, action="organization.created",
                     target=organization, request=request)
        messages.success(request, "Your dairy workspace is ready.")
        return redirect("business:dashboard", organization_slug=organization.slug)
    return render(request, "organizations/register.html", {"form": form})


@login_required
@organization_access()
def dashboard(request, organization_slug):
    organization = request.organization
    context = {
        "organization": organization,
        "membership": request.membership,
        "branch_count": organization.branches.filter(is_active=True).count(),
        "customer_count": organization.customers.filter(is_active=True).count(),
        "farmer_count": organization.farmers.filter(is_active=True).count(),
        "collection_count": organization.milk_collections.count(),
    }
    return render(request, "dashboard/business.html", context)


@login_required
@organization_access(Membership.Role.OWNER, Membership.Role.ADMIN)
@require_http_methods(["GET", "POST"])
def branches(request, organization_slug):
    organization = request.organization
    form = BranchForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        branch = form.save(commit=False)
        branch.organization = organization
        branch.save()
        record_event(actor=request.user, organization=organization, action="branch.created",
                     target=branch, request=request)
        messages.success(request, "Branch created.")
        return redirect("business:branches", organization_slug=organization_slug)
    return render(request, "organizations/branches.html", {
        "organization": organization,
        "branches": organization.branches.order_by("name"),
        "form": form,
    })
