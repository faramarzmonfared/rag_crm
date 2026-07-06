import logging
from datetime import datetime
from apps.leads.models import Lead

logger = logging.getLogger(__name__)

def generate_welcome_message(
    lead: Lead, 
    is_new: bool, 
    last_conversation_at: datetime | None
) -> str:
    """
    Generate a personalized welcome message using a lightweight LLM call.
    Uses hardcoded fallbacks if the LLM call fails.
    
    Args:
        lead: The Lead object.
        is_new: True if the lead is completely new.
        last_conversation_at: Timestamp of the last conversation, if returning.
    """
    # TODO: Replace with actual LangChain/LLM call later
    try:
        if is_new:
            fallback_msg = f"سلام {lead.first_name} عزیز! به آموزشگاه ما خوش آمدید. چطور می‌توانم کمکتان کنم؟"
        elif last_conversation_at:
            # In the future, LLM will use this to say "دیروز رفتی" or "مدتی نبودید"
            fallback_msg = f"سلام {lead.first_name} عزیز! خوش برگشتید. چطور می‌توانم کمکتان کنم؟"
        else:
            # Fallback for edge cases (should not normally hit this if logic is correct)
            fallback_msg = f"سلام {lead.first_name} عزیز!"
            
        return fallback_msg
    except Exception as e:
        logger.error("Failed to generate welcome message via LLM: %s", e)
        return f"سلام! به آموزشگاه ما خوش آمدید."