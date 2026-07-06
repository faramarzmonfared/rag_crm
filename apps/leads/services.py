from datetime import datetime
from typing import Tuple
from apps.leads.models import Conversation, Lead


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