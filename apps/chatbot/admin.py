from django.contrib import admin

from apps.chatbot.models import BotPersona, PipelineLog, PromptTemplate


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


@admin.register(BotPersona)
class BotPersonaAdmin(admin.ModelAdmin):
    """Admin configuration for BotPersona model."""
    list_display = ("name", "tone_of_voice", "is_active")
    list_filter = ("is_active",)

@admin.register(PromptTemplate)
class PromptTemplateAdmin(admin.ModelAdmin):
    """Admin configuration for PromptTemplate model."""
    list_display = ("persona", "stage", "created_at")
    list_filter = ("persona", "stage")