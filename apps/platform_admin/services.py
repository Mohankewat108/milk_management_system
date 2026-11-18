from uuid import uuid4

from django.db import transaction
from django.utils import timezone
from django.utils.text import slugify

from apps.organizations.models import Branch, Membership, Organization


@transaction.atomic
def create_platform_organization(*, owner, name, **details):
    """Create one tenant, its owner membership and its initial branch atomically.

    The owner can own multiple organisations. Every organisation receives its
    own tenant record and main branch; no customer or operational records are
    shared between organisations.
    """
    base = slugify(name)[:150] or "dairy"
    slug = f"{base}-{uuid4().hex[:8]}"
    organization = Organization.objects.create(
        owner=owner,
        name=name.strip(),
        slug=slug,
        status=Organization.Status.TRIAL,
        **details,
    )
    Membership.objects.create(
        user=owner,
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
    return organization
