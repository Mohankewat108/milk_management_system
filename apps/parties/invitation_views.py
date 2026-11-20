import secrets

from django.contrib import messages
from django.contrib.auth import get_user_model, login
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import SetPasswordForm
from django.core.cache import cache
from django.core.exceptions import ValidationError
from django.db import transaction
from django.http import HttpResponseForbidden
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.utils.text import slugify
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_http_methods, require_POST

from apps.audit.services import record_event
from apps.organizations.decorators import organization_access
from apps.organizations.models import Membership

from .invitations import resend_farmer_invitation, revoke_farmer_invitation, send_farmer_invitation, valid_invitation
from .models import Farmer, FarmerInvitation

User = get_user_model()


def _farmer_for_request(request, organization_slug, farmer_id):
    return get_object_or_404(
        Farmer.objects.filter(
            organization=request.organization,
            deleted_at__isnull=True,
        ).select_related("organization"),
        pk=farmer_id,
    )


def _rate_limit(request, farmer):
    key = f"dairynexus:farmer-invite:{request.user.pk}:{farmer.pk}"
    return cache.add(key, 1, timeout=60)


@login_required
@organization_access(
    Membership.Role.OWNER,
    Membership.Role.ADMIN,
    Membership.Role.BRANCH_MANAGER,
)
@require_POST
def send_invitation(request, organization_slug, farmer_id):
    farmer = _farmer_for_request(request, organization_slug, farmer_id)
    if not _rate_limit(request, farmer):
        messages.error(request, "Please wait one minute before sending another invitation.")
        return redirect("parties:farmer_detail", organization_slug=organization_slug, farmer_id=farmer.pk)
    try:
        send_farmer_invitation(actor=request.user, farmer=farmer, request=request)
    except ValidationError as exc:
        messages.error(request, "; ".join(exc.messages))
    except Exception:
        messages.error(
            request,
            "The invitation was created but the email could not be delivered. "
            "Check the email configuration and resend the invitation.",
        )
    else:
        messages.success(request, f"Invitation sent to {farmer.email}.")
    return redirect("parties:farmer_detail", organization_slug=organization_slug, farmer_id=farmer.pk)


@login_required
@organization_access(
    Membership.Role.OWNER,
    Membership.Role.ADMIN,
    Membership.Role.BRANCH_MANAGER,
)
@require_POST
def resend_invitation(request, organization_slug, farmer_id):
    farmer = _farmer_for_request(request, organization_slug, farmer_id)
    if not _rate_limit(request, farmer):
        messages.error(request, "Please wait one minute before resending this invitation.")
        return redirect("parties:farmer_detail", organization_slug=organization_slug, farmer_id=farmer.pk)
    try:
        resend_farmer_invitation(actor=request.user, farmer=farmer, request=request)
    except ValidationError as exc:
        messages.error(request, "; ".join(exc.messages))
    except Exception:
        messages.error(request, "The resend email could not be delivered. The previous link was revoked.")
    else:
        messages.success(request, f"A fresh invitation was sent to {farmer.email}.")
    return redirect("parties:farmer_detail", organization_slug=organization_slug, farmer_id=farmer.pk)


@login_required
@organization_access(
    Membership.Role.OWNER,
    Membership.Role.ADMIN,
    Membership.Role.BRANCH_MANAGER,
)
@require_POST
def revoke_invitation(request, organization_slug, farmer_id):
    farmer = _farmer_for_request(request, organization_slug, farmer_id)
    try:
        revoke_farmer_invitation(actor=request.user, farmer=farmer, request=request)
    except ValidationError as exc:
        messages.error(request, "; ".join(exc.messages))
    else:
        messages.success(request, "The farmer invitation was revoked.")
    return redirect("parties:farmer_detail", organization_slug=organization_slug, farmer_id=farmer.pk)


def _username_for_email(email):
    base = slugify(email.split("@", 1)[0])[:120] or "farmer"
    candidate = base
    while User.objects.filter(username__iexact=candidate).exists():
        candidate = f"{base[:110]}-{secrets.token_hex(4)}"
    return candidate


@never_cache
@require_http_methods(["GET", "POST"])
def accept_invitation(request, invitation_id, token):
    invitation = get_object_or_404(
        FarmerInvitation.objects.select_related("organization", "farmer"),
        pk=invitation_id,
    )
    if not valid_invitation(invitation, token):
        if (
            invitation.status in {FarmerInvitation.Status.PENDING, FarmerInvitation.Status.SENT}
            and invitation.expires_at <= timezone.now()
        ):
            invitation.status = FarmerInvitation.Status.EXPIRED
            invitation.save(update_fields=["status", "updated_at"])
            record_event(
                actor=None,
                organization=invitation.organization,
                action="farmer.invitation.expired",
                target=invitation,
                changes={"farmer_id": str(invitation.farmer_id)},
                request=request,
            )
        return render(request, "parties/farmer_invitation_invalid.html", {"invitation": invitation}, status=410)

    if (
        request.user.is_authenticated
        and request.user.email.strip().lower() != invitation.email.strip().lower()
    ):
        return HttpResponseForbidden("This invitation belongs to another account.")

    existing = User.objects.filter(email__iexact=invitation.email).first()
    if existing is not None and (existing.is_staff or existing.is_superuser):
        return HttpResponseForbidden(
            "This account cannot be activated through a farmer invitation."
        )
    if existing is not None and existing.is_active:
        if not request.user.is_authenticated:
            return redirect(f"{reverse('accounts:login')}?next={request.path}")
        if request.user.pk != existing.pk:
            return HttpResponseForbidden("Sign in with the email address that received this invitation.")
        user = existing
        form = None
    else:
        if request.user.is_authenticated and existing is not None and request.user.pk != existing.pk:
            return HttpResponseForbidden("This invitation belongs to another account.")
        user = existing or User(
            username=_username_for_email(invitation.email),
            email=invitation.email,
            first_name=invitation.farmer.full_name[:150],
            is_active=False,
        )
        form = SetPasswordForm(user, request.POST or None)

    if request.method == "POST":
        if form is not None and not form.is_valid():
            return render(
                request,
                "parties/farmer_invitation_accept.html",
                {"invitation": invitation, "form": form, "requires_password": True},
            )
        with transaction.atomic():
            locked = FarmerInvitation.objects.select_for_update().select_related(
                "organization", "farmer"
            ).get(pk=invitation.pk)
            if not valid_invitation(locked, token):
                return render(
                    request,
                    "parties/farmer_invitation_invalid.html",
                    {"invitation": locked},
                    status=410,
                )
            if (
                locked.farmer.organization_id != locked.organization_id
                or locked.farmer.email.strip().lower() != locked.email.strip().lower()
            ):
                return render(
                    request,
                    "parties/farmer_invitation_invalid.html",
                    {"invitation": locked},
                    status=410,
                )
            if existing is None:
                user.set_password(form.cleaned_data["new_password1"])
                user.is_active = True
                user.email_verified = True
                user.save()
            else:
                if not user.is_active:
                    form.save()
                    user.is_active = True
                    user.email_verified = True
                    user.save(update_fields=["is_active", "email_verified"])
                elif user.is_active:
                    user.email_verified = True
                    user.save(update_fields=["email_verified"])

            farmer = locked.farmer
            if farmer.user_id not in (None, user.pk):
                return HttpResponseForbidden("This farmer profile is already linked to another account.")
            linked_farmer = getattr(user, "farmer_profile", None)
            if linked_farmer is not None and linked_farmer.pk != farmer.pk:
                return HttpResponseForbidden("This account is already linked to another farmer.")
            farmer.user = user
            farmer.is_active = True
            farmer.save(update_fields=["user", "is_active", "updated_at"])

            locked.status = FarmerInvitation.Status.ACCEPTED
            locked.accepted_at = timezone.now()
            locked.save(update_fields=["status", "accepted_at", "updated_at"])
            record_event(
                actor=user,
                organization=locked.organization,
                action="farmer.invitation.accepted",
                target=locked,
                changes={"farmer_id": str(farmer.pk), "email": locked.email},
                request=request,
            )
        if not request.user.is_authenticated:
            login(request, user, backend="apps.accounts.backends.EmailOrUsernameBackend")
        messages.success(
            request,
            f"Welcome! Your farmer account for {locked.organization.name} is now active.",
        )
        return redirect("farmer_portal:home")

    return render(
        request,
        "parties/farmer_invitation_accept.html",
        {"invitation": invitation, "form": form, "requires_password": form is not None},
    )
