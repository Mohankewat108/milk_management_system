from .models import AuditEvent


def record_event(*, actor, organization=None, action, target=None, changes=None, request=None):
    ip_address = None
    user_agent = ""
    if request is not None:
        forwarded = request.META.get("HTTP_X_FORWARDED_FOR", "")
        ip_address = (
            forwarded.split(",")[0].strip() if forwarded else request.META.get("REMOTE_ADDR")
        )
        user_agent = request.META.get("HTTP_USER_AGENT", "")[:500]
    return AuditEvent.objects.create(
        actor=actor,
        organization=organization,
        action=action,
        target_type=target.__class__.__name__ if target is not None else "",
        target_id=str(getattr(target, "pk", "")) if target is not None else "",
        changes=changes or {},
        ip_address=ip_address,
        user_agent=user_agent,
    )
