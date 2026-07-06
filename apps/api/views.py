from typing import Any, cast
from rest_framework import status
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.api.serializers import LeadRegistrationSerializer
from apps.chatbot.services import generate_welcome_message
from apps.leads.models import Message
from apps.leads.services import get_or_create_lead_and_conversation


class LeadRegisterView(APIView):
    """API view to register or retrieve a Lead and its active Conversation."""

    def post(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        """Handle POST request to upsert lead and return tokens."""
        serializer = LeadRegistrationSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        validated_data = cast(dict[str, Any], serializer.validated_data)
        
        lead, conversation, lead_created, conversation_created, last_conv_at = (
            get_or_create_lead_and_conversation(
                first_name=validated_data["first_name"],
                last_name=validated_data["last_name"],
                phone_number=validated_data["phone_number"]
            )
        )
        
        welcome_text = None
        
        # Only generate welcome message if it's a NEW conversation (not a page refresh)
        if conversation_created:
            welcome_text = generate_welcome_message(
                lead=lead,
                is_new=lead_created,
                last_conversation_at=last_conv_at
            )
            
            # Save the welcome message as a BOT message
            Message.objects.create(
                conversation=conversation,
                sender=Message.Sender.BOT,
                content=welcome_text
            )
        
        response_status = status.HTTP_201_CREATED if lead_created else status.HTTP_200_OK
        
        return Response(
            {
                "lead_token": str(lead.token),
                "conversation_id": conversation.id,  # type: ignore[attr-defined]
                "welcome_message": welcome_text  # Will be null if it was a refresh
            },
            status=response_status
        )