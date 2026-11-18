from decimal import Decimal

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth import get_user_model
from django.db import transaction
from django.http import HttpResponse
from django.shortcuts import redirect, render
from django.utils import timezone
import csv

from audit_logs.models import AuditLog
from organizations.models import Branch, Membership
from .models import (
    Customer,
    Expense,
    Farmer,
    InventoryItem,
    MilkCollection,
    Payment,
    PricingConfiguration,
    StaffMember,
    SupportTicket,
)


def tenant_membership(request):
    return (
        Membership.objects
        .filter(
            user=request.user,
            is_active=True,
            organisation__status__in=['active', 'trial'],
        )
        .select_related('organisation')
        .first()
    )


@login_required
def customer_list(request):
    membership = tenant_membership(request)
    if membership is None:
        return redirect('dashboard')
    customers = Customer.objects.filter(
        organisation=membership.organisation,
        is_active=True,
    ).select_related('branch').order_by('name')
    return render(request, 'operations/customer_list.html', {
        'customers': customers,
        'organisation': membership.organisation,
    })


@login_required
def customer_create(request):
    membership = tenant_membership(request)
    if membership is None:
        return redirect('dashboard')
    organisation = membership.organisation
    branches = Branch.objects.filter(organisation=organisation, is_active=True)
    if request.method == 'POST':
        branch_id = request.POST.get('branch')
        try:
            branch = branches.get(id=branch_id)
        except Branch.DoesNotExist:
            messages.error(request, 'Please select a valid branch.')
            return redirect('customer_create')
        customer = Customer.objects.create(
            organisation=organisation,
            branch=branch,
            name=request.POST.get('name', '').strip(),
            phone_number=request.POST.get('phone_number', '').strip(),
            email=request.POST.get('email', '').strip(),
            city=request.POST.get('city', '').strip(),
            village=request.POST.get('village', '').strip(),
            ward=request.POST.get('ward', '').strip(),
        )
        AuditLog.objects.create(
            organisation=organisation,
            actor=request.user,
            action='customer_created',
            object_type='Customer',
            object_id=str(customer.id),
        )
        messages.success(request, 'Customer created.')
        return redirect('customer_list')
    return render(request, 'operations/customer_form.html', {
        'branches': branches,
        'organisation': organisation,
    })


@login_required
def collection_list(request):
    membership = tenant_membership(request)
    if membership is None:
        return redirect('dashboard')
    collections = MilkCollection.objects.filter(
        organisation=membership.organisation,
        is_void=False,
    ).select_related('customer', 'branch').order_by('-collection_date', '-created_at')
    return render(request, 'operations/collection_list.html', {
        'collections': collections,
        'organisation': membership.organisation,
    })


@login_required
@transaction.atomic
def collection_create(request):
    membership = tenant_membership(request)
    if membership is None:
        return redirect('dashboard')
    organisation = membership.organisation
    branches = Branch.objects.filter(organisation=organisation, is_active=True)
    customers = Customer.objects.filter(organisation=organisation, is_active=True).select_related('branch')
    if request.method == 'POST':
        try:
            branch = branches.get(id=request.POST.get('branch'))
            customer = customers.get(id=request.POST.get('customer'))
            milk_liters = Decimal(request.POST.get('milk_liters'))
            snf = Decimal(request.POST.get('snf'))
            fat = Decimal(request.POST.get('fat'))
            lacto = Decimal(request.POST.get('lacto'))
            collection_date = request.POST.get('collection_date')
            if milk_liters <= 0 or snf < 0 or fat < 0 or lacto < 0:
                raise ValueError
            pricing = PricingConfiguration.objects.filter(
                organisation=organisation,
                branch=branch,
                effective_from__lte=collection_date,
            ).order_by('-effective_from').first()
            if pricing is None:
                messages.error(request, 'Configure pricing for this branch before recording milk.')
                return redirect('collection_create')
            milk_rate = (snf * pricing.snf_rate) + (fat * pricing.fat_rate) + (lacto * pricing.lacto_rate)
            total_amount = (milk_liters * milk_rate).quantize(Decimal('0.01'))
            collection = MilkCollection.objects.create(
                organisation=organisation,
                branch=branch,
                customer=customer,
                recorded_by=request.user,
                milk_liters=milk_liters,
                snf=snf,
                fat=fat,
                lacto=lacto,
                milk_rate=milk_rate,
                total_amount=total_amount,
                collection_date=collection_date,
            )
            AuditLog.objects.create(
                organisation=organisation,
                actor=request.user,
                action='milk_collection_created',
                object_type='MilkCollection',
                object_id=str(collection.id),
            )
            messages.success(request, f'Milk collection saved. Amount: {total_amount}')
            return redirect('collection_list')
        except (Branch.DoesNotExist, Customer.DoesNotExist, ValueError):
            messages.error(request, 'Invalid branch, customer, date, or measurement value.')
    return render(request, 'operations/collection_form.html', {
        'branches': branches,
        'customers': customers,
        'organisation': organisation,
        'today': timezone.localdate(),
    })


