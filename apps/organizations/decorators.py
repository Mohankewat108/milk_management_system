from functools import wraps

from django.http import Http404

from .models import Membership, Organization


def organization_access(*allowed_roles):
    """Resolve tenant from slug and require active membership server-side."""

    def decorator(view_func):
        @wraps(view_func)
        def wrapped(request, organization_slug, *args, **kwargs):
            if not request.user.is_authenticated:
                raise Http404
            membership = (
                Membership.objects.select_related("organization", "user")
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
            if membership is None or (allowed_roles and membership.role not in allowed_roles):
                raise Http404
            request.membership = membership
            request.organization = membership.organization
            return view_func(request, organization_slug, *args, **kwargs)

        return wrapped

    return decorator
