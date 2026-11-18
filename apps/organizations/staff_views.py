from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.db import IntegrityError, transaction
from django.shortcuts import redirect, render
from django.views.decorators.http import require_http_methods

from apps.audit.services import record_event

from .decorators import organization_access
from .models import BranchAssignment, Membership
from .staff_forms import StaffMembershipForm

User = get_user_model()


@login_required
@organization_access(Membership.Role.OWNER, Membership.Role.ADMIN)
@require_http_methods(["GET", "POST"])
def staff_list(request, organization_slug):
    org = request.organization
    form = StaffMembershipForm(request.POST or None, organization=org)
    if request.method == "POST" and form.is_valid():
        data = form.cleaned_data
        email = data["email"].strip().lower()
        if User.objects.filter(email__iexact=email).exists():
            user = User.objects.get(email__iexact=email)
            if user.username != data["username"]:
                form.add_error("email", "This email already belongs to another account.")
                return render(request, "organizations/staff.html", {
                    "organization": org, "form": form,
                    "memberships": org.memberships.select_related("user").order_by("user__username"),
                })
        elif User.objects.filter(username__iexact=data["username"]).exists():
            form.add_error("username", "This username is already taken.")
            return render(request, "organizations/staff.html", {
                "organization": org, "form": form,
                "memberships": org.memberships.select_related("user").order_by("user__username"),
            })
        else:
            user = User(username=data["username"], email=email,
                        first_name=data["first_name"], last_name=data["last_name"])
            user.set_unusable_password()
            user.save()
        try:
            with transaction.atomic():
                membership = Membership.objects.create(
                    user=user, organization=org, role=data["role"],
                    status=Membership.Status.ACTIVE,
                )
                BranchAssignment.objects.bulk_create([
                    BranchAssignment(membership=membership, branch=branch)
                    for branch in data["branches"]
                ])
        except IntegrityError:
            form.add_error(None, "This user already has a membership in the organisation.")
        else:
            record_event(actor=request.user, organization=org, action="staff.membership_created",
                         target=membership, request=request)
            messages.success(
                request,
                "Staff access created. The staff member must use Forgot password to set their first password.",
            )
            return redirect("business:staff", organization_slug=organization_slug)
    memberships = org.memberships.select_related("user").prefetch_related("branch_assignments__branch").order_by("user__username")
    return render(request, "organizations/staff.html", {
        "organization": org, "form": form, "memberships": memberships,
    })
