from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.core.paginator import Paginator
from django.shortcuts import redirect, render
from django.utils import timezone
from django.views.decorators.http import require_http_methods

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
    page = Paginator(records, 25).get_page(request.GET.get("page"))
    return render(request, "collections/list.html", {
        "organization": organization, "page_obj": page,
        "total_litres": records.aggregate_total_litres if hasattr(records, "aggregate_total_litres") else None,
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
            record_event(actor=request.user, organization=organization, action="milk_collection.created",
                         target=entry, request=request)
            messages.success(request, f"Collection {entry.reference} recorded.")
            return redirect("collections:list", organization_slug=organization_slug)
    return render(request, "collections/form.html", {"organization": organization, "form": form})


urlpatterns = []
