from django.contrib import messages
from django.contrib.auth import login, logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.views import LoginView
from django.core.cache import cache
from django.http import HttpResponse
from django.shortcuts import redirect, render
from django.urls import reverse
from django.views.decorators.http import require_http_methods, require_POST

from .forms import EmailAuthenticationForm, UserRegistrationForm


class AccountLoginView(LoginView):
    template_name = "accounts/login.html"
    authentication_form = EmailAuthenticationForm
    redirect_authenticated_user = True
    max_attempts = 10
    lockout_seconds = 900

    def get_default_redirect_url(self):
        """
        Send platform administrators to the central control centre.
        Django's get_success_url() still honours a safe ?next= URL first.
        """
        if self.request.user.is_superuser:
            return reverse("platform:dashboard")
        return super().get_default_redirect_url()

    def rate_key(self):
        ip = self.request.META.get("REMOTE_ADDR", "unknown")
        return f"dairynexus:login-attempts:{ip}"

    def dispatch(self, request, *args, **kwargs):
        if cache.get(self.rate_key(), 0) >= self.max_attempts:
            return HttpResponse(
                "Too many failed login attempts. Try again in 15 minutes.",
                status=429,
                content_type="text/plain",
            )
        return super().dispatch(request, *args, **kwargs)

    def form_invalid(self, form):
        key = self.rate_key()
        if not cache.add(key, 0, timeout=self.lockout_seconds):
            try:
                cache.incr(key)
            except ValueError:
                cache.set(key, 1, timeout=self.lockout_seconds)
        else:
            cache.incr(key)
        return super().form_invalid(form)

    def form_valid(self, form):
        cache.delete(self.rate_key())
        return super().form_valid(form)


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
