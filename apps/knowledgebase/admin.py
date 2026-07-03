from django.contrib import admin

from apps.knowledgebase.models import Chunk


@admin.register(Chunk)
class ChunkAdmin(admin.ModelAdmin):
    """Admin configuration for Chunk model."""
    list_display = ("id", "source_type", "content_hash", "embedding_model_name", "embedded_at")
    list_filter = ("source_type", "embedding_model_name")
    search_fields = ("content",)