from django.contrib import messages
from django.contrib.auth import login, logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.views import LoginView
from django.shortcuts import redirect, render
from django.views.decorators.http import require_http_methods, require_POST

from .forms import EmailAuthenticationForm, UserRegistrationForm


class AccountLoginView(LoginView):
    template_name = "accounts/login.html"
    authentication_form = EmailAuthenticationForm
    redirect_authenticated_user = True


@require_http_methods(["GET", "POST"])
def register_account(request):
    if request.user.is_authenticated:
        return redirect("business:workspace")
    form = UserRegistrationForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        user = form.save()
        login(request, user, backend="apps.accounts.backends.EmailOrUsernameBackend")
        messages.success(request, "Account created. Set up your dairy workspace to continue.")
        return redirect("business:register")
    return render(request, "accounts/register.html", {"form": form})


@login_required
@require_POST
def account_logout(request):
    logout(request)
    messages.success(request, "You have been securely signed out.")
    return redirect("accounts:login")