@login_required
def branch_create(request):
    membership = tenant_membership(request)
    if membership is None:
        return redirect('dashboard')
    if request.method == 'POST':
        name = request.POST.get('name', '').strip()
        if name:
            branch, created = Branch.objects.get_or_create(
                organisation=membership.organisation,
                name=name,
                defaults={
                    'address': request.POST.get('address', '').strip(),
                    'phone': request.POST.get('phone', '').strip(),
                },
            )
            if created:
                messages.success(request, 'Branch created.')
            else:
                messages.error(request, 'A branch with that name already exists.')
            return redirect('dashboard')
    return render(request, 'operations/branch_form.html', {'organisation': membership.organisation})


@login_required
def pricing_create(request):
    membership = tenant_membership(request)
    if membership is None:
        return redirect('dashboard')
    branches = Branch.objects.filter(organisation=membership.organisation, is_active=True)
    if request.method == 'POST':
        try:
            branch = branches.get(id=request.POST.get('branch'))
            config, created = PricingConfiguration.objects.update_or_create(
                organisation=membership.organisation,
                branch=branch,
                effective_from=request.POST.get('effective_from'),
                defaults={
                    'snf_rate': Decimal(request.POST.get('snf_rate')),
                    'fat_rate': Decimal(request.POST.get('fat_rate')),
                    'lacto_rate': Decimal(request.POST.get('lacto_rate')),
                },
            )
            if created:
                messages.success(request, 'Historical pricing configuration added.')
            else:
                messages.success(request, 'Pricing configuration updated.')
            return redirect('pricing_create')
        except (Branch.DoesNotExist, ValueError):
            messages.error(request, 'Invalid pricing values or branch.')
    return render(request, 'operations/pricing_form.html', {
        'branches': branches,
        'organisation': membership.organisation,
        'today': timezone.localdate(),
    })


@login_required
def farmer_list(request):
    membership = tenant_membership(request)
    if membership is None:
        return redirect('dashboard')
    farmers = Farmer.objects.filter(organisation=membership.organisation, is_active=True).select_related('branch')
    return render(request, 'operations/farmer_list.html', {'farmers': farmers})


@login_required
def farmer_create(request):
    membership = tenant_membership(request)
    if membership is None:
        return redirect('dashboard')
    branches = Branch.objects.filter(organisation=membership.organisation, is_active=True)
    if request.method == 'POST':
        try:
            branch = branches.get(id=request.POST.get('branch'))
            Farmer.objects.create(
                organisation=membership.organisation,
                branch=branch,
                name=request.POST.get('name', '').strip(),
                phone_number=request.POST.get('phone_number', '').strip(),
            )
            messages.success(request, 'Farmer created.')
            return redirect('farmer_list')
        except Branch.DoesNotExist:
            messages.error(request, 'Please select a valid branch.')
    return render(request, 'operations/farmer_form.html', {'branches': branches})


@login_required
def staff_list(request):
    membership = tenant_membership(request)
    if membership is None:
        return redirect('dashboard')
    staff = StaffMember.objects.filter(organisation=membership.organisation, is_active=True).select_related('user', 'branch')
    return render(request, 'operations/staff_list.html', {'staff': staff})


@login_required
def staff_create(request):
    membership = tenant_membership(request)
    if membership is None:
        return redirect('dashboard')
    branches = Branch.objects.filter(organisation=membership.organisation, is_active=True)
    if request.method == 'POST':
        try:
            branch = branches.get(id=request.POST.get('branch'))
            User = get_user_model()
            user, created = User.objects.get_or_create(
                username=request.POST.get('username', '').strip(),
                defaults={
                    'email': request.POST.get('email', '').strip(),
                    'first_name': request.POST.get('first_name', '').strip(),
                },
            )
            if created:
                user.set_password(request.POST.get('password', 'ChangeMe123!'))
                user.save(update_fields=['password'])
            StaffMember.objects.create(
                organisation=membership.organisation,
                branch=branch,
                user=user,
                employee_code=request.POST.get('employee_code', '').strip(),
            )
            role = request.POST.get('role')
            if role not in Membership.Role.values:
                role = Membership.Role.MILK_COLLECTION_OPERATOR
            Membership.objects.update_or_create(
                organisation=membership.organisation,
                user=user,
                defaults={'role': role, 'is_active': True},
            )
            messages.success(request, 'Staff account and organisation membership created.')
            return redirect('staff_list')
        except (Branch.DoesNotExist, User.DoesNotExist):
            messages.error(request, 'Please provide valid staff details.')
    return render(request, 'operations/staff_form.html', {
        'branches': branches,
        'roles': Membership.Role.choices,
    })


