from django.contrib import admin

from .models import AuditEvent


@admin.register(AuditEvent)
class AuditEventAdmin(admin.ModelAdmin):
    list_display = ("created_at", "organization", "actor", "action", "target_type", "target_id")
    list_filter = ("action", "organization")
    search_fields = ("actor__email", "action", "target_id")
    readonly_fields = (
        "organization", "actor", "action", "target_type", "target_id",
        "changes", "ip_address", "user_agent", "created_at", "updated_at",
    )

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
