from django.core.exceptions import ValidationError
from django.db import models

from typing import Any

from apps.leads.validators import IranMobileValidator


class Lead(models.Model):
    """Represents a potential customer interacting with the chatbot."""

    class Status(models.TextChoices):
        """Enum for lead status."""
        NEW = "new", "جدید"
        NEEDS_FOLLOWUP = "needs_followup", "نیازمند پیگیری"
        CONVERTED = "converted", "تبدیل شده"

    first_name = models.CharField(max_length=100, verbose_name="نام")
    last_name = models.CharField(max_length=100, verbose_name="نام خانوادگی")
    phone_number = models.CharField(max_length=15, unique=True, verbose_name="شماره تماس")
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.NEW, verbose_name="وضعیت")
    aggregated_summary = models.TextField(blank=True, verbose_name="خلاصه تجمیعی مکالمات")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="تاریخ ثبت")

    class Meta:
        """Meta configuration for Lead."""
        verbose_name = "ردیابی (Lead)"
        verbose_name_plural = "ردیابی‌ها (Leads)"

    def __str__(self) -> str:
        """Return string representation of the lead."""
        return f"{self.first_name} {self.last_name} - {self.phone_number}"

    def clean(self) -> None:
        """Validate and normalize the phone number before saving."""
        validator = IranMobileValidator(strict=True, output_format="local", debug=False)
        result = validator.validate(str(self.phone_number))
        if not result.is_valid:
            raise ValidationError({"phone_number": "Invalid Iranian mobile number."})
        self.phone_number = result.normalized

    def save(self, *args: Any, **kwargs: Any) -> None:
        """Override save to enforce validation."""
        self.full_clean()
        super().save(*args, **kwargs)


class Conversation(models.Model):
    """Represents a single chat session for a lead."""

    lead = models.ForeignKey(
        Lead,
        on_delete=models.CASCADE,
        related_name="conversations",
        verbose_name="ردیابی"
    )
    started_at = models.DateTimeField(auto_now_add=True, verbose_name="زمان شروع")
    ended_at = models.DateTimeField(null=True, blank=True, verbose_name="زمان پایان")
    is_active = models.BooleanField(default=True, verbose_name="فعال")

    class Meta:
        """Meta configuration for Conversation."""
        verbose_name = "مکالمه"
        verbose_name_plural = "مکالمه‌ها"

    def __str__(self) -> str:
        """Return string representation of the conversation."""
        return f"Conversation {self.id} for Lead {self.lead_id}"  # type: ignore[attr-defined]


class Message(models.Model):
    """Represents a single message in a conversation."""

    class Sender(models.TextChoices):
        """Enum for message sender."""
        USER = "user", "کاربر"
        BOT = "bot", "بات"

    conversation = models.ForeignKey(
        Conversation,
        on_delete=models.CASCADE,
        related_name="messages",
        verbose_name="مکالمه"
    )
    sender = models.CharField(max_length=10, choices=Sender.choices, verbose_name="فرستنده")
    content = models.TextField(verbose_name="متن پیام")
    timestamp = models.DateTimeField(auto_now_add=True, verbose_name="زمان ارسال")

    class Meta:
        """Meta configuration for Message."""
        verbose_name = "پیام"
        verbose_name_plural = "پیام‌ها"
        ordering = ["timestamp"]

    def __str__(self) -> str:
        """Return string representation of the message."""
        return f"{self.sender} at {self.timestamp:%Y-%m-%d %H:%M}"  # type: ignore[attr-defined]