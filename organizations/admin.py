from django.contrib import admin

# Register your models here.
from django.contrib import admin

from .models import Organisation, Membership, Branch


@admin.register(Organisation)
class OrganisationAdmin(admin.ModelAdmin):
    list_display = ('name', 'slug', 'status', 'created_at')
    list_filter = ('status',)
    search_fields = ('name', 'slug')


@admin.register(Membership)
class MembershipAdmin(admin.ModelAdmin):
    list_display = ('organisation', 'user', 'role', 'is_active')
    list_filter = ('role', 'is_active')


@admin.register(Branch)
class BranchAdmin(admin.ModelAdmin):
    list_display = ('organisation', 'name', 'is_active')
