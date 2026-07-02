from django.db import models


class Department(models.Model):
    """Represents a course department at the institution."""

    name = models.CharField(max_length=255, verbose_name="نام")
    url = models.URLField(unique=True, verbose_name="لینک")

    class Meta:
        """Meta configuration for Department."""
        verbose_name = "دپارتمان"
        verbose_name_plural = "دپارتمان‌ها"

    def __str__(self) -> str:
        """Return string representation of the department."""
        return self.name


class Course(models.Model):
    """Represents a course offering with details scraped from the source."""

    class Status(models.TextChoices):
        """Enum for course enrollment status."""
        ENROLLING = "enrolling", "در حال ثبت‌نام"
        FILLING = "filling", "در حال تکمیل ظرفیت"
        FULL = "full", "تکمیل ظرفیت"

    class StartStatus(models.TextChoices):
        """Derived enum for course start status."""
        CONFIRMED = "confirmed", "قطعی"
        PENDING_CAPACITY = "pending_capacity", "منوط به تکمیل ظرفیت"
        UNDECIDED = "undecided", "نامشخص"

    department = models.ForeignKey(
        Department,
        on_delete=models.CASCADE,
        related_name="courses",
        verbose_name="دپارتمان"
    )
    name = models.CharField(max_length=500, verbose_name="نام دوره")
    instructor = models.CharField(max_length=255, blank=True, verbose_name="مدرس")
    schedule = models.CharField(max_length=500, blank=True, verbose_name="زمان برگزاری")
    start_date = models.CharField(max_length=100, blank=True, verbose_name="تاریخ شروع (متن خام)")
    start_date_parsed = models.DateField(null=True, blank=True, verbose_name="تاریخ شروع (پارس شده)")
    start_note = models.CharField(max_length=255, blank=True, verbose_name="توضیحات شروع")
    duration_hours = models.PositiveIntegerField(default=0, verbose_name="مدت دوره (ساعت)")
    capacity_remaining = models.PositiveIntegerField(default=0, verbose_name="ظرفیت باقی‌مانده")
    original_price = models.DecimalField(max_digits=10, decimal_places=0, null=True, blank=True, verbose_name="قیمت اصلی")
    final_price = models.DecimalField(max_digits=10, decimal_places=0, null=True, blank=True, verbose_name="قیمت نهایی")
    discount_description = models.CharField(max_length=500, blank=True, verbose_name="توضیحات تخفیف")
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.ENROLLING, verbose_name="وضعیت ثبت‌نام")
    sub_courses = models.JSONField(default=list, blank=True, verbose_name="زیردوره‌ها")
    url = models.URLField(unique=True, verbose_name="لینک دوره")
    start_status = models.CharField(
        max_length=20,
        choices=StartStatus.choices,
        default=StartStatus.UNDECIDED,
        verbose_name="وضعیت شروع"
    )

    class Meta:
        """Meta configuration for Course."""
        verbose_name = "دوره"
        verbose_name_plural = "دوره‌ها"

    def __str__(self) -> str:
        """Return string representation of the course."""
        return self.name


class CourseDetail(models.Model):
    """Stores the raw, unstructured description text for a course."""

    course = models.OneToOneField(
        Course,
        on_delete=models.CASCADE,
        related_name="details",
        verbose_name="دوره"
    )
    description = models.TextField(verbose_name="توضیحات")

    class Meta:
        """Meta configuration for CourseDetail."""
        verbose_name = "جزئیات دوره"
        verbose_name_plural = "جزئیات دوره‌ها"

    def __str__(self) -> str:
        """Return string representation of the course detail."""
        return self.course.name