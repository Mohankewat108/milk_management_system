from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required, user_passes_test
from django.db.models import Count
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_http_methods, require_POST

from apps.audit.services import record_event
from apps.organizations.models import Organization
from apps.platform_admin.forms import PlatformOrganizationCreateForm
from apps.platform_admin.models import Subscription
from apps.platform_admin.services import create_platform_organization


User = get_user_model()


def is_platform_owner(user):
    return user.is_authenticated and user.is_superuser


@login_required
@user_passes_test(is_platform_owner)
def dashboard(request):
    organizations = Organization.objects.select_related("owner").annotate(
        member_count=Count("memberships", distinct=True),
        customer_count=Count("customers", distinct=True),
        farmer_count=Count("farmers", distinct=True),
    ).order_by("-created_at")
    context = {
        "organization_count": Organization.objects.count(),
        "active_organizations": Organization.objects.filter(status=Organization.Status.ACTIVE).count(),
        "trial_organizations": Organization.objects.filter(status=Organization.Status.TRIAL).count(),
        "suspended_organizations": Organization.objects.filter(status=Organization.Status.SUSPENDED).count(),
        "user_count": User.objects.count(),
        "customer_count": Organization.objects.aggregate(total=Count("customers", distinct=True))["total"],
        "subscription_count": Subscription.objects.count(),
        "organizations": organizations[:50],
    }
    return render(request, "platform/dashboard.html", context)


@login_required
@user_passes_test(is_platform_owner)
@require_http_methods(["GET", "POST"])
def organization_create(request):
    form = PlatformOrganizationCreateForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        data = form.cleaned_data.copy()
        owner = data.pop("owner")
        name = data.pop("name")
        organization = create_platform_organization(owner=owner, name=name, **data)
        record_event(
            actor=request.user,
            organization=organization,
            action="platform.organization.created",
            target=organization,
            request=request,
        )
        messages.success(
            request,
            f"{organization.name} has been created and {owner.email} is now its dairy owner.",
        )
        return redirect("platform:dashboard")
    return render(request, "platform/organization_form.html", {"form": form})


@login_required
@user_passes_test(is_platform_owner)
@require_POST
def organization_set_status(request, organization_id):
    organization = get_object_or_404(Organization, pk=organization_id)
    new_status = request.POST.get("status", "").strip()
    reason = request.POST.get("reason", "").strip()
    allowed_statuses = {
        Organization.Status.ACTIVE,
        Organization.Status.SUSPENDED,
        Organization.Status.CLOSED,
    }
    if new_status not in allowed_statuses:
        messages.error(request, "Choose a valid farm status.")
        return redirect("platform:dashboard")
    if not reason:
        messages.error(request, "A reason is required for a farm status change.")
        return redirect("platform:dashboard")
    old_status = organization.status
    if old_status == new_status:
        messages.info(request, "The farm already has that status.")
        return redirect("platform:dashboard")
    organization.status = new_status
    organization.save(update_fields=["status", "updated_at"])
    record_event(
        actor=request.user,
        organization=organization,
        action="platform.organization.status_changed",
        target=organization,
        changes={"from": old_status, "to": new_status, "reason": reason},
        request=request,
    )
    messages.success(request, f"{organization.name} status changed to {organization.get_status_display()}.")
    return redirect("platform:dashboard")