@login_required
def payment_create(request):
    membership = tenant_membership(request)
    if membership is None:
        return redirect('dashboard')
    organisation = membership.organisation
    branches = Branch.objects.filter(organisation=organisation, is_active=True)
    customers = Customer.objects.filter(organisation=organisation, is_active=True)
    if request.method == 'POST':
        try:
            branch = branches.get(id=request.POST.get('branch'))
            customer_id = request.POST.get('customer')
            customer = customers.get(id=customer_id) if customer_id else None
            amount = Decimal(request.POST.get('amount'))
            if amount <= 0:
                raise ValueError
            Payment.objects.create(
                organisation=organisation,
                branch=branch,
                customer=customer,
                amount=amount,
                payment_date=request.POST.get('payment_date'),
                reference=request.POST.get('reference', '').strip(),
                method=request.POST.get('method', 'cash'),
                recorded_by=request.user,
                notes=request.POST.get('notes', '').strip(),
            )
            messages.success(request, 'Payment recorded.')
            return redirect('dashboard')
        except (Branch.DoesNotExist, Customer.DoesNotExist, ValueError):
            messages.error(request, 'Invalid payment information.')
    return render(request, 'operations/payment_form.html', {
        'branches': branches,
        'customers': customers,
        'today': timezone.localdate(),
    })


@login_required
def expense_create(request):
    membership = tenant_membership(request)
    if membership is None:
        return redirect('dashboard')
    organisation = membership.organisation
    branches = Branch.objects.filter(organisation=organisation, is_active=True)
    if request.method == 'POST':
        try:
            branch = branches.get(id=request.POST.get('branch'))
            amount = Decimal(request.POST.get('amount'))
            if amount <= 0:
                raise ValueError
            Expense.objects.create(
                organisation=organisation,
                branch=branch,
                category=request.POST.get('category', '').strip(),
                amount=amount,
                expense_date=request.POST.get('expense_date'),
                vendor=request.POST.get('vendor', '').strip(),
                reference=request.POST.get('reference', '').strip(),
                recorded_by=request.user,
                notes=request.POST.get('notes', '').strip(),
            )
            messages.success(request, 'Expense recorded.')
            return redirect('dashboard')
        except (Branch.DoesNotExist, ValueError):
            messages.error(request, 'Invalid expense information.')
    return render(request, 'operations/expense_form.html', {
        'branches': branches,
        'today': timezone.localdate(),
    })


@login_required
def inventory_list(request):
    membership = tenant_membership(request)
    if membership is None:
        return redirect('dashboard')
    items = InventoryItem.objects.filter(
        organisation=membership.organisation,
        is_active=True,
    ).select_related('branch', 'supplier')
    return render(request, 'operations/inventory_list.html', {'items': items})


@login_required
def support_list(request):
    membership = tenant_membership(request)
    if membership is None:
        return redirect('dashboard')
    if request.method == 'POST':
        subject = request.POST.get('subject', '').strip()
        description = request.POST.get('description', '').strip()
        if subject and description:
            SupportTicket.objects.create(
                organisation=membership.organisation,
                subject=subject,
                description=description,
                requested_by=request.user,
            )
            messages.success(request, 'Support request submitted.')
            return redirect('support_list')
    tickets = SupportTicket.objects.filter(
        organisation=membership.organisation,
    ).filter(requested_by=request.user).order_by('-created_at')
    return render(request, 'operations/support_list.html', {'tickets': tickets})


@login_required
def customer_portal(request):
    try:
        customer = request.user.customer_profile
    except Customer.DoesNotExist:
        messages.error(request, 'This account is not linked to a milk customer.')
        return redirect('dashboard')
    collections = MilkCollection.objects.filter(
        organisation=customer.organisation,
        customer=customer,
        is_void=False,
    ).order_by('-collection_date')
    payments = Payment.objects.filter(
        organisation=customer.organisation,
        customer=customer,
    ).order_by('-payment_date')
    return render(request, 'operations/customer_portal.html', {
        'customer': customer,
        'collections': collections,
        'payments': payments,
    })


@login_required
def collections_csv(request):
    membership = tenant_membership(request)
    if membership is None:
        return redirect('dashboard')
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="milk_collections.csv"'
    writer = csv.writer(response)
    writer.writerow(['Date', 'Customer', 'Branch', 'Litres', 'SNF', 'FAT', 'Lacto', 'Rate', 'Amount'])
    for collection in MilkCollection.objects.filter(
        organisation=membership.organisation,
        is_void=False,
    ).select_related('customer', 'branch').order_by('-collection_date'):
        writer.writerow([
            collection.collection_date,
            collection.customer.name,
            collection.branch.name,
            collection.milk_liters,
            collection.snf,
            collection.fat,
            collection.lacto,
            collection.milk_rate,
            collection.total_amount,
        ])
    return response
