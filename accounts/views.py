from django.contrib import messages
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render
from django.views.decorators.http import require_POST

from organizations.models import Branch, Membership, Organisation
from .forms import RegistrationForm


def login_view(request):
    if request.user.is_authenticated:
        return redirect('dashboard')
    if request.method == 'POST':
        user = authenticate(request, username=request.POST.get('username'), password=request.POST.get('password'))
        if user is not None:
            login(request, user)
            return redirect('dashboard')
        messages.error(request, 'Invalid username or password.')
    return render(request, 'accounts/login.html')


@require_POST
def logout_view(request):
    logout(request)
    return redirect('login')


def register_view(request):
    if request.method == 'POST':
        form = RegistrationForm(request.POST)
        organisation_name = request.POST.get('organisation_name', '').strip()
        organisation_slug = request.POST.get('organisation_slug', '').strip().lower()
        if form.is_valid() and organisation_name and organisation_slug:
            user = form.save()
            organisation = Organisation.objects.create(
                name=organisation_name,
                slug=organisation_slug,
            )
            Membership.objects.create(
                organisation=organisation,
                user=user,
                role=Membership.Role.DAIRY_OWNER,
            )
            Branch.objects.create(
                organisation=organisation,
                name='Main Branch',
            )
            login(request, user)
            return redirect('dashboard')
        if organisation_name and organisation_slug:
            messages.error(request, 'Please correct the registration errors.')
    else:
        form = RegistrationForm()
    return render(request, 'accounts/register.html', {'form': form})
