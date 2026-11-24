from .models import Membership, Organization

ORGANISATION_WIDE_ROLES = {
    Membership.Role.OWNER,
    Membership.Role.ADMIN,
}


# Default role capabilities are centrally defined and can be extended by explicit
# grants stored on a membership. Dairy managers use their explicitly assigned grants.
ROLE_PERMISSION_DEFAULTS = {
    Membership.Role.DAIRY_MANAGER: set(),
    Membership.Role.BRANCH_MANAGER: {
        "dashboard.view", "parties.view", "parties.manage",
        "collections.view", "collections.create",
        "reports.view", "exports.create",
    },
    Membership.Role.COLLECTION_OPERATOR: {
        "dashboard.view", "collections.view", "collections.create", "exports.create",
    },
    Membership.Role.QUALITY_OFFICER: {
        "dashboard.view", "collections.view", "collections.approve", "reports.view", "exports.create",
    },
    Membership.Role.ACCOUNTANT: {
        "dashboard.view", "finance.view", "finance.manage", "reports.view", "exports.create",
    },
    Membership.Role.INVENTORY_MANAGER: {
        "dashboard.view", "inventory.view", "inventory.manage", "reports.view", "exports.create",
    },
    Membership.Role.SUPPORT: {
        "dashboard.view", "parties.view", "reports.view",
    },
}


def accessible_branch_ids(membership):
    """Return restricted branch IDs; only owner/admin have organisation-wide scope."""
    if membership.role in ORGANISATION_WIDE_ROLES:
        return None
    return list(membership.branch_assignments.values_list("branch_id", flat=True))


def has_organization_permission(membership, permission):
    """Check a capability; write grants imply the matching read capability."""
    if membership.role in ORGANISATION_WIDE_ROLES:
        return True
    implied = {
        "collections.view": {"collections.create", "collections.approve"},
        "parties.view": {"parties.manage"},
        "finance.view": {"finance.manage"},
        "inventory.view": {"inventory.manage"},
    }
    granted_keys = {permission, *implied.get(permission, set())}
    if permission in ROLE_PERMISSION_DEFAULTS.get(membership.role, set()):
        return True
    if any(key in ROLE_PERMISSION_DEFAULTS.get(membership.role, set()) for key in granted_keys):
        return True
    return membership.permissions.filter(key__in=granted_keys).exists()


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
