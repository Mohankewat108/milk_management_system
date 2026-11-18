from datetime import date

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.db.models import Max, Q
from django.shortcuts import redirect, render
from django.utils import timezone
from django.views.decorators.http import require_http_methods, require_POST

from apps.audit.services import record_event
from apps.organizations.decorators import organization_access
from apps.organizations.models import Membership
from .forms import PricingConfigurationForm, QualityConfigurationForm
from .models import PricingConfiguration, QualityConfiguration
from .services import active_pricing_on


def _effective_end(value):
    return value or date.max


@login_required
@organization_access(Membership.Role.OWNER, Membership.Role.ADMIN)
@require_http_methods(["GET", "POST"])
def settings_view(request, organization_slug):
    organization = request.organization
    form = PricingConfigurationForm(request.POST or None, organization=organization)
    if request.method == "POST" and form.is_valid():
        data = form.cleaned_data
        branch = data["branch"]
        start, end = data["effective_from"], data["effective_to"]
        if branch and branch.organization_id != organization.id:
            form.add_error("branch", "Select a branch belonging to this dairy.")
        else:
            with transaction.atomic():
                # Lock the tenant row to serialize concurrent edits to the same rate schedule.
                type(organization).objects.select_for_update().get(pk=organization.pk)
                overlaps = PricingConfiguration.objects.filter(
                    organization=organization, branch=branch, deleted_at__isnull=True,
                    effective_from__lte=_effective_end(end),
                ).filter(Q(effective_to__isnull=True) | Q(effective_to__gte=start))
                if overlaps.exists():
                    form.add_error(
                        None,
                        "This rate schedule overlaps an existing schedule for the same scope. "
                        "Close the previous date range first, then publish the new rates.",
                    )
                else:
                    version = (PricingConfiguration.objects.filter(organization=organization)
                               .aggregate(value=Max("version"))["value"] or 0) + 1
                    pricing = form.save(commit=False)
                    pricing.organization = organization
                    pricing.version = version
                    pricing.created_by = request.user
                    # Owner-created rates are approved immediately; admin-created rates require owner approval.
                    pricing.is_approved = request.membership.role == Membership.Role.OWNER
                    if pricing.is_approved:
                        pricing.approved_by = request.user
                        pricing.approved_at = timezone.now()
                    pricing.save()
                    record_event(
                        actor=request.user, organization=organization,
                        action="pricing.created", target=pricing, request=request,
                    )
                    created_pricing = pricing
            if not form.errors:
                messages.success(
                    request,
                    "Dairy-wide rate schedule published for all customers."
                    if created_pricing.is_approved and created_pricing.branch_id is None
                    else "Rate schedule saved. It will apply after owner approval and its start date.",
                )
                return redirect("pricing:settings", organization_slug=organization_slug)
    history = PricingConfiguration.objects.filter(
        organization=organization
    ).select_related("branch", "created_by", "approved_by")
    lookup_date = request.GET.get("date")
    try:
        selected_date = date.fromisoformat(lookup_date) if lookup_date else timezone.localdate()
    except ValueError:
        selected_date = timezone.localdate()
    active_rate = active_pricing_on(organization=organization, pricing_date=selected_date)
    return render(request, "pricing/settings.html", {
        "organization": organization, "form": form, "history": history,
        "membership": request.membership, "selected_date": selected_date,
        "active_rate": active_rate, "schedule_date": selected_date.isoformat(),
    })


@login_required
@organization_access(Membership.Role.OWNER)
@require_POST
def approve_pricing(request, organization_slug, pricing_id):
    with transaction.atomic():
        pricing = PricingConfiguration.objects.select_for_update().get(
            pk=pricing_id, organization=request.organization, deleted_at__isnull=True
        )
        if pricing.is_approved:
            messages.info(request, "This rate schedule is already approved.")
        else:
            pricing.is_approved = True
            pricing.approved_by = request.user
            pricing.approved_at = timezone.now()
            pricing.save(update_fields=["is_approved", "approved_by", "approved_at", "updated_at"])
            record_event(actor=request.user, organization=request.organization,
                         action="pricing.approved", target=pricing, request=request)
            messages.success(request, "Rate schedule approved.")
    return redirect("pricing:settings", organization_slug=organization_slug)


@login_required
@organization_access(Membership.Role.OWNER)
@require_http_methods(["GET", "POST"])
def quality_settings(request, organization_slug):
    organization = request.organization
    form = QualityConfigurationForm(request.POST or None, organization=organization)
    if request.method == "POST" and form.is_valid():
        data = form.cleaned_data
        query_end = data["effective_to"] or date.max
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


@login_required
@organization_access(Membership.Role.OWNER, Membership.Role.ADMIN)
@require_http_methods(["GET", "POST"])
def pricing_edit(request, organization_slug, pricing_id):
    organization = request.organization
    pricing = PricingConfiguration.objects.get(
        pk=pricing_id, organization=organization,
        is_approved=False, deleted_at__isnull=True,
    )
    if pricing.collections.exists():
        messages.error(request, "This rate schedule is already referenced by collections and is immutable.")
        return redirect("pricing:settings", organization_slug=organization_slug)
    form = PricingConfigurationForm(request.POST or None, instance=pricing, organization=organization)
    if request.method == "POST" and form.is_valid():
        data = form.cleaned_data
        branch, start, end = data["branch"], data["effective_from"], data["effective_to"]
        overlaps = PricingConfiguration.objects.filter(
            organization=organization, branch=branch, deleted_at__isnull=True,
            effective_from__lte=_effective_end(end),
        ).filter(Q(effective_to__isnull=True) | Q(effective_to__gte=start)).exclude(pk=pricing.pk)
        if overlaps.exists():
            form.add_error(None, "This rate schedule overlaps another schedule for the same scope.")
        else:
            updated = form.save()
            record_event(
                actor=request.user, organization=organization,
                action="pricing.updated", target=updated,
                changes={"updated_fields": list(form.changed_data)}, request=request,
            )
            messages.success(request, "Pending rate schedule updated. Owner approval is still required.")
            return redirect("pricing:settings", organization_slug=organization_slug)
    return render(request, "pricing/edit.html", {
        "organization": organization, "form": form, "pricing": pricing,
    })
