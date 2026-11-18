from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required, user_passes_test
from django.db.models import Count
from django.shortcuts import redirect, render
from django.views.decorators.http import require_http_methods

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
        "customer_count": sum(item.customer_count for item in organizations),
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
