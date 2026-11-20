from .models import Membership, Organization

ORGANISATION_WIDE_ROLES = {
    Membership.Role.OWNER,
    Membership.Role.ADMIN,
}


def accessible_branch_ids(membership):
    """Return restricted branch IDs; only owner/admin have organisation-wide scope."""
    if membership.role in ORGANISATION_WIDE_ROLES:
        return None
    return list(membership.branch_assignments.values_list("branch_id", flat=True))


def has_organization_permission(membership, permission):
    """Check an explicit organisation capability; owners/admins retain existing authority."""
    if membership.role in ORGANISATION_WIDE_ROLES:
        return True
    return membership.permissions.filter(key=permission).exists()


def can_access_branch(membership, branch):
    if branch.organization_id != membership.organization_id:
        return False
    branch_ids = accessible_branch_ids(membership)
    return branch_ids is None or branch.pk in branch_ids


def require_actor_branch_access(*, actor, organization, branch):
    """Require active tenant membership and access to an active tenant branch."""
    from django.core.exceptions import PermissionDenied

    if (
        organization.status not in {Organization.Status.TRIAL, Organization.Status.ACTIVE}
        or branch.organization_id != organization.pk
        or not branch.is_active
        or getattr(branch, "deleted_at", None) is not None
    ):
        raise PermissionDenied("You are not authorised to access this branch.")

    membership = Membership.objects.filter(
        user=actor,
        organization=organization,
        status=Membership.Status.ACTIVE,
    ).first()
    if membership is None or not can_access_branch(membership, branch):
        raise PermissionDenied("You are not authorised to access this branch.")
    return membership
