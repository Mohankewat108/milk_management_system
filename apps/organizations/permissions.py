def accessible_branch_ids(membership):
    """Return the member's branch scope, or None when the member has org-wide access."""
    assigned = membership.branch_assignments.values_list("branch_id", flat=True)
    values = list(assigned)
    return values or None


def can_access_branch(membership, branch):
    if branch.organization_id != membership.organization_id:
        return False
    branch_ids = accessible_branch_ids(membership)
    return branch_ids is None or branch.pk in branch_ids
