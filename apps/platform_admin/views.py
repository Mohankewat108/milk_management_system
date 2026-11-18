from django.contrib.auth.decorators import user_passes_test
from django.db.models import Count
from django.shortcuts import render

from apps.accounts.models import User
from apps.organizations.models import Organization
from apps.platform_admin.models import Subscription


@user_passes_test(lambda user: user.is_authenticated and user.is_superuser)
def dashboard(request):
    context = {
        "organization_count": Organization.objects.count(),
        "active_organizations": Organization.objects.filter(status=Organization.Status.ACTIVE).count(),
        "suspended_organizations": Organization.objects.filter(status=Organization.Status.SUSPENDED).count(),
        "user_count": User.objects.count(),
        "subscription_count": Subscription.objects.count(),
        "organizations": Organization.objects.annotate(member_count=Count("memberships")).order_by("-created_at")[:20],
    }
    return render(request, "platform/dashboard.html", context)
