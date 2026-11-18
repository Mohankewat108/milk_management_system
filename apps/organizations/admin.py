from django.contrib import admin

from .models import Branch, BranchAssignment, Membership, Organization


class BranchInline(admin.TabularInline):
    model = Branch
    extra = 0


@admin.register(Organization)
class OrganizationAdmin(admin.ModelAdmin):
    list_display = ("name", "slug", "owner", "status", "country", "created_at")
    list_filter = ("status", "country")
    search_fields = ("name", "legal_name", "email", "registration_number")
    inlines = [BranchInline]


@admin.register(Membership)
class MembershipAdmin(admin.ModelAdmin):
    list_display = ("user", "organization", "role", "status", "joined_at")
    list_filter = ("role", "status", "organization")
    search_fields = ("user__email", "organization__name")


admin.site.register(BranchAssignment)
