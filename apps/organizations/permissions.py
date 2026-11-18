from .models import Membership


ORGANISATION_WIDE_ROLES = {
    Membership.Role.OWNER,
    Membership.Role.ADMIN,
}


def accessible_branch_ids(membership):
    """Return restricted branch IDs; organisation-wide roles get None."""
    if membership.role in ORGANISATION_WIDE_ROLES:
        return None
    return list(membership.branch_assignments.values_list("branch_id", flat=True))


def can_access_branch(membership, branch):
    if branch.organization_id != membership.organization_id:
        return False
    branch_ids = accessible_branch_ids(membership)
    return branch_ids is None or branch.pk in branch_ids



def require_actor_branch_access(*, actor, organization, branch):
    """Reject service-layer writes unless the actor has active access to this branch."""
    from django.core.exceptions import PermissionDenied

    membership = Membership.objects.filter(
        user=actor,
        organization=organization,
        status=Membership.Status.ACTIVE,
    ).first()
    if membership is None or not can_access_branch(membership, branch):
        raise PermissionDenied("You are not authorised to access this branch.")
    return membership
