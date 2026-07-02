from django.contrib import admin

from apps.leads.models import Conversation, Lead, Message


@admin.register(Lead)
class LeadAdmin(admin.ModelAdmin):
    """Admin configuration for Lead model."""
    list_display = ("id", "first_name", "last_name", "phone_number", "status", "created_at")
    list_filter = ("status",)
    search_fields = ("first_name", "last_name", "phone_number")


@admin.register(Conversation)
class ConversationAdmin(admin.ModelAdmin):
    """Admin configuration for Conversation model (Read-Only)."""
    list_display = ("id", "lead", "started_at", "ended_at", "is_active")
    list_filter = ("is_active",)
    search_fields = ("lead__phone_number",)

    def has_add_permission(self, request) -> bool:
        """Disable adding conversations from admin."""
        return False

    def has_change_permission(self, request, obj=None) -> bool:
        """Disable editing conversations from admin."""
        return False

    def has_delete_permission(self, request, obj=None) -> bool:
        """Disable deleting conversations from admin."""
        return False


@admin.register(Message)
class MessageAdmin(admin.ModelAdmin):
    """Admin configuration for Message model (Read-Only)."""
    list_display = ("id", "conversation", "sender", "timestamp")
    list_filter = ("sender",)
    search_fields = ("content",)

    def has_add_permission(self, request) -> bool:
        """Disable adding messages from admin."""
        return False

    def has_change_permission(self, request, obj=None) -> bool:
        """Disable editing messages from admin."""
        return False

    def has_delete_permission(self, request, obj=None) -> bool:
        """Disable deleting messages from admin."""
        return False