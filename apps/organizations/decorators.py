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
            if (
                membership.role == Membership.Role.DAIRY_MANAGER
                and permission
                and not has_organization_permission(membership, permission)
            ):
                raise Http404
            request.membership = membership
            request.organization = membership.organization
            return view_func(request, organization_slug, *args, **kwargs)

        return wrapped

    return decorator
