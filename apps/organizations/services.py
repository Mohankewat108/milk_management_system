from uuid import uuid4

from django.db import transaction
from django.utils import timezone
from django.utils.text import slugify

from .models import Branch, Membership, Organization


@transaction.atomic
def register_organization(
    *, user, name, legal_name="", phone="", email="", country="Nepal", address=""
):
    base = slugify(name)[:150] or "dairy"
    organization = Organization.objects.create(
        owner=user,
        name=name,
        legal_name=legal_name,
        slug=f"{base}-{uuid4().hex[:8]}",
        phone=phone,
        email=email,
        country=country,
    )
    Membership.objects.create(
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
        address=address,
        phone=phone,
    )
    return organization
