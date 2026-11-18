from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Count, Sum
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST
from django.utils import timezone

from audit_logs.models import AuditLog
from operations.models import Customer, MilkCollection
from .models import Membership, Organisation


def active_memberships(user):
    return Membership.objects.filter(
        user=user,
        is_active=True,
        organisation__status__in=['active', 'trial'],
    )


@login_required
def dashboard(request):
    membership = active_memberships(request.user).select_related('organisation').first()
    if membership is None:
        return render(request, 'organizations/no_organisation.html')
    organisation = membership.organisation
    today = timezone.localdate()
    collections = MilkCollection.objects.filter(organisation=organisation, is_void=False)
    context = {
        'organisation': organisation,
        'membership': membership,
        'customer_count': Customer.objects.filter(organisation=organisation, is_active=True).count(),
        'collection_count': collections.filter(collection_date=today).count(),
        'milk_today': collections.filter(collection_date=today).aggregate(total=Sum('milk_liters'))['total'] or 0,
        'revenue_today': collections.filter(collection_date=today).aggregate(total=Sum('total_amount'))['total'] or 0,
    }
    return render(request, 'organizations/dashboard.html', context)


def is_platform_admin(user):
    return user.is_superuser or active_memberships(user).filter(role='platform_super_admin').exists()


@login_required
def platform_dashboard(request):
    if not is_platform_admin(request.user):
        messages.error(request, 'Platform administrator access required.')
        return redirect('dashboard')
    organisations = Organisation.objects.annotate(
        member_count=Count('memberships', distinct=True),
        branch_count=Count('branches', distinct=True),
    )
    context = {
        'organisations': organisations,
        'organisation_count': organisations.count(),
        'active_count': organisations.filter(status=Organisation.Status.ACTIVE).count(),
        'suspended_count': organisations.filter(status=Organisation.Status.SUSPENDED).count(),
        'trial_count': organisations.filter(status=Organisation.Status.TRIAL).count(),
    }
    return render(request, 'platform/dashboard.html', context)


@login_required
def platform_organisations(request):
    if not is_platform_admin(request.user):
        return redirect('dashboard')
    query = request.GET.get('q', '').strip()
    organisations = Organisation.objects.all()
    if query:
        organisations = organisations.filter(name__icontains=query)
    return render(request, 'platform/organisations.html', {
        'organisations': organisations.order_by('-created_at'),
        'query': query,
    })


@login_required
@require_POST
def platform_org_status(request, organisation_id):
    if not is_platform_admin(request.user):
        return redirect('dashboard')
    organisation = get_object_or_404(Organisation, id=organisation_id)
    status = request.POST.get('status')
    if status not in Organisation.Status.values:
        messages.error(request, 'Invalid organisation status.')
        return redirect('platform_organisations')
    organisation.status = status
    organisation.save(update_fields=['status', 'updated_at'])
    AuditLog.objects.create(
        organisation=organisation,
        actor=request.user,
        action='organisation_status_changed',
        object_type='Organisation',
        object_id=str(organisation.id),
        metadata={'status': status},
    )
    messages.success(request, f'{organisation.name} status changed to {status}.')
    return redirect('platform_organisations')
