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
