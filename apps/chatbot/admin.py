from django.contrib import admin

from apps.chatbot.models import PipelineLog


@admin.register(PipelineLog)
class PipelineLogAdmin(admin.ModelAdmin):
    """Admin configuration for PipelineLog model (Read-Only)."""
    list_display = ("id", "trace_id", "stage", "intent", "outcome", "latency_ms", "created_at")
    list_filter = ("stage", "intent", "outcome")
    search_fields = ("trace_id", "decision_reason", "error_message")

    def has_add_permission(self, request) -> bool:
        """Disable adding logs from admin."""
        return False

    def has_change_permission(self, request, obj=None) -> bool:
        """Disable editing logs from admin."""
        return False

    def has_delete_permission(self, request, obj=None) -> bool:
        """Disable deleting logs from admin."""
        return False