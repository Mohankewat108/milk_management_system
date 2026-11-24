from functools import wraps

from django.http import Http404

from .models import Membership, Organization
from .permissions import has_organization_permission


def organization_access(*allowed_roles, permission=None):
    """Resolve tenant from slug and require active membership and optional capability."""

    def decorator(view_func):
        @wraps(view_func)
        def wrapped(request, organization_slug, *args, **kwargs):
            if not request.user.is_authenticated:
                raise Http404
            membership = (
                Membership.objects.select_related("organization", "user")
                .prefetch_related("permissions")
                .filter(
                    user=request.user,
                    organization__slug=organization_slug,
                    organization__status__in=[
                        Organization.Status.TRIAL,
                        Organization.Status.ACTIVE,
                    ],
                    status=Membership.Status.ACTIVE,
                )
                .first()
            )
            if membership is None:
                raise Http404
            if allowed_roles and membership.role not in allowed_roles:
                raise Http404
            if permission and not has_organization_permission(membership, permission):
                raise Http404
            request.membership = membership
            request.organization = membership.organization
            request.can_dashboard = has_organization_permission(membership, "dashboard.view")
            request.can_parties = has_organization_permission(membership, "parties.view")
            request.can_collections = has_organization_permission(membership, "collections.view")
            request.can_finance = has_organization_permission(membership, "finance.view")
            request.can_inventory = has_organization_permission(membership, "inventory.view")
            request.can_exports = has_organization_permission(membership, "exports.create")
            request.can_reports = has_organization_permission(membership, "reports.view")
            return view_func(request, organization_slug, *args, **kwargs)

        return wrapped

    return decorator
