from .models import Membership, Organization


def memberships_for_user(user):
    return (
        Membership.objects.select_related("organization")
        .filter(
            user=user,
            status=Membership.Status.ACTIVE,
            organization__status__in=[Organization.Status.TRIAL, Organization.Status.ACTIVE],
        )
        .order_by("organization__name")
    )
