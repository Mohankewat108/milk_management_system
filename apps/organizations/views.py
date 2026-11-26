from datetime import timedelta

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render
from django.utils import timezone
from django.views.decorators.http import require_http_methods

from apps.audit.services import record_event
from apps.organizations.permissions import accessible_branch_ids
from apps.platform_admin.models import Subscription, SubscriptionPlan
from apps.pricing.services import active_pricing_on

from .decorators import organization_access
from .forms import BranchForm, OrganizationProfileForm, OrganizationRegistrationForm
from .models import Membership
from .permissions import has_organization_permission
from .selectors import memberships_for_user
from .services import register_organization


@login_required
def workspace(request):
    if getattr(request.user, "farmer_profile", None):
        return redirect("farmer_portal:home")
    memberships = memberships_for_user(request.user)
    if memberships.count() == 1:
        return redirect(
            "business:dashboard", organization_slug=memberships.first().organization.slug
        )
    return render(request, "organizations/workspace.html", {"memberships": memberships})


@login_required
@require_http_methods(["GET", "POST"])
def register_business(request):
    form = OrganizationRegistrationForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        request.session["dairy_registration_data"] = form.cleaned_data
        return redirect("business:subscription_plans")
    return render(request, "organizations/register.html", {"form": form})


@login_required
@require_http_methods(["GET", "POST"])
def subscription_plans(request):
    registration_data = request.session.get("dairy_registration_data")
    if not registration_data:
        messages.info(request, "Please complete your dairy profile first.")
        return redirect("business:register")
    plans = SubscriptionPlan.objects.filter(is_active=True).order_by("monthly_price")
    if request.method == "POST":
        plan_id = request.POST.get("plan")
        plan = plans.filter(pk=plan_id).first()
        if not plan:
            messages.error(request, "Please select a valid subscription plan.")
            return redirect("business:subscription_plans")
        data = registration_data
        organization = register_organization(
            user=request.user,
            name=data["name"],
            legal_name=data.get("legal_name", ""),
            phone=data.get("phone", ""),
            email=data.get("email", ""),
            country=data.get("country", "Nepal"),
            address=data.get("address", ""),
        )
        today = timezone.localdate()
        Subscription.objects.create(
            organization=organization,
            plan=plan,
            status=Subscription.Status.TRIAL,
            starts_at=today,
            ends_at=today + timedelta(days=14),
        )
        request.session.pop("dairy_registration_data", None)
        record_event(
            actor=request.user,
            organization=organization,
            action="organization.created",
            target=organization,
            request=request,
        )
        record_event(
            actor=request.user,
            organization=organization,
            action="subscription.plan_selected",
            target=plan,
            changes={"plan_code": plan.code},
            request=request,
        )
        messages.success(request, "Your dairy workspace and subscription trial are ready.")
        return redirect("business:dashboard", organization_slug=organization.slug)
    return render(request, "organizations/subscription_plans.html", {"plans": plans})


