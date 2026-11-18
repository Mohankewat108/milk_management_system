from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Max, Q
from django.shortcuts import redirect, render
from django.views.decorators.http import require_http_methods, require_POST

from apps.audit.services import record_event
from apps.organizations.decorators import organization_access
from apps.organizations.models import Membership
from .forms import PricingConfigurationForm, QualityConfigurationForm
from .models import PricingConfiguration, QualityConfiguration


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
            query_end = end_date or data["effective_from"].replace(year=9999)
            overlap = PricingConfiguration.objects.filter(
                organization=organization, branch=data["branch"],
                effective_from__lte=query_end,
            ).filter(Q(effective_to__isnull=True) | Q(effective_to__gte=data["effective_from"]))
            if overlap.exists():
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


@login_required
@organization_access(Membership.Role.OWNER)
@require_http_methods(["GET", "POST"])
def quality_settings(request, organization_slug):
    organization = request.organization
    form = QualityConfigurationForm(request.POST or None, organization=organization)
    if request.method == "POST" and form.is_valid():
        data = form.cleaned_data
        query_end = data["effective_to"] or data["effective_from"].replace(year=9999)
        overlap = QualityConfiguration.objects.filter(
            organization=organization, branch=data["branch"],
            effective_from__lte=query_end,
        ).filter(Q(effective_to__isnull=True) | Q(effective_to__gte=data["effective_from"]))
        if overlap.exists():
            form.add_error(None, "This branch scope already has an overlapping effective quality profile.")
        else:
            version = (QualityConfiguration.objects.filter(organization=organization)
                       .aggregate(value=Max("version"))["value"] or 0) + 1
            config = form.save(commit=False)
            config.organization = organization
            config.version = version
            config.created_by = request.user
            config.is_approved = True
            config.save()
            record_event(actor=request.user, organization=organization,
                         action="quality_profile.created", target=config, request=request)
            messages.success(request, "Quality profile saved and activated.")
            return redirect("pricing:quality", organization_slug=organization_slug)
    history = QualityConfiguration.objects.filter(organization=organization).select_related("branch")
    return render(request, "pricing/quality.html", {
        "organization": organization, "form": form, "history": history,
    })
