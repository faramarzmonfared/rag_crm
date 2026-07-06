import logging
import time
import uuid
from typing import Any

from langchain_core.output_parsers import JsonOutputParser
from langchain_core.prompts import ChatPromptTemplate

from apps.chatbot.models import BotPersona, PipelineLog, PromptTemplate, Intent
from apps.chatbot.schemas import QueryUnderstandingOutput
from apps.leads.models import Message
from config.llm_config import get_llm

logger = logging.getLogger(__name__)


def get_recent_messages_context(conversation_id: int, limit: int = 5) -> str:
    """
    Fetch recent messages from the active conversation to provide context.
    """
    messages = Message.objects.filter(conversation_id=conversation_id).order_by("-timestamp")[:limit]
    # Reverse to chronological order
    messages = reversed(messages)
    
    context_lines = []
    for msg in messages:
        sender = "کاربر" if msg.sender == Message.Sender.USER else "بات"
        context_lines.append(f"{sender}: {msg.content}")
        
    return "\n".join(context_lines)


def run_query_understanding(message: Message, trace_id: uuid.UUID) -> dict[str, Any]:
    """
    Execute the Query Understanding stage of the pipeline.
    
    Args:
        message: The user's Message object.
        trace_id: The unique ID tracking this pipeline execution.
        
    Returns:
        A dictionary containing the LLM's structured output (intent, clean_query, entities).
    """
    start_time = time.time()
    stage = PipelineLog.Stage.QUERY_UNDERSTANDING
    
    try:
        persona = BotPersona.objects.filter(is_active=True).first()
        if not persona:
            raise ValueError("No active BotPersona found.")
            
        prompt_template = PromptTemplate.objects.filter(
            persona=persona,
            stage=PromptTemplate.Stage.QUERY_UNDERSTANDING
        ).first()
        
        if not prompt_template:
            raise ValueError("No QUERY_UNDERSTANDING PromptTemplate found.")

        llm = get_llm("query_understanding")
        parser = JsonOutputParser(pydantic_object=QueryUnderstandingOutput)
        
        context = get_recent_messages_context(message.conversation_id)  # type: ignore[attr-defined]
        
        prompt = ChatPromptTemplate.from_messages([
            ("system", prompt_template.system_prompt),
            ("human", prompt_template.human_prompt)
        ])
        
        chain = prompt | llm | parser
        
        valid_intents = ", ".join([intent.value for intent in Intent])
        short_circuit_intents = "small_talk, unclear_needs_clarification, out_of_scope"
        
        output = chain.invoke({
            "identity_description": persona.identity_description,
            "tone_of_voice": persona.tone_of_voice,
            "context": context,
            "user_message": message.content,
            "valid_intents": valid_intents,  
            "short_circuit_intents": short_circuit_intents, 
            "format_instructions": parser.get_format_instructions()
        })
        
        latency_ms = int((time.time() - start_time) * 1000)
        
        # Extract intent safely for logging
        raw_intent = output.get("intent")
        intent_value = raw_intent.value if isinstance(raw_intent, Intent) else raw_intent

        if output.get("direct_response"):
            # Log that we short-circuited the pipeline
            PipelineLog.objects.create(
                message=message,
                trace_id=trace_id,
                stage=stage,
                intent=intent_value,
                outcome=PipelineLog.Outcome.SUCCESS,
                model_name=llm.model,  # type: ignore[attr-defined]
                latency_ms=int((time.time() - start_time) * 1000),
                input_data={"user_message": message.content, "context": context},
                output_data=output,
            )
            return output
        else:
            # Log successful execution
            PipelineLog.objects.create(
                message=message,
                trace_id=trace_id,
                stage=stage,
                intent=intent_value,
                outcome=PipelineLog.Outcome.SUCCESS,
                model_name=llm.model,  # type: ignore[attr-defined]
                latency_ms=latency_ms,
                input_data={"user_message": message.content, "context": context},
                output_data=output,
            )
        
            return output

    except Exception as e:
        logger.error("Query Understanding failed: %s", e)
        latency_ms = int((time.time() - start_time) * 1000)
        
        # Log failure
        PipelineLog.objects.create(
            message=message,
            trace_id=trace_id,
            stage=stage,
            outcome=PipelineLog.Outcome.FAILED_HARD,
            latency_ms=latency_ms,
            error_message=str(e),
            input_data={"user_message": message.content},
        )
        
        # Fallback: assume it's a generic course query if LLM fails
        return {
            "intent": "UNCLEAR_UNANSWERABLE",
            "clean_query": message.content,
            "entities": []
        }