@login_required
@organization_access()
def dashboard(request, organization_slug):
    organization = request.organization
    membership = request.membership
    branch_ids = accessible_branch_ids(membership)
    if membership.role == Membership.Role.DAIRY_MANAGER and not has_organization_permission(
        membership, "dashboard.view"
    ):
        from django.http import Http404

        raise Http404
    branches = organization.branches.filter(is_active=True, deleted_at__isnull=True)
    customers = organization.customers.filter(is_active=True, deleted_at__isnull=True)
    farmers = organization.farmers.filter(is_active=True, deleted_at__isnull=True)
    collections = organization.milk_collections.exclude(status="reversed")
    if branch_ids is not None:
        branches = branches.filter(pk__in=branch_ids)
        customers = customers.filter(branch_id__in=branch_ids)
        farmers = farmers.filter(branch_id__in=branch_ids)
        collections = collections.filter(branch_id__in=branch_ids)
    today = timezone.localdate()
    branch_for_rate = branches.first() if branch_ids is not None else None
    active_rate = active_pricing_on(
        organization=organization, pricing_date=today, branch=branch_for_rate
    )
    context = {
        "organization": organization,
        "membership": membership,
        "branch_count": branches.count(),
        "customer_count": customers.count(),
        "farmer_count": farmers.count(),
        "collection_count": collections.count(),
        "active_rate": active_rate,
        "rate_date": today,
        "can_record_collection": has_organization_permission(membership, "collections.create"),
        "can_view_parties": has_organization_permission(membership, "parties.view"),
        "can_view_collections": has_organization_permission(membership, "collections.view"),
        "can_approve_collections": has_organization_permission(membership, "collections.approve"),
        "can_manage_staff": membership.role in {Membership.Role.OWNER, Membership.Role.ADMIN},
        "can_manage_finance": has_organization_permission(membership, "finance.view"),
        "can_manage_inventory": has_organization_permission(membership, "inventory.view"),
        "can_manage_configuration": membership.role
        in {Membership.Role.OWNER, Membership.Role.ADMIN},
    }
    return render(request, "dashboard/business.html", context)


@login_required
@organization_access(
    Membership.Role.OWNER,
    Membership.Role.ADMIN,
)
@require_http_methods(["GET", "POST"])
def branches(request, organization_slug):
    organization = request.organization
    form = BranchForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        branch = form.save(commit=False)
        branch.organization = organization
        branch.save()
        record_event(
            actor=request.user,
            organization=organization,
            action="branch.created",
            target=branch,
            request=request,
        )
        messages.success(request, "Branch created.")
        return redirect("business:branches", organization_slug=organization_slug)
    return render(
        request,
        "organizations/branches.html",
        {
            "organization": organization,
            "branches": organization.branches.filter(deleted_at__isnull=True).order_by("name"),
            "form": form,
        },
    )


@login_required
@organization_access(
    Membership.Role.OWNER,
    Membership.Role.ADMIN,
)
@require_http_methods(["GET", "POST"])
def branch_edit(request, organization_slug, branch_id):
    from django.shortcuts import get_object_or_404

    branch = get_object_or_404(
        request.organization.branches.filter(deleted_at__isnull=True), pk=branch_id
    )
    form = BranchForm(request.POST or None, instance=branch)
    if request.method == "POST" and form.is_valid():
        updated = form.save(commit=False)
        updated.organization = request.organization
        updated.save()
        record_event(
            actor=request.user,
            organization=request.organization,
            action="branch.updated",
            target=updated,
            changes={"updated_fields": list(form.changed_data)},
            request=request,
        )
        messages.success(request, f"Branch {updated.name} updated.")
        return redirect("business:branches", organization_slug=organization_slug)
    return render(
        request,
        "organizations/branch_form.html",
        {
            "organization": request.organization,
            "form": form,
            "branch": branch,
        },
    )


@login_required
@organization_access(
    Membership.Role.OWNER,
    Membership.Role.ADMIN,
)
@require_http_methods(["GET", "POST"])
def organization_edit(request, organization_slug):
    organization = request.organization
    if request.membership.role != Membership.Role.OWNER:
        messages.error(
            request, "Only the dairy owner can change legal and billing profile details."
        )
        return redirect("business:dashboard", organization_slug=organization_slug)
    form = OrganizationProfileForm(request.POST or None, instance=organization)
    if request.method == "POST" and form.is_valid():
        updated = form.save()
        record_event(
            actor=request.user,
            organization=updated,
            action="organization.updated",
            target=updated,
            changes={"updated_fields": list(form.changed_data)},
            request=request,
        )
        messages.success(request, "Dairy workspace profile updated.")
        return redirect("business:dashboard", organization_slug=organization_slug)
    return render(
        request,
        "organizations/profile_form.html",
        {
            "organization": organization,
            "form": form,
        },
    )
