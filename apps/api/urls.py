from django.urls import path
from apps.api.views import LeadRegisterView, ChatHistoryView, ChatMessageView

app_name = "api"

urlpatterns = [
    path("leads/register", LeadRegisterView.as_view(), name="lead-register"),
    path("chat/history", ChatHistoryView.as_view(), name="chat-history"),
    path("chat/message", ChatMessageView.as_view(), name="chat-message"),
]   