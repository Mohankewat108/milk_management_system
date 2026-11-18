import hashlib
import hmac

from django.conf import settings
from django.contrib import messages
from django.contrib.auth import get_user_model, login
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib.auth.forms import SetPasswordForm
from django.core.mail import send_mail
from django.db import transaction
from django.db.models import Count
from django.http import HttpResponseForbidden
from django.shortcuts import get_object_or_404, redirect, render
from django.template.loader import render_to_string
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_http_methods, require_POST

from apps.audit.services import record_event
from apps.organizations.models import Membership, Organization
from apps.platform_admin.forms import PlatformOrganizationCreateForm
from apps.platform_admin.models import FarmOwnerInvitation, Subscription
from apps.platform_admin.services import create_platform_organization_invitation


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
        "customer_count": Organization.objects.aggregate(total=Count("customers", distinct=True))["total"],
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
        owner_email = data.pop("owner_email")
        owner_first_name = data.pop("owner_first_name")
        owner_last_name = data.pop("owner_last_name")
        name = data.pop("name")
        organization, membership, invitation, raw_token = create_platform_organization_invitation(
            invited_by=request.user,
            owner_email=owner_email,
            owner_first_name=owner_first_name,
            owner_last_name=owner_last_name,
            name=name,
            **data,
        )
        invite_path = reverse(
            "platform:owner_invitation_accept",
            kwargs={"invitation_id": invitation.pk, "token": raw_token},
        )
        invitation_url = request.build_absolute_uri(invite_path)
        context = {
            "owner_name": owner_first_name,
            "farm_name": organization.name,
            "invitation_url": invitation_url,
            "expires_at": invitation.expires_at,
        }
        subject = f"You are invited to manage {organization.name} on DairyNexus"
        text_body = render_to_string("emails/farm_owner_invitation.txt", context)
        html_body = render_to_string("emails/farm_owner_invitation.html", context)
        try:
            send_mail(
                subject,
                text_body,
                settings.DEFAULT_FROM_EMAIL,
                [owner_email],
                html_message=html_body,
                fail_silently=False,
            )
        except Exception:
            # Do not expose the invitation token in the UI or logs. The farm
            # remains pending; the platform owner can issue a fresh invitation.
            messages.error(
                request,
                "The dairy farm was created, but the invitation email could not be sent. "
                "Check email configuration before inviting the owner again.",
            )
            record_event(
                actor=request.user, organization=organization,
                action="platform.owner_invitation.email_failed",
                target=invitation, request=request,
            )
            return redirect("platform:dashboard")

        record_event(
            actor=request.user,
            organization=organization,
            action="platform.organization.created",
            target=organization,
            changes={"owner_email": owner_email, "invitation_id": str(invitation.pk)},
            request=request,
        )
        messages.success(
            request,
            f"{organization.name} was created. An invitation was sent to {owner_email}.",
        )
        return redirect("platform:dashboard")
    return render(request, "platform/organization_form.html", {"form": form})


def _valid_invitation(invitation, raw_token):
    supplied_hash = hashlib.sha256(raw_token.encode("utf-8")).hexdigest()
    return (
        hmac.compare_digest(invitation.token_hash, supplied_hash)
        and invitation.accepted_at is None
        and invitation.revoked_at is None
        and invitation.expires_at > timezone.now()
    )


@require_http_methods(["GET", "POST"])
def owner_invitation_accept(request, invitation_id, token):
    invitation = get_object_or_404(
        FarmOwnerInvitation.objects.select_related("user", "organization"),
        pk=invitation_id,
    )
    if not _valid_invitation(invitation, token):
        return render(request, "platform/invitation_invalid.html", status=410)

    invited_user = invitation.user
    if invited_user.is_active:
        if not request.user.is_authenticated:
            login_url = reverse("accounts:login")
            return redirect(f"{login_url}?next={request.path}")
        if request.user.pk != invited_user.pk:
            return HttpResponseForbidden(
                "Sign in with the email address that received this farm invitation."
            )
        form = None
    else:
        if request.user.is_authenticated and request.user.pk != invited_user.pk:
            return HttpResponseForbidden("This invitation belongs to another account.")
        form = SetPasswordForm(invited_user, request.POST or None)

    if request.method == "POST":
        if form is not None and not form.is_valid():
            return render(request, "platform/invitation_accept.html", {
                "invitation": invitation, "form": form, "requires_password": True,
            })
        with transaction.atomic():
            locked = FarmOwnerInvitation.objects.select_for_update().get(pk=invitation.pk)
            if not _valid_invitation(locked, token):
                return render(request, "platform/invitation_invalid.html", status=410)
            user = locked.user
            if not user.is_active:
                form.save()
                user.is_active = True
                user.email_verified = True
                user.save(update_fields=["is_active", "email_verified"])
            membership = Membership.objects.select_for_update().get(
                user=user, organization=locked.organization,
                role=Membership.Role.OWNER,
            )
            membership.status = Membership.Status.ACTIVE
            membership.joined_at = timezone.now()
            membership.save(update_fields=["status", "joined_at", "updated_at"])
            locked.accepted_at = timezone.now()
            locked.save(update_fields=["accepted_at", "updated_at"])
            record_event(
                actor=user, organization=locked.organization,
                action="platform.owner_invitation.accepted",
                target=locked, request=request,
            )
        if not request.user.is_authenticated:
            login(request, user, backend="apps.accounts.backends.EmailOrUsernameBackend")
        messages.success(request, f"Welcome! You now have access to {invitation.organization.name}.")
        return redirect("business:workspace")

    return render(request, "platform/invitation_accept.html", {
        "invitation": invitation,
        "form": form,
        "requires_password": form is not None,
    })


@login_required
@user_passes_test(is_platform_owner)
@require_POST
def organization_set_status(request, organization_id):
    organization = get_object_or_404(Organization, pk=organization_id)
    new_status = request.POST.get("status", "").strip()
    reason = request.POST.get("reason", "").strip()
    allowed_statuses = {
        Organization.Status.ACTIVE,
        Organization.Status.SUSPENDED,
        Organization.Status.CLOSED,
    }
    if new_status not in allowed_statuses:
        messages.error(request, "Choose a valid farm status.")
        return redirect("platform:dashboard")
    if not reason:
        messages.error(request, "A reason is required for a farm status change.")
        return redirect("platform:dashboard")
    old_status = organization.status
    if old_status == new_status:
        messages.info(request, "The farm already has that status.")
        return redirect("platform:dashboard")
    organization.status = new_status
    organization.save(update_fields=["status", "updated_at"])
    record_event(
        actor=request.user,
        organization=organization,
        action="platform.organization.status_changed",
        target=organization,
        changes={"from": old_status, "to": new_status, "reason": reason},
        request=request,
    )
    messages.success(request, f"{organization.name} status changed to {organization.get_status_display()}.")
    return redirect("platform:dashboard")
