from django.urls import path
from apps.api.views import LeadRegisterView

app_name = "api"

urlpatterns = [
    path("leads/register", LeadRegisterView.as_view(), name="lead-register"),
]   