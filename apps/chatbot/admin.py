from django import forms
from django.contrib import admin

from apps.chatbot.models import BotPersona, PipelineLog, PromptTemplate, Shift, WorkingDay, Institution, ContactInfo
from django.core.exceptions import ValidationError

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


class WorkingDayAdminForm(forms.ModelForm):
    """Custom form to validate shift overlaps before saving in admin."""
    
    class Meta:
        model = WorkingDay
        fields = "__all__"

    def clean(self):
        """Validate that assigned shifts do not overlap."""
        cleaned_data = super().clean()
        shifts = cleaned_data.get("shifts")
        
        if shifts:
            shifts_list = list(shifts)
            for i in range(len(shifts_list)):
                for j in range(i + 1, len(shifts_list)):
                    s1 = shifts_list[i]
                    s2 = shifts_list[j]
                    latest_start = max(s1.start_time, s2.start_time)
                    earliest_end = min(s1.end_time, s2.end_time)
                    if latest_start < earliest_end:
                        raise ValidationError(
                            f"Shift overlap detected: {s1.name} and {s2.name} on {cleaned_data.get('day')}."
                        )
        return cleaned_data

    
@admin.register(WorkingDay)
class WorkingDayAdmin(admin.ModelAdmin):
    """Admin configuration for WorkingDay model."""
    form = WorkingDayAdminForm
    list_display = ("day",)
    filter_horizontal = ("shifts",)


@admin.register(Shift)
class ShiftAdmin(admin.ModelAdmin):
    """Admin configuration for Shift model."""
    list_display = ["name", "start_time", "end_time"]


@admin.register(Institution)
class InstitutionAdmin(admin.ModelAdmin):
    """Admin configuration for Institution model."""
    list_display = ("name", "address", "is_active")
    list_filter = ("is_active",)

@admin.register(ContactInfo)
class ContactInfoAdmin(admin.ModelAdmin):
    """Admin configuration for ContactInfo model."""
    list_display = ("institution", "type", "value", "is_support_number")
    list_filter = ("type", "is_support_number")