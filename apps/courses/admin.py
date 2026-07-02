from django.contrib import admin

from apps.courses.models import Course, CourseDetail, Department


@admin.register(Department)
class DepartmentAdmin(admin.ModelAdmin):
    """Admin configuration for Department model."""
    list_display = ("id", "name", "url")
    search_fields = ("name",)


@admin.register(Course)
class CourseAdmin(admin.ModelAdmin):
    """Admin configuration for Course model."""
    list_display = ("id", "name", "department", "instructor", "status", "start_status", "start_date_parsed")
    list_filter = ("department", "status", "start_status")
    search_fields = ("name", "instructor")


@admin.register(CourseDetail)
class CourseDetailAdmin(admin.ModelAdmin):
    """Admin configuration for CourseDetail model."""
    list_display = ("id", "course")
    search_fields = ("course__name",)