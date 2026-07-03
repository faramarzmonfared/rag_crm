from django.db import models
import pgvector.django


class KnowledgeBaseSource(models.TextChoices):
    """Enum for the source of the knowledge base chunk."""
    COURSE = "course", "دوره"
    INSTITUTION_FAQ = "institution_faq", "سوالات متداول موسسه"


class Chunk(models.Model):
    """
    Represents a piece of text and its embedding vector for RAG retrieval.
    
    Metadata Strategy:
    - Stable Metadata (title, instructor, etc.) is injected into the `content` 
      field and becomes part of the embedding.
    - Dynamic Metadata (capacity, price, etc.) is stored ONLY in the `metadata` 
      JSONField and is used at Retrieval time, preventing unnecessary re-embeddings.
    - `content_hash` is used to detect changes in the `content` (stable data).
    """

    source_type = models.CharField(
        max_length=20,
        choices=KnowledgeBaseSource.choices,
        verbose_name="نوع منبع"
    )
    source_course_detail = models.ForeignKey(
        "courses.CourseDetail",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="chunks",
        verbose_name="جزئیات دوره منبع"
    )
    content = models.TextField(verbose_name="محتوای متنی (شامل متادیتای پایدار)")
    content_hash = models.CharField(
        max_length=64, 
        blank=True, 
        verbose_name="هش محتوا (برای تشخیص تغییرات پایدار)"
    )
    embedding = pgvector.django.VectorField(
        dimensions=1024,
        null=True,
        blank=True,
        verbose_name="بردار (Embedding)"
    )
    embedding_model_name = models.CharField(
        max_length=100,
        null=True,
        blank=True,
        verbose_name="مدل Embedding"
    )
    embedded_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name="زمان Embedding"
    )
    # Schema for this will be validated via Pydantic at the application layer later
    metadata = models.JSONField(default=dict, verbose_name="متادیتای پویا")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="تاریخ ایجاد")

    class Meta:
        """Meta configuration for Chunk."""
        verbose_name = "تکه دانش (Chunk)"
        verbose_name_plural = "تکه‌های دانش (Chunks)"

    def __str__(self) -> str:
        """Return string representation of the chunk."""
        return f"{self.source_type} Chunk {self.id}"  # type: ignore[attr-defined]