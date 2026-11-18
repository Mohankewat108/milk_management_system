from django.contrib import admin

# Register your models here.
from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from .models import User


@admin.register(User)
class CustomUserAdmin(UserAdmin):
    fieldsets = UserAdmin.fieldsets + (
        ('DairyNexus', {'fields': ('phone_number', 'email_verified', 'phone_verified', 'profile_photo', 'preferred_language', 'timezone')}),
    )
