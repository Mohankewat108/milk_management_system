from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.core.paginator import Paginator
from django.db.models import Sum
from django.shortcuts import redirect, render
from django.views.decorators.http import require_http_methods, require_POST

from apps.audit.services import record_event
from apps.organizations.decorators import organization_access
from apps.organizations.models import Membership
from .forms import CollectionEntryForm
from .models import MilkCollection
from .services import create_collection


@login_required
@organization_access(
    Membership.Role.OWNER, Membership.Role.ADMIN, Membership.Role.BRANCH_MANAGER,
    Membership.Role.COLLECTION_OPERATOR, Membership.Role.QUALITY_OFFICER,
)
def collection_list(request, organization_slug):
    organization = request.organization
    records = MilkCollection.objects.filter(organization=organization).select_related(
        "branch", "farmer", "customer", "recorded_by"
    ).order_by("-collected_at")
    start, end = request.GET.get("from"), request.GET.get("to")
    if start:
        records = records.filter(collected_at__date__gte=start)
    if end:
        records = records.filter(collected_at__date__lte=end)
    total_litres = records.aggregate(value=Sum("quantity_litres"))["value"] or 0
    page = Paginator(records, 25).get_page(request.GET.get("page"))
    return render(request, "collections/list.html", {
        "organization": organization, "page_obj": page, "total_litres": total_litres,
    })


@login_required
@organization_access(
    Membership.Role.OWNER, Membership.Role.ADMIN, Membership.Role.BRANCH_MANAGER,
    Membership.Role.COLLECTION_OPERATOR,
)
@require_http_methods(["GET", "POST"])
def collection_create(request, organization_slug):
    organization = request.organization
    form = CollectionEntryForm(request.POST or None, organization=organization)
    if request.method == "POST" and form.is_valid():
        data = form.cleaned_data
        assigned = request.membership.branch_assignments.values_list("branch_id", flat=True)
        if assigned.exists() and not assigned.filter(pk=data["branch"].pk).exists():
            form.add_error("branch", "You are not assigned to this branch.")
        else:
            try:
                entry = create_collection(
                    organization=organization, branch=data["branch"], actor=request.user,
                    collected_at=data["collected_at"], quantity_litres=data["quantity_litres"],
                    snf=data["snf"], fat=data["fat"], lactose=data["lactose"],
                    farmer=data["farmer"], customer=data["customer"], notes=data["notes"],
                )
            except ValidationError as exc:
                form.add_error(None, exc)
            else:
                record_event(actor=request.user, organization=organization,
                             action="milk_collection.created", target=entry, request=request)
                messages.success(request, f"Collection {entry.reference} recorded.")
                return redirect("collections:list", organization_slug=organization_slug)
    return render(request, "collections/form.html", {"organization": organization, "form": form})


@login_required
@organization_access(Membership.Role.OWNER, Membership.Role.ADMIN, Membership.Role.QUALITY_OFFICER)
@require_POST
def approve_collection(request, organization_slug, collection_id):
    entry = MilkCollection.objects.get(pk=collection_id, organization=request.organization)
    if entry.status != MilkCollection.Status.SUBMITTED:
        messages.error(request, "Only submitted collections can be approved.")
    else:
        entry.status = MilkCollection.Status.APPROVED
        entry.save(update_fields=["status", "updated_at"])
        record_event(actor=request.user, organization=request.organization,
                     action="milk_collection.approved", target=entry, request=request)
        messages.success(request, "Collection approved.")
    return redirect("collections:list", organization_slug=organization_slug)
