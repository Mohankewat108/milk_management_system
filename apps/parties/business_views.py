from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.shortcuts import redirect, render
from django.views.decorators.http import require_http_methods

from apps.audit.services import record_event
from apps.organizations.decorators import organization_access
from apps.organizations.models import Membership

from .forms import CustomerForm, FarmerForm
from .models import Customer, Farmer


@login_required
@organization_access(Membership.Role.OWNER, Membership.Role.ADMIN, Membership.Role.BRANCH_MANAGER,
                     Membership.Role.SUPPORT)
def customer_list(request, organization_slug):
    org = request.organization
    records = Customer.objects.filter(organization=org).order_by("full_name")
    term = request.GET.get("q", "").strip()
    if term:
        from django.db.models import Q
        records = records.filter(Q(full_name__icontains=term) | Q(code__icontains=term) | Q(phone__icontains=term))
    page = Paginator(records, 25).get_page(request.GET.get("page"))
    return render(request, "parties/customers.html", {"organization": org, "page_obj": page, "query": term})


@login_required
@organization_access(Membership.Role.OWNER, Membership.Role.ADMIN, Membership.Role.BRANCH_MANAGER)
@require_http_methods(["GET", "POST"])
def customer_create(request, organization_slug):
    org = request.organization
    form = CustomerForm(request.POST or None, organization=org)
    if request.method == "POST" and form.is_valid():
        customer = form.save(commit=False)
        customer.organization = org
        customer.save()
        record_event(actor=request.user, organization=org, action="customer.created",
                     target=customer, request=request)
        messages.success(request, f"Customer {customer.full_name} created.")
        return redirect("parties:customers", organization_slug=organization_slug)
    return render(request, "parties/customer_form.html", {"organization": org, "form": form})


@login_required
@organization_access(Membership.Role.OWNER, Membership.Role.ADMIN, Membership.Role.BRANCH_MANAGER,
                     Membership.Role.SUPPORT)
def farmer_list(request, organization_slug):
    org = request.organization
    records = Farmer.objects.filter(organization=org).order_by("full_name")
    term = request.GET.get("q", "").strip()
    if term:
        from django.db.models import Q
        records = records.filter(Q(full_name__icontains=term) | Q(code__icontains=term) | Q(phone__icontains=term))
    page = Paginator(records, 25).get_page(request.GET.get("page"))
    return render(request, "parties/farmers.html", {"organization": org, "page_obj": page, "query": term})


@login_required
@organization_access(Membership.Role.OWNER, Membership.Role.ADMIN, Membership.Role.BRANCH_MANAGER)
@require_http_methods(["GET", "POST"])
def farmer_create(request, organization_slug):
    org = request.organization
    form = FarmerForm(request.POST or None, organization=org)
    if request.method == "POST" and form.is_valid():
        farmer = form.save(commit=False)
        farmer.organization = org
        farmer.save()
        record_event(actor=request.user, organization=org, action="farmer.created",
                     target=farmer, request=request)
        messages.success(request, f"Farmer {farmer.full_name} created.")
        return redirect("parties:farmers", organization_slug=organization_slug)
    return render(request, "parties/farmer_form.html", {"organization": org, "form": form})
