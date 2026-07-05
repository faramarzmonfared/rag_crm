from django.db import models
from apps.leads.models import Message


class Intent(models.TextChoices):
    """Enum for user intents based on query understanding."""
    COURSE_SPECIFIC = "course_specific", "Course Specific"
    INSTITUTION_FAQ = "institution_faq", "Institution FAQ"
    STRUCTURED_LOOKUP = "structured_lookup", "Structured Lookup"
    SMALL_TALK = "small_talk", "Small Talk"
    UNCLEAR_NEEDS_CLARIFICATION = "unclear_needs_clarification", "Unclear (Needs Clarification)"
    UNCLEAR_UNANSWERABLE = "unclear_unanswerable", "Unclear (Unanswerable)"
    OUT_OF_SCOPE = "out_of_scope", "Out of Scope"


class PipelineLog(models.Model):
    """
    Tracks technical execution details of the RAG pipeline for debugging.
    
    Architecture Notes:
    - trace_id is generated once per user message at the service layer and passed down.
    - QUERY_UNDERSTANDING uses a sliding window of recent messages from the active 
      Conversation as context, not just the latest message.
    - Routing intents (SMALL_TALK, UNCLEAR_*, OUT_OF_SCOPE) dictate the pipeline path:
      - SMALL_TALK / OUT_OF_SCOPE: No retrieval, direct LLM response.
      - UNCLEAR_NEEDS_CLARIFICATION: Bot asks a clarifying question.
      - UNCLEAR_UNANSWERABLE: Triggers Human Handoff.
    """

    class Stage(models.TextChoices):
        """Enum for pipeline stages."""
        QUERY_UNDERSTANDING = "query_understanding", "Query Understanding"
        ROUTING = "routing", "Routing"
        RETRIEVAL = "retrieval", "Retrieval"
        RESPONSE_GENERATION = "response_generation", "Response Generation"
        HANDOFF = "handoff", "Human Handoff"

    class Outcome(models.TextChoices):
        """Enum for stage outcome."""
        SUCCESS = "success", "Success"
        FAILED_HARD = "failed_hard", "Failed (Exception)"
        SUCCESS_BUT_LOW_CONFIDENCE = "success_but_low_confidence", "Success (Low Confidence)"

    message = models.ForeignKey(
        Message,
        on_delete=models.CASCADE,
        related_name="pipeline_logs",
        verbose_name="پیام کاربر"
    )
    trace_id = models.UUIDField(editable=False, db_index=True, verbose_name="Trace ID")
    stage = models.CharField(max_length=30, choices=Stage.choices, verbose_name="مرحله")
    outcome = models.CharField(max_length=40, choices=Outcome.choices, verbose_name="نتیجه")
    intent = models.CharField(
        max_length=40, 
        choices=Intent.choices, 
        blank=True, 
        verbose_name="قصد کاربر (Intent)"
    )
    model_name = models.CharField(max_length=100, blank=True, verbose_name="مدل استفاده شده")
    latency_ms = models.PositiveIntegerField(null=True, blank=True, verbose_name="تاخیر (میلی‌ثانیه)")
    input_data = models.JSONField(default=dict, verbose_name="ورودی مرحله")
    output_data = models.JSONField(default=dict, verbose_name="خروجی مرحله")
    error_message = models.TextField(blank=True, verbose_name="پیام خطا")
    retrieved_chunk_ids = models.JSONField(default=list, blank=True, verbose_name="شناسه چانک‌های بازیابی شده")
    similarity_scores = models.JSONField(default=list, blank=True, verbose_name="امتیازات شباهت")
    decision_reason = models.TextField(blank=True, verbose_name="دلیل تصمیم (Routing)")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="تاریخ ثبت")

    class Meta:
        """Meta configuration for PipelineLog."""
        verbose_name = "لاگ پایپ‌لاین"
        verbose_name_plural = "لاگ‌های پایپ‌لاین"
        ordering = ["created_at"]

    def __str__(self) -> str:
        """Return string representation of the pipeline log."""
        return f"Log {self.id} - {self.stage} - {self.trace_id}"  # type: ignore[attr-defined]