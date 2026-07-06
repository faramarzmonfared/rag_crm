from datetime import datetime
from typing import Tuple
from apps.leads.models import Conversation, Lead
from datetime import timedelta
from django.utils import timezone


CONVERSATION_TIMEOUT_MINUTES = 30

def check_and_close_conversation_if_timeout(conversation: Conversation) -> Conversation:
    """
    Check if the conversation has timed out (30 mins of inactivity).
    If so, close it and create a new one.
    
    Args:
        conversation: The current active conversation.
        
    Returns:
        The active conversation (either the original or a new one).
    """
    if not conversation.is_active:
        return Conversation.objects.create(lead=conversation.lead)

    last_message = conversation.messages.order_by("-timestamp").first()     # type: ignore[attr-defined]
    if last_message:
        time_since_last_msg = timezone.now() - last_message.timestamp
        if time_since_last_msg > timedelta(minutes=CONVERSATION_TIMEOUT_MINUTES):
            # Timeout reached, close old conversation
            conversation.is_active = False
            conversation.ended_at = timezone.now()
            conversation.save()
            # Create and return new conversation
            return Conversation.objects.create(lead=conversation.lead)

    return conversation

def get_or_create_lead_and_conversation(
    first_name: str,
    last_name: str,
    phone_number: str
) -> Tuple[Lead, Conversation, bool, bool, datetime | None]:
    """
    Upsert a Lead and manage active/inactive conversations.
    
    Returns:
        A tuple containing:
        - lead: The Lead object.
        - conversation: The active or newly created Conversation.
        - lead_created: Boolean indicating if the lead was newly created.
        - conversation_created: Boolean indicating if a new conversation was started.
        - last_conversation_at: Timestamp of the last inactive conversation (if any).
    """
    lead, lead_created = Lead.objects.update_or_create(
        phone_number=phone_number,
        defaults={
            "first_name": first_name,
            "last_name": last_name,
        }
    )
    
    conversation = Conversation.objects.filter(lead=lead, is_active=True).first()
    conversation_created = False
    last_conversation_at = None
    
    if not conversation:
        # Fetch the end time of the previous conversation before creating a new one
        last_conversation_at = (
            Conversation.objects
            .filter(lead=lead, is_active=False)
            .order_by("-started_at")
            .values_list("started_at", flat=True)
            .first()
        )
        conversation = Conversation.objects.create(lead=lead)
        conversation_created = True
        
    return lead, conversation, lead_created, conversation_created, last_conversation_at