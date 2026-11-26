import hashlib
import hmac
import secrets
from datetime import timedelta

from django.conf import settings
from django.contrib import messages
from django.contrib.auth import get_user_model, login
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib.auth.forms import SetPasswordForm
from django.core.mail import send_mail
from django.db import transaction
from django.db.models import Count
from django.http import HttpResponseForbidden
from django.shortcuts import get_object_or_404, redirect, render
from django.template.loader import render_to_string
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_http_methods, require_POST

from apps.audit.services import record_event
from apps.core.site_urls import build_site_absolute_uri
from apps.organizations.models import Membership, Organization
from apps.platform_admin.forms import PlatformOrganizationCreateForm
from apps.platform_admin.models import FarmOwnerInvitation, Subscription, SubscriptionPlan
from apps.platform_admin.services import (
    create_platform_organization_invitation,
    create_platform_organization_manual_owner,
)

User = get_user_model()


def is_platform_owner(user):
    return user.is_authenticated and user.is_superuser


@login_required
@user_passes_test(is_platform_owner)
def dashboard(request):
    from django.db.models import Exists, OuterRef

    pending_owner_membership = Membership.objects.filter(
        organization_id=OuterRef("pk"),
        role=Membership.Role.OWNER,
        status=Membership.Status.INVITED,
    )
    organizations = (
        Organization.objects.select_related("owner")
        .annotate(
            member_count=Count("memberships", distinct=True),
            customer_count=Count("customers", distinct=True),
            farmer_count=Count("farmers", distinct=True),
            owner_invitation_pending=Exists(pending_owner_membership),
        )
        .order_by("-created_at")
    )
    today = timezone.localdate()
    upcoming_expiry = (
        Subscription.objects.filter(
            status__in=[Subscription.Status.ACTIVE, Subscription.Status.TRIAL],
            ends_at__gte=today,
            ends_at__lte=today + timedelta(days=30),
        )
        .select_related("plan", "organization")
        .order_by("ends_at")
    )
    active_subscription_values = Subscription.objects.filter(
        status=Subscription.Status.ACTIVE
    ).select_related("plan")
    estimated_mrr = sum((sub.plan.monthly_price for sub in active_subscription_values), start=0)
    from apps.audit.models import AuditEvent

    context = {
        "estimated_mrr": estimated_mrr,
        "expiring_subscriptions": upcoming_expiry[:8],
        "expiring_subscription_count": upcoming_expiry.count(),
        "past_due_subscription_count": Subscription.objects.filter(
            status=Subscription.Status.PAST_DUE
        ).count(),
        "recent_organizations": Organization.objects.select_related("owner").order_by(
            "-created_at"
        )[:5],
        "recent_activity": AuditEvent.objects.select_related("actor", "organization").order_by(
            "-created_at"
        )[:8],
        "organization_count": Organization.objects.count(),
        "active_organizations": Organization.objects.filter(
            status=Organization.Status.ACTIVE
        ).count(),
        "trial_organizations": Organization.objects.filter(
            status=Organization.Status.TRIAL
        ).count(),
        "suspended_organizations": Organization.objects.filter(
            status=Organization.Status.SUSPENDED
        ).count(),
        "user_count": User.objects.count(),
        "customer_count": Organization.objects.aggregate(total=Count("customers", distinct=True))[
            "total"
        ],
        "subscription_count": Subscription.objects.count(),
        "organizations": organizations,
    }
    return render(request, "platform/dashboard.html", context)


@login_required
@user_passes_test(is_platform_owner)
@require_http_methods(["GET", "POST"])
def organization_create(request):
    form = PlatformOrganizationCreateForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        data = form.cleaned_data.copy()
        invitation_method = data.pop("invitation_method", "email")
        owner_email = data.pop("owner_email", "")
        manual_username = data.pop("manual_username", "")
        manual_password = data.pop("manual_password", "")
        owner_first_name = data.pop("owner_first_name")
        owner_last_name = data.pop("owner_last_name")
        name = data.pop("name")
        subscription_plan = data.pop("subscription_plan")
        if invitation_method == "manual":
            organization, membership, owner_user = create_platform_organization_manual_owner(
                invited_by=request.user,
                owner_first_name=owner_first_name,
                owner_last_name=owner_last_name,
                username=manual_username,
                temporary_password=manual_password,
                name=name,
                subscription_plan=subscription_plan,
                phone_number=data.get("phone", ""),
                **data,
            )
            record_event(
                actor=request.user,
                organization=organization,
                action="platform.organization.created_manual_owner",
                target=membership,
                changes={"owner_username": manual_username, "account_method": "manual"},
                request=request,
            )
            messages.success(
                request,
                f"Farm {organization.name} created. Owner login: {manual_username}. "
                f"Temporary password: {manual_password}. "
                "Give these credentials directly to the owner.",
            )
            return redirect("platform:dashboard")

        organization, membership, invitation, raw_token = create_platform_organization_invitation(
            invited_by=request.user,
            owner_email=owner_email,
            owner_first_name=owner_first_name,
            owner_last_name=owner_last_name,
            name=name,
            subscription_plan=subscription_plan,
            **data,
        )
        invite_path = reverse(
            "platform:owner_invitation_accept",
            kwargs={"invitation_id": invitation.pk, "token": raw_token},
        )
        invitation_url = build_site_absolute_uri(request, invite_path)
        context = {
            "owner_name": owner_first_name,
            "farm_name": organization.name,
            "invitation_url": invitation_url,
            "expires_at": invitation.expires_at,
        }
        subject = f"You are invited to manage {organization.name} on Dairy Nepal"
        text_body = render_to_string("emails/farm_owner_invitation.txt", context)
        html_body = render_to_string("emails/farm_owner_invitation.html", context)
        try:
            send_mail(
                subject,
                text_body,
                settings.DEFAULT_FROM_EMAIL,
                [owner_email],
                html_message=html_body,
                fail_silently=False,
            )
        except Exception:
            # Do not expose the invitation token in the UI or logs. The farm
            # remains pending; the platform owner can issue a fresh invitation.
            messages.error(
                request,
                "The dairy farm was created, but the invitation email could not be sent. "
                "Check email configuration before inviting the owner again.",
            )
            record_event(
                actor=request.user,
                organization=organization,
                action="platform.owner_invitation.email_failed",
                target=invitation,
                request=request,
            )
            return redirect("platform:dashboard")

        record_event(
            actor=request.user,
            organization=organization,
            action="platform.organization.created",
            target=organization,
            changes={"owner_email": owner_email, "invitation_id": str(invitation.pk)},
            request=request,
        )
        messages.success(
            request,
            f"{organization.name} was created. An invitation was sent to {owner_email}.",
        )
        return redirect("platform:dashboard")
    return render(
        request,
        "platform/organization_form.html",
        {
            "form": form,
            "active_subscription_plans": SubscriptionPlan.objects.filter(is_active=True).order_by(
                "monthly_price"
            ),
        },
    )


def _valid_invitation(invitation, raw_token):
    supplied_hash = hashlib.sha256(raw_token.encode("utf-8")).hexdigest()
    return (
        hmac.compare_digest(invitation.token_hash, supplied_hash)
        and invitation.accepted_at is None
        and invitation.revoked_at is None
        and invitation.expires_at > timezone.now()
    )


