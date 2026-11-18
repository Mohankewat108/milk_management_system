from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Max, Q
from django.shortcuts import redirect, render
from django.views.decorators.http import require_http_methods, require_POST

from apps.audit.services import record_event
from apps.organizations.decorators import organization_access
from apps.organizations.models import Membership
from .forms import PricingConfigurationForm
from .models import PricingConfiguration


@login_required
@organization_access(Membership.Role.OWNER, Membership.Role.ADMIN)
@require_http_methods(["GET", "POST"])
def settings_view(request, organization_slug):
    organization = request.organization
    form = PricingConfigurationForm(request.POST or None, organization=organization)
    if request.method == "POST" and form.is_valid():
        data = form.cleaned_data
        end_date = data["effective_to"]
        if end_date and end_date < data["effective_from"]:
            form.add_error("effective_to", "End date must be on or after start date.")
        else:
            scope = PricingConfiguration.objects.filter(
                organization=organization, branch=data["branch"]
            ).filter(effective_from__lte=end_date or data["effective_from"]).filter(
                Q(effective_to__isnull=True) | Q(effective_to__gte=data["effective_from"])
            )
            if scope.exists():
                form.add_error(None, "This branch scope already has an overlapping effective pricing period.")
            else:
                version = (PricingConfiguration.objects.filter(organization=organization)
                           .aggregate(value=Max("version"))["value"] or 0) + 1
                pricing = form.save(commit=False)
                pricing.organization = organization
                pricing.version = version
                pricing.created_by = request.user
                pricing.is_approved = request.membership.role == Membership.Role.OWNER
                pricing.save()
                record_event(actor=request.user, organization=organization,
                             action="pricing.created", target=pricing, request=request)
                messages.success(request, "Pricing configuration saved.")
                return redirect("pricing:settings", organization_slug=organization_slug)
    history = PricingConfiguration.objects.filter(organization=organization).select_related("branch", "created_by")
    return render(request, "pricing/settings.html", {
        "organization": organization, "form": form, "history": history,
        "membership": request.membership,
    })


@login_required
@organization_access(Membership.Role.OWNER)
@require_POST
def approve_pricing(request, organization_slug, pricing_id):
    pricing = PricingConfiguration.objects.get(pk=pricing_id, organization=request.organization)
    pricing.is_approved = True
    pricing.save(update_fields=["is_approved", "updated_at"])
    record_event(actor=request.user, organization=request.organization,
                 action="pricing.approved", target=pricing, request=request)
    messages.success(request, "Pricing version approved.")
    return redirect("pricing:settings", organization_slug=organization_slug)
