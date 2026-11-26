import hashlib
import secrets
from datetime import timedelta
from uuid import uuid4

from django.contrib.auth import get_user_model
from django.db import transaction
from django.utils import timezone
from django.utils.text import slugify

from apps.organizations.models import Branch, Membership, Organization
from apps.platform_admin.models import FarmOwnerInvitation, Subscription

User = get_user_model()


def _username_for_email(email):
    base = slugify(email.split("@", 1)[0])[:120] or "farm-owner"
    candidate = base
    while User.objects.filter(username__iexact=candidate).exists():
        candidate = f"{base[:110]}-{secrets.token_hex(4)}"
    return candidate


@transaction.atomic
def create_platform_organization_invitation(
    *,
    invited_by,
    owner_email,
    owner_first_name,
    owner_last_name="",
    name,
    subscription_plan,
    **details,
):
    """Create a tenant and invite its owner without assigning a password.

    Existing accounts are reused. New accounts are inactive and have an
    unusable password until the recipient accepts the email invitation.
    """
    email = owner_email.strip().lower()
    user = User.objects.filter(email__iexact=email).first()
    if user is None:
        user = User.objects.create(
            username=_username_for_email(email),
            email=email,
            first_name=owner_first_name.strip(),
            last_name=owner_last_name.strip(),
            is_active=False,
        )
        user.set_unusable_password()
        user.save(update_fields=["password"])

    base = slugify(name)[:150] or "dairy"
    organization = Organization.objects.create(
        owner=user,
        name=name.strip(),
        slug=f"{base}-{uuid4().hex[:8]}",
        status=Organization.Status.TRIAL,
        **details,
    )
    membership = Membership.objects.create(
        user=user,
        organization=organization,
        role=Membership.Role.OWNER,
        status=Membership.Status.INVITED,
    )
    Branch.objects.create(
        organization=organization,
        code="MAIN",
        name="Main branch",
        address=organization.address,
        phone=organization.phone,
    )

    today = timezone.localdate()
    Subscription.objects.create(
        organization=organization,
        plan=subscription_plan,
        status=Subscription.Status.TRIAL,
        starts_at=today,
        ends_at=today + timedelta(days=14),
    )

    # Revoke outstanding invitations for this same tenant/email before issuing
    # a fresh token, so only the newest invitation can be used.
    FarmOwnerInvitation.objects.filter(
        organization=organization,
        email=email,
        accepted_at__isnull=True,
        revoked_at__isnull=True,
    ).update(revoked_at=timezone.now())

    raw_token = secrets.token_urlsafe(32)
    invitation = FarmOwnerInvitation.objects.create(
        organization=organization,
        user=user,
        invited_by=invited_by,
        email=email,
        token_hash=hashlib.sha256(raw_token.encode("utf-8")).hexdigest(),
        expires_at=timezone.now() + timedelta(hours=48),
    )
    return organization, membership, invitation, raw_token


@transaction.atomic
def create_platform_organization_manual_owner(
    *,
    invited_by,
    owner_first_name,
    owner_last_name="",
    username,
    temporary_password,
    name,
    subscription_plan,
    phone_number="",
    **details,
):
    """Create a farm and active owner account for people without email access."""
    username = username.strip()
    # The account email field is required and unique by the custom User model;
    # use a clearly non-deliverable internal address for phone/username accounts.
    placeholder_email = f"{slugify(username)[:100]}-{uuid4().hex[:8]}@no-email.dairynexus.invalid"
    user = User.objects.create(
        username=username,
        email=placeholder_email,
        first_name=owner_first_name.strip(),
        last_name=owner_last_name.strip(),
        phone_number=phone_number.strip(),
        is_active=True,
        email_verified=False,
    )
    user.set_password(temporary_password)
    user.save(update_fields=["password"])

    base = slugify(name)[:150] or "dairy"
    organization = Organization.objects.create(
        owner=user,
        name=name.strip(),
        slug=f"{base}-{uuid4().hex[:8]}",
        status=Organization.Status.TRIAL,
        **details,
    )
    membership = Membership.objects.create(
        user=user,
        organization=organization,
        role=Membership.Role.OWNER,
        status=Membership.Status.ACTIVE,
        joined_at=timezone.now(),
    )
    Branch.objects.create(
        organization=organization,
        code="MAIN",
        name="Main branch",
        address=organization.address,
        phone=organization.phone,
    )
    today = timezone.localdate()
    Subscription.objects.create(
        organization=organization,
        plan=subscription_plan,
        status=Subscription.Status.TRIAL,
        starts_at=today,
        ends_at=today + timedelta(days=14),
    )
    return organization, membership, user
