import hashlib
import hmac
import secrets
from datetime import timedelta

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.mail import send_mail
from django.core.validators import validate_email
from django.db import transaction
from django.template.loader import render_to_string
from django.urls import reverse
from django.utils import timezone

from apps.audit.services import record_event
from apps.core.site_urls import build_site_absolute_uri

from .models import FarmerInvitation


def hash_invitation_token(raw_token):
    return hashlib.sha256(raw_token.encode("utf-8")).hexdigest()


def valid_invitation(invitation, raw_token):
    supplied_hash = hash_invitation_token(raw_token)
    return (
        hmac.compare_digest(invitation.token_hash, supplied_hash)
        and invitation.status
        in {
            FarmerInvitation.Status.PENDING,
            FarmerInvitation.Status.SENT,
        }
        and invitation.accepted_at is None
        and invitation.revoked_at is None
        and invitation.expires_at > timezone.now()
    )


def expire_stale_invitations(farmer):
    now = timezone.now()
    stale = farmer.invitations.filter(
        status__in=[FarmerInvitation.Status.PENDING, FarmerInvitation.Status.SENT],
        expires_at__lte=now,
    )
    for invitation in stale:
        invitation.status = FarmerInvitation.Status.EXPIRED
        invitation.save(update_fields=["status", "updated_at"])
        record_event(
            actor=None,
            organization=invitation.organization,
            action="farmer.invitation.expired",
            target=invitation,
            changes={"farmer_id": str(farmer.pk)},
        )


@transaction.atomic
def create_farmer_invitation(
    *,
    actor,
    farmer,
    request=None,
):
    farmer = farmer.__class__.objects.select_for_update().get(pk=farmer.pk)
    if farmer.deleted_at is not None:
        raise ValidationError("A deleted farmer cannot be invited.")
    email = farmer.email.strip().lower()
    if not email:
        raise ValidationError("Add the farmer's email address before sending an invitation.")
    try:
        validate_email(email)
    except ValidationError as exc:
        raise ValidationError("Enter a valid email address before sending the invitation.") from exc

    expire_stale_invitations(farmer)
    active = farmer.invitations.filter(
        status__in=[FarmerInvitation.Status.PENDING, FarmerInvitation.Status.SENT]
    ).first()
    if active is not None:
        raise ValidationError("A pending invitation already exists. Resend or revoke it instead.")

    expiry_hours = settings.FARMER_INVITATION_EXPIRY_HOURS
    if expiry_hours <= 0:
        raise ValidationError("Farmer invitation expiry must be configured as a positive value.")

    raw_token = secrets.token_urlsafe(32)
    expires_at = timezone.now() + timedelta(hours=expiry_hours)
    invitation = FarmerInvitation.objects.create(
        organization=farmer.organization,
        farmer=farmer,
        invited_by=actor,
        email=email,
        token_hash=hash_invitation_token(raw_token),
        status=FarmerInvitation.Status.PENDING,
        expires_at=expires_at,
    )
    record_event(
        actor=actor,
        organization=farmer.organization,
        action="farmer.invitation.created",
        target=invitation,
        changes={"farmer_id": str(farmer.pk), "email": email},
        request=request,
    )
    return invitation, raw_token


def send_farmer_invitation(*, actor, farmer, request):
    invitation, raw_token = create_farmer_invitation(
        actor=actor,
        farmer=farmer,
        request=request,
    )
    invite_path = reverse(
        "parties:farmer_invitation_accept",
        kwargs={"invitation_id": invitation.pk, "token": raw_token},
    )
    invitation_url = build_site_absolute_uri(request, invite_path)
    context = {
        "farmer_name": farmer.full_name,
        "farm_name": farmer.organization.name,
        "invitation_url": invitation_url,
        "expires_at": invitation.expires_at,
        "support_email": getattr(settings, "DEFAULT_FROM_EMAIL", ""),
    }
    subject = f"You are invited to join {farmer.organization.name} — Farmer Portal"
    text_body = render_to_string("emails/farmer_invitation.txt", context)
    html_body = render_to_string("emails/farmer_invitation.html", context)
    try:
        send_mail(
            subject,
            text_body,
            settings.DEFAULT_FROM_EMAIL,
            [invitation.email],
            html_message=html_body,
            fail_silently=False,
        )
    except Exception:
        invitation.status = FarmerInvitation.Status.FAILED
        invitation.failed_at = timezone.now()
        invitation.save(update_fields=["status", "failed_at", "updated_at"])
        record_event(
            actor=actor,
            organization=farmer.organization,
            action="farmer.invitation.email_failed",
            target=invitation,
            changes={"farmer_id": str(farmer.pk), "email": invitation.email},
            request=request,
        )
        raise

    invitation.status = FarmerInvitation.Status.SENT
    invitation.sent_at = timezone.now()
    invitation.save(update_fields=["status", "sent_at", "updated_at"])
    record_event(
        actor=actor,
        organization=farmer.organization,
        action="farmer.invitation.sent",
        target=invitation,
        changes={"farmer_id": str(farmer.pk), "email": invitation.email},
        request=request,
    )
    return invitation


def resend_farmer_invitation(*, actor, farmer, request):
    expire_stale_invitations(farmer)
    active = farmer.invitations.filter(
        status__in=[FarmerInvitation.Status.PENDING, FarmerInvitation.Status.SENT]
    ).first()
    if active is not None:
        active.status = FarmerInvitation.Status.REVOKED
        active.revoked_at = timezone.now()
        active.save(update_fields=["status", "revoked_at", "updated_at"])
        record_event(
            actor=actor,
            organization=farmer.organization,
            action="farmer.invitation.resent",
            target=active,
            changes={"farmer_id": str(farmer.pk), "superseded": True},
            request=request,
        )
    return send_farmer_invitation(actor=actor, farmer=farmer, request=request)


@transaction.atomic
def revoke_farmer_invitation(*, actor, farmer, request=None):
    invitation = farmer.invitations.filter(
        status__in=[FarmerInvitation.Status.PENDING, FarmerInvitation.Status.SENT]
    ).first()
    if invitation is None:
        raise ValidationError("There is no active invitation to revoke.")
    invitation.status = FarmerInvitation.Status.REVOKED
    invitation.revoked_at = timezone.now()
    invitation.save(update_fields=["status", "revoked_at", "updated_at"])
    record_event(
        actor=actor,
        organization=farmer.organization,
        action="farmer.invitation.revoked",
        target=invitation,
        changes={"farmer_id": str(farmer.pk)},
        request=request,
    )
    return invitation