@never_cache
@require_http_methods(["GET", "POST"])
def owner_invitation_accept(request, invitation_id, token):
    invitation = get_object_or_404(
        FarmOwnerInvitation.objects.select_related("user", "organization"),
        pk=invitation_id,
    )
    if not _valid_invitation(invitation, token):
        return render(request, "platform/invitation_invalid.html", status=410)

    invited_user = invitation.user
    if invited_user.is_active:
        if not request.user.is_authenticated:
            login_url = reverse("accounts:login")
            return redirect(f"{login_url}?next={request.path}")
        if request.user.pk != invited_user.pk:
            return HttpResponseForbidden(
                "Sign in with the email address that received this farm invitation."
            )
        form = None
    else:
        if request.user.is_authenticated and request.user.pk != invited_user.pk:
            return HttpResponseForbidden("This invitation belongs to another account.")
        form = SetPasswordForm(invited_user, request.POST or None)

    if request.method == "POST":
        if form is not None and not form.is_valid():
            return render(
                request,
                "platform/invitation_accept.html",
                {
                    "invitation": invitation,
                    "form": form,
                    "requires_password": True,
                },
            )
        with transaction.atomic():
            locked = FarmOwnerInvitation.objects.select_for_update().get(pk=invitation.pk)
            if not _valid_invitation(locked, token):
                return render(request, "platform/invitation_invalid.html", status=410)
            user = locked.user
            if not user.is_active:
                form.save()
                user.is_active = True
            if not user.email_verified:
                user.email_verified = True
            user.save(update_fields=["is_active", "email_verified"])
            membership = Membership.objects.select_for_update().get(
                user=user,
                organization=locked.organization,
                role=Membership.Role.OWNER,
            )
            membership.status = Membership.Status.ACTIVE
            membership.joined_at = timezone.now()
            membership.save(update_fields=["status", "joined_at", "updated_at"])
            locked.accepted_at = timezone.now()
            locked.save(update_fields=["accepted_at", "updated_at"])
            record_event(
                actor=user,
                organization=locked.organization,
                action="platform.owner_invitation.accepted",
                target=locked,
                request=request,
            )
        if not request.user.is_authenticated:
            login(request, user, backend="apps.accounts.backends.EmailOrUsernameBackend")
        messages.success(
            request, f"Welcome! You now have access to {invitation.organization.name}."
        )
        return redirect("business:workspace")

    return render(
        request,
        "platform/invitation_accept.html",
        {
            "invitation": invitation,
            "form": form,
            "requires_password": form is not None,
        },
    )


@login_required
@user_passes_test(is_platform_owner)
@require_POST
def organization_set_status(request, organization_id):
    organization = get_object_or_404(Organization, pk=organization_id)
    new_status = request.POST.get("status", "").strip()
    reason = request.POST.get("reason", "").strip()
    allowed_statuses = {
        Organization.Status.ACTIVE,
        Organization.Status.SUSPENDED,
        Organization.Status.CLOSED,
    }
    if new_status not in allowed_statuses:
        messages.error(request, "Choose a valid farm status.")
        return redirect("platform:dashboard")
    if not reason:
        messages.error(request, "A reason is required for a farm status change.")
        return redirect("platform:dashboard")
    old_status = organization.status
    if old_status == new_status:
        messages.info(request, "The farm already has that status.")
        return redirect("platform:dashboard")
    organization.status = new_status
    organization.save(update_fields=["status", "updated_at"])
    record_event(
        actor=request.user,
        organization=organization,
        action="platform.organization.status_changed",
        target=organization,
        changes={"from": old_status, "to": new_status, "reason": reason},
        request=request,
    )
    messages.success(
        request, f"{organization.name} status changed to {organization.get_status_display()}."
    )
    return redirect("platform:dashboard")


@login_required
@user_passes_test(is_platform_owner)
@require_POST
def organization_delete(request, organization_id):
    organization = get_object_or_404(Organization, pk=organization_id)
    confirmation = request.POST.get("confirm_name", "").strip()
    if confirmation != organization.name:
        messages.error(request, "Farm deletion cancelled: the confirmation name did not match.")
        return redirect("platform:dashboard")

    from django.db.models.deletion import ProtectedError

    from apps.audit.models import AuditEvent
    from apps.collections.models import MilkCollection
    from apps.finance.models import Expense, Payment

    # Never hard-delete farms with business/financial history.
    protected_counts = {
        "milk collections": MilkCollection.objects.filter(organization=organization).count(),
        "payments": Payment.objects.filter(organization=organization).count(),
        "expenses": Expense.objects.filter(organization=organization).count(),
    }
    nonzero = {label: count for label, count in protected_counts.items() if count}
    if nonzero:
        details = ", ".join(f"{count} {label}" for label, count in nonzero.items())
        messages.error(
            request,
            f"{organization.name} cannot be deleted because it has records ({details}). "
            "Close or suspend it instead.",
        )
        return redirect("platform:dashboard")

    org_name = organization.name
    org_id = str(organization.pk)
    try:
        with transaction.atomic():
            Subscription.objects.filter(organization=organization).delete()
            FarmOwnerInvitation.objects.filter(organization=organization).delete()
            AuditEvent.objects.filter(organization=organization).delete()
            organization.delete()
            record_event(
                actor=request.user,
                organization=None,
                action="platform.organization.deleted",
                target=None,
                changes={"organization_id": org_id, "organization_name": org_name},
                request=request,
            )
    except ProtectedError:
        messages.error(
            request,
            f"{org_name} contains protected data and could not be deleted. No data was removed.",
        )
        return redirect("platform:dashboard")

    messages.success(request, f"{org_name} was deleted. Its owner account was not deleted.")
    return redirect("platform:dashboard")


@login_required
@user_passes_test(is_platform_owner)
@require_POST
def organization_resend_invitation(request, organization_id):
    organization = get_object_or_404(
        Organization.objects.select_related("owner"), pk=organization_id
    )
    get_object_or_404(
        Membership,
        organization=organization,
        user=organization.owner,
        role=Membership.Role.OWNER,
        status=Membership.Status.INVITED,
    )
    email = organization.owner.email
    raw_token = secrets.token_urlsafe(32)
    with transaction.atomic():
        FarmOwnerInvitation.objects.filter(
            organization=organization,
            email=email,
            accepted_at__isnull=True,
            revoked_at__isnull=True,
        ).update(revoked_at=timezone.now())
        invitation = FarmOwnerInvitation.objects.create(
            organization=organization,
            user=organization.owner,
            invited_by=request.user,
            email=email,
            token_hash=hashlib.sha256(raw_token.encode("utf-8")).hexdigest(),
            expires_at=timezone.now() + timedelta(hours=48),
        )
    invite_path = reverse(
        "platform:owner_invitation_accept",
        kwargs={"invitation_id": invitation.pk, "token": raw_token},
    )
    context = {
        "owner_name": organization.owner.first_name,
        "farm_name": organization.name,
        "invitation_url": build_site_absolute_uri(request, invite_path),
        "expires_at": invitation.expires_at,
    }
    try:
        send_mail(
            f"Your Dairy Nepal invitation for {organization.name}",
            render_to_string("emails/farm_owner_invitation.txt", context),
            settings.DEFAULT_FROM_EMAIL,
            [email],
            html_message=render_to_string("emails/farm_owner_invitation.html", context),
            fail_silently=False,
        )
    except Exception:
        messages.error(request, "The invitation could not be sent. Check the SMTP configuration.")
        record_event(
            actor=request.user,
            organization=organization,
            action="platform.owner_invitation.resend_failed",
            target=invitation,
            request=request,
        )
        return redirect("platform:dashboard")
    record_event(
        actor=request.user,
        organization=organization,
        action="platform.owner_invitation.resent",
        target=invitation,
        request=request,
    )
    messages.success(
        request, f"A fresh invitation was sent to {email}. The previous link is no longer valid."
    )
    return redirect("platform:dashboard")


@login_required
@user_passes_test(is_platform_owner)
@require_POST
def organization_reset_owner_password(request, organization_id):
    organization = get_object_or_404(
        Organization.objects.select_related("owner"), pk=organization_id
    )
    owner = organization.owner
    temporary_password = secrets.token_urlsafe(12)
    owner.set_password(temporary_password)
    owner.force_password_change = True
    owner.save(update_fields=["password", "force_password_change"])
    record_event(
        actor=request.user,
        organization=organization,
        action="platform.organization.owner_password_reset",
        target=owner,
        changes={"force_password_change": True, "reset_by_platform_owner": True},
        request=request,
    )
    messages.warning(
        request,
        f"Temporary password for {owner.username}: {temporary_password}. "
        "Provide it directly to the owner. They must change it at next login.",
    )
    return redirect("platform:dashboard")
