from django.contrib.auth.views import (
    PasswordChangeDoneView,
    PasswordChangeView,
    PasswordResetCompleteView,
    PasswordResetConfirmView,
    PasswordResetDoneView,
    PasswordResetView,
)
from django.urls import path, reverse_lazy

from .views import AccountLoginView, account_logout, register_account
from apps.organizations.staff_views import staff_invitation_accept

app_name = "accounts"

urlpatterns = [
    path("register/", register_account, name="register"),
    path("staff-invitations/<uuid:invitation_id>/<str:token>/", staff_invitation_accept, name="staff_invitation_accept"),
    path("login/", AccountLoginView.as_view(), name="login"),
    path("logout/", account_logout, name="logout"),
    path("password/change/", PasswordChangeView.as_view(
        template_name="accounts/password_change.html",
        success_url=reverse_lazy("accounts:password_change_done"),
    ), name="password_change"),
    path("password/change/done/", PasswordChangeDoneView.as_view(
        template_name="accounts/password_change_done.html",
    ), name="password_change_done"),
    path("password/reset/", PasswordResetView.as_view(
        template_name="accounts/password_reset.html",
        email_template_name="emails/password_reset.txt",
        success_url=reverse_lazy("accounts:password_reset_done"),
    ), name="password_reset"),
    path("password/reset/done/", PasswordResetDoneView.as_view(
        template_name="accounts/password_reset_done.html",
    ), name="password_reset_done"),
    path("password/reset/<uidb64>/<token>/", PasswordResetConfirmView.as_view(
        template_name="accounts/password_reset_confirm.html",
        success_url=reverse_lazy("accounts:password_reset_complete"),
    ), name="password_reset_confirm"),
    path("password/reset/complete/", PasswordResetCompleteView.as_view(
        template_name="accounts/password_reset_complete.html",
    ), name="password_reset_complete"),
]
