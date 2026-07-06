import uuid

from django.utils import timezone
from apps.api.serializers import LeadRegistrationSerializer, MessageSerializer
from apps.chatbot.pipeline import run_query_understanding

from typing import Any, cast
from rest_framework import status
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView
from django.shortcuts import get_object_or_404

from apps.api.serializers import LeadRegistrationSerializer, MessageSerializer
from apps.chatbot.services import generate_welcome_message
from apps.leads.models import Conversation, Lead, Message
from apps.leads.services import get_or_create_lead_and_conversation, check_and_close_conversation_if_timeout


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


class ChatHistoryView(APIView):
    """API view to retrieve the message history for a specific conversation."""

    def get(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        """Handle GET request to fetch chat history using headers."""
        lead_token = request.headers.get("Lead-Token")
        conversation_id = request.headers.get("Conversation-Id")

        if not lead_token or not conversation_id:
            return Response(
                {"detail": "Lead-Token and Conversation-Id headers are required."},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Validate access: ensure the conversation belongs to the lead
        lead = get_object_or_404(Lead, token=lead_token)
        conversation = get_object_or_404(
            Conversation, 
            id=conversation_id, 
            lead=lead
        )

        messages = conversation.messages.all().order_by("timestamp")    # type: ignore[attr-defined]
        serializer = MessageSerializer(messages, many=True)
        
        return Response(serializer.data, status=status.HTTP_200_OK)


class ChatMessageView(APIView):
    """API view to receive a user message, process it, and return the bot response."""

    def post(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        """Handle POST request to process a chat message."""
        lead_token = request.headers.get("Lead-Token")
        conversation_id = request.headers.get("Conversation-Id")

        if not lead_token or not conversation_id:
            return Response(
                {"detail": "Lead-Token and Conversation-Id headers are required."},
                status=status.HTTP_400_BAD_REQUEST
            )

        lead = get_object_or_404(Lead, token=lead_token)
        conversation = get_object_or_404(Conversation, id=conversation_id, lead=lead)

        # Lazy Check: Close if timeout, start a new one if needed
        conversation = check_and_close_conversation_if_timeout(conversation)
        new_conversation_started = str(conversation.id) != conversation_id

        # Cast request.data to dict to resolve Pylance 'Empty' type issue
        data = cast(dict[str, Any], request.data)
        user_text = data.get("message", "").strip()
        if not user_text:
            return Response({"detail": "Message cannot be empty."}, status=status.HTTP_400_BAD_REQUEST)
            
        user_message = Message.objects.create(
            conversation=conversation,
            sender=Message.Sender.USER,
            content=user_text
        )

        # Generate a unique trace_id for this pipeline execution
        trace_id = uuid.uuid4()

        # Stage 1: Query Understanding
        query_understanding_output = run_query_understanding(user_message, trace_id)

        # Short-circuit check: if LLM provided a direct response, skip the rest
        direct_response = query_understanding_output.get("direct_response")
        if direct_response:
            bot_response_text = direct_response
        else:
            # TODO: Stage 2 (Routing), Stage 3 (Retrieval), Stage 4 (Response Generation)
            bot_response_text = f"پاسخ تستی. نیت شناسایی شده: {query_understanding_output.get('intent')}"

        # Check if LLM decided to end the conversation (e.g., explicit goodbye)
        end_conversation = query_understanding_output.get("end_conversation", False)
        if end_conversation:
            conversation.is_active = False
            conversation.ended_at = timezone.now()
            conversation.save()

        # Save bot's response
        bot_message = Message.objects.create(
            conversation=conversation,
            sender=Message.Sender.BOT,
            content=bot_response_text
        )

        return Response(
            {
                "trace_id": str(trace_id),
                "bot_message": bot_message.content,
                "query_understanding": query_understanding_output,
                "new_conversation_id": str(conversation.id) if new_conversation_started else None,      # type: ignore[attr-defined]
                "conversation_ended": end_conversation
            },
            status=status.HTTP_200_OK
        )


class ChatEndView(APIView):
    """API view to explicitly end a conversation (e.g., on page close)."""

    def post(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        """Handle POST request to close an active conversation."""
        lead_token = request.headers.get("Lead-Token")
        conversation_id = request.headers.get("Conversation-Id")

        if not lead_token or not conversation_id:
            return Response(
                {"detail": "Lead-Token and Conversation-Id headers are required."},
                status=status.HTTP_400_BAD_REQUEST
            )

        lead = get_object_or_404(Lead, token=lead_token)
        conversation = get_object_or_404(Conversation, id=conversation_id, lead=lead)

        if conversation.is_active:
            conversation.is_active = False
            conversation.ended_at = timezone.now()
            conversation.save()
            
        return Response({"detail": "Conversation ended successfully."}, status=status.HTTP_200_OK)