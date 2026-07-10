import logging
from datetime import datetime
from typing import Optional

from django.utils import timezone
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate

from apps.chatbot.models import BotPersona, PromptTemplate, WorkingDay
from apps.leads.models import Lead
from config.llm_config import get_llm

logger = logging.getLogger(__name__)


def generate_welcome_message(
    lead: Lead, 
    is_new: bool, 
    last_conversation_at: Optional[datetime]
) -> str:
    """
    Generate a personalized welcome message using an LLM and DB-driven prompts.
    Uses hardcoded fallbacks if DB records or LLM call fail.
    """
    # Hardcoded fallbacks
    if is_new:
        fallback_msg = f"سلام {lead.first_name} عزیز! به آموزشگاه ما خوش آمدید."
    elif last_conversation_at:
        fallback_msg = f"سلام {lead.first_name} عزیز! خوش برگشتید."
    else:
        fallback_msg = f"سلام {lead.first_name} عزیز!"

    try:
        # Fetch active persona and prompt template from DB
        persona = BotPersona.objects.filter(is_active=True).first()
        if not persona:
            logger.warning("No active BotPersona found. Using fallback message.")
            return fallback_msg

        prompt_template = PromptTemplate.objects.filter(
            persona=persona, 
            stage=PromptTemplate.Stage.WELCOME_MESSAGE
        ).first()
        
        if not prompt_template:
            logger.warning("No WELCOME_MESSAGE PromptTemplate found. Using fallback message.")
            return fallback_msg

        llm = get_llm("response")
        
        # Build context string
        if is_new:
            context = "این کاربر کاملاً جدید است و برای اولین بار با ما چت می‌کند."
        elif last_conversation_at:
            now = timezone.now()
            days_ago = (now - last_conversation_at).days
            if days_ago == 0:
                context = "این کاربر امروز قبلاً با ما چت کرده است."
            else:
                context = f"این کاربر قبلاً با ما چت کرده است. آخرین مکالمه حدود {days_ago} روز پیش بوده است."
        else:
            context = "این کاربر قبلاً با ما چت کرده است."

        prompt = ChatPromptTemplate.from_messages([
            ("system", prompt_template.system_prompt),
            ("human", prompt_template.human_prompt),
        ])

        chain = prompt | llm | StrOutputParser()
        
        welcome_text = chain.invoke({
            "identity_description": persona.identity_description,
            "tone_of_voice": persona.tone_of_voice,
            "first_name": lead.first_name,
            "context": context
        })
        
        return welcome_text.strip()

    except Exception as e:
        logger.error("Failed to generate welcome message via LLM: %s", e)
        return fallback_msg


def is_within_working_hours() -> bool:
    """
    Check if the current time falls within any defined working shift.
    """
    now = timezone.now()
    current_day = now.weekday()  # Monday is 0 and Sunday is 6 (direct match)
    current_time = now.time()

    try:
        working_day = WorkingDay.objects.get(day=current_day)
        for shift in working_day.shifts.all():
            if shift.start_time <= current_time <= shift.end_time:
                return True
    except WorkingDay.DoesNotExist:
        return False
        
    return False