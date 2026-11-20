import hashlib
import hmac
import secrets
from datetime import timedelta

from django.conf import settings
from django.contrib import messages
from django.contrib.auth import get_user_model, login
from django.contrib.auth.decorators import login_required
from django.core.mail import send_mail
from django.db import transaction
from django.http import HttpResponseForbidden
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_http_methods, require_POST

from apps.audit.services import record_event
from apps.core.site_urls import build_site_absolute_uri

from .decorators import organization_access
from .models import BranchAssignment, Membership, StaffInvitation
from .staff_forms import StaffAccessUpdateForm, StaffMembershipForm

User = get_user_model()
MANAGER_ROLES = (Membership.Role.OWNER, Membership.Role.ADMIN)


def _invitation_valid(invitation, token):
    supplied = hashlib.sha256(token.encode("utf-8")).hexdigest()
    return (
        hmac.compare_digest(invitation.token_hash, supplied)
        and invitation.accepted_at is None
        and invitation.revoked_at is None
        and invitation.expires_at > timezone.now()
    )


@login_required
@organization_access(*MANAGER_ROLES)
@require_http_methods(["GET", "POST"])
def staff_list(request, organization_slug):
    org = request.organization
    form = StaffMembershipForm(request.POST or None, organization=org)
    if request.method == "POST" and form.is_valid():
        data = form.cleaned_data
        email = data["email"]
        existing_user = User.objects.filter(email__iexact=email).first()
        if (
            existing_user
            and Membership.objects.filter(organization=org, user=existing_user).exists()
        ):
            form.add_error("email", "This person already has a membership in this dairy.")
        elif StaffInvitation.objects.filter(
            organization=org,
            email__iexact=email,
            accepted_at__isnull=True,
            revoked_at__isnull=True,
            expires_at__gt=timezone.now(),
        ).exists():
            form.add_error("email", "An active invitation already exists for this email.")
        else:
            token = secrets.token_urlsafe(32)
            with transaction.atomic():
                invitation = StaffInvitation.objects.create(
                    organization=org,
                    invited_by=request.user,
                    email=email,
                    first_name=data["first_name"],
                    last_name=data["last_name"],
                    role=data["role"],
                    token_hash=hashlib.sha256(token.encode("utf-8")).hexdigest(),
                    expires_at=timezone.now() + timedelta(hours=48),
                )
                invitation.branches.set(data["branches"])
                invitation.permissions.set(data["permissions"])
                invite_path = reverse(
                    "accounts:staff_invitation_accept",
                    kwargs={"invitation_id": invitation.pk, "token": token},
                )
                invitation_url = build_site_absolute_uri(request, invite_path)
                body = (
                    f"You have been invited to join {org.name} on DairyNexus.\n\n"
                    f"Role: {invitation.get_role_display()}\n"
                    f"Accept your invitation within 48 hours: {invitation_url}\n\n"
                    "If you were not expecting this invitation, you can ignore this email."
                )
                try:
                    send_mail(
                        f"Staff invitation to {org.name}",
                        body,
                        settings.DEFAULT_FROM_EMAIL,
                        [email],
                        fail_silently=False,
                    )
                except Exception:
                    invitation.revoked_at = timezone.now()
                    invitation.save(update_fields=["revoked_at", "updated_at"])
                    messages.error(
                        request,
                        "Invitation could not be emailed. Check email configuration and try again.",
                    )
                    return redirect("business:staff", organization_slug=organization_slug)
            record_event(
                actor=request.user,
                organization=org,
                action="staff.invitation.created",
                target=invitation,
                changes={
                    "email": email,
                    "role": invitation.role,
                    "branch_ids": [str(b.pk) for b in data["branches"]],
                },
                request=request,
            )
            messages.success(request, f"Staff invitation sent to {email}. It expires in 48 hours.")
            return redirect("business:staff", organization_slug=organization_slug)

    memberships = (
        org.memberships.exclude(role=Membership.Role.OWNER)
        .select_related("user")
        .prefetch_related("branch_assignments__branch")
        .order_by("user__email")
    )
    invitations = org.staff_invitations.select_related("invited_by").prefetch_related("branches")
    return render(
        request,
        "organizations/staff.html",
        {
            "organization": org,
            "form": form,
            "memberships": memberships,
            "invitations": invitations,
        },
    )


@login_required
@organization_access(*MANAGER_ROLES)
@require_http_methods(["GET", "POST"])
def staff_membership_edit(request, organization_slug, membership_id):
    membership = get_object_or_404(
        Membership.objects.filter(organization=request.organization)
        .exclude(role=Membership.Role.OWNER)
        .select_related("user")
        .prefetch_related("branch_assignments__branch"),
        pk=membership_id,
    )
    initial = {
        "role": membership.role,
        "branches": [item.branch_id for item in membership.branch_assignments.all()],
        "permissions": list(membership.permissions.values_list("pk", flat=True)),
    }
    form = StaffAccessUpdateForm(
        request.POST or None,
        initial=initial,
        organization=request.organization,
    )
    if request.method == "POST" and form.is_valid():
        with transaction.atomic():
            locked = Membership.objects.select_for_update().get(
                pk=membership.pk, organization=request.organization
            )
            before_role = locked.role
            before_branches = list(locked.branch_assignments.values_list("branch_id", flat=True))
            locked.role = form.cleaned_data["role"]
            locked.save(update_fields=["role", "updated_at"])
            locked.permissions.set(form.cleaned_data["permissions"])
            locked.branch_assignments.all().delete()
            BranchAssignment.objects.bulk_create(
                [
                    BranchAssignment(membership=locked, branch=branch)
                    for branch in form.cleaned_data["branches"]
                ]
            )
            record_event(
                actor=request.user,
                organization=request.organization,
                action="staff.access_updated",
                target=locked,
                changes={
                    "before_role": before_role,
                    "after_role": locked.role,
                    "permission_keys": list(locked.permissions.values_list("key", flat=True)),
                    "before_branch_ids": [str(value) for value in before_branches],
                    "after_branch_ids": [
                        str(branch.pk) for branch in form.cleaned_data["branches"]
                    ],
                },
                request=request,
            )
        messages.success(request, f"Access updated for {membership.user.email}.")
        return redirect("business:staff", organization_slug=organization_slug)
    return render(
        request,
        "organizations/staff_edit.html",
        {"organization": request.organization, "membership": membership, "form": form},
    )


@login_required
@organization_access(*MANAGER_ROLES)
@require_POST
def staff_membership_status(request, organization_slug, membership_id):
    membership = get_object_or_404(
        Membership.objects.filter(organization=request.organization).exclude(
            role=Membership.Role.OWNER
        ),
        pk=membership_id,
    )
    status = request.POST.get("status")
    if status not in {Membership.Status.ACTIVE, Membership.Status.SUSPENDED}:
        messages.error(request, "Invalid staff status.")
    else:
        membership.status = status
        membership.save(update_fields=["status", "updated_at"])
        record_event(
            actor=request.user,
            organization=request.organization,
            action="staff.membership_status_changed",
            target=membership,
            changes={"status": status},
            request=request,
        )
        messages.success(request, f"Staff access {status}.")
    return redirect("business:staff", organization_slug=organization_slug)


@login_required
@organization_access(*MANAGER_ROLES)
@require_POST
def staff_invitation_revoke(request, organization_slug, invitation_id):
    invitation = get_object_or_404(
        StaffInvitation.objects.filter(organization=request.organization),
        pk=invitation_id,
    )
    if invitation.accepted_at is None and invitation.revoked_at is None:
        invitation.revoked_at = timezone.now()
        invitation.save(update_fields=["revoked_at", "updated_at"])
        record_event(
            actor=request.user,
            organization=request.organization,
            action="staff.invitation.revoked",
            target=invitation,
            request=request,
        )
        messages.success(request, "Staff invitation revoked.")
    return redirect("business:staff", organization_slug=organization_slug)


@never_cache
@require_http_methods(["GET", "POST"])
def staff_invitation_accept(request, invitation_id, token):
    invitation = get_object_or_404(
        StaffInvitation.objects.select_related("organization", "invited_by"),
        pk=invitation_id,
    )
    if not _invitation_valid(invitation, token):
        return render(request, "organizations/staff_invitation_invalid.html", status=410)

    user = User.objects.filter(email__iexact=invitation.email).first()
    invited_user_created = user is None
    if user and not user.is_active:
        return HttpResponseForbidden("This account is inactive. Contact support to restore access.")
    if user:
        if not request.user.is_authenticated:
            login_url = reverse("accounts:login")
            return redirect(f"{login_url}?next={request.path}")
        if request.user.pk != user.pk:
            return HttpResponseForbidden(
                "Sign in with the email address that received this staff invitation."
            )

    from django.contrib.auth.forms import SetPasswordForm

    if invited_user_created:
        user = User(
            username=f"staff-{secrets.token_hex(8)}",
            email=invitation.email,
            first_name=invitation.first_name,
            last_name=invitation.last_name,
            is_active=False,
        )
        user.set_unusable_password()
    form = SetPasswordForm(user, request.POST or None) if invited_user_created else None

    if request.method == "POST":
        if form is not None and not form.is_valid():
            return render(
                request,
                "organizations/staff_invitation_accept.html",
                {
                    "invitation": invitation,
                    "form": form,
                },
            )
        with transaction.atomic():
            locked = StaffInvitation.objects.select_for_update().get(pk=invitation.pk)
            if not _invitation_valid(locked, token):
                return render(request, "organizations/staff_invitation_invalid.html", status=410)
            if not invited_user_created:
                user = User.objects.select_for_update().get(pk=user.pk)
                if not user.is_active:
                    return HttpResponseForbidden(
                        "This account is inactive. Contact support to restore access."
                    )
            if (
                not invited_user_created
                and Membership.objects.filter(organization=locked.organization, user=user).exists()
            ):
                return HttpResponseForbidden("This account already has access to this dairy.")
            if invited_user_created:
                form.save()
                user.is_active = True
                user.email_verified = True
                user.save(update_fields=["is_active", "email_verified"])
            membership = Membership.objects.create(
                user=user,
                organization=locked.organization,
                role=locked.role,
                status=Membership.Status.ACTIVE,
                invited_email=locked.email,
                joined_at=timezone.now(),
            )
            BranchAssignment.objects.bulk_create(
                [
                    BranchAssignment(membership=membership, branch=branch)
                    for branch in locked.branches.all()
                ]
            )
            membership.permissions.set(locked.permissions.all())
            locked.accepted_at = timezone.now()
            locked.save(update_fields=["accepted_at", "updated_at"])
            record_event(
                actor=user,
                organization=locked.organization,
                action="staff.invitation.accepted",
                target=locked,
                request=request,
            )
        if not request.user.is_authenticated:
            login(request, user, backend="apps.accounts.backends.EmailOrUsernameBackend")
        messages.success(
            request, f"Welcome to {invitation.organization.name}. Your staff access is active."
        )
        return redirect("business:workspace")

    return render(
        request,
        "organizations/staff_invitation_accept.html",
        {
            "invitation": invitation,
            "form": form,
        },
    )
