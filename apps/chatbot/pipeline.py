import logging
import time
import uuid
from typing import Any

from langchain_core.output_parsers import JsonOutputParser, StrOutputParser
from langchain_core.prompts import ChatPromptTemplate

from apps.chatbot.models import BotPersona, PipelineLog, PromptTemplate, Intent, ContactInfo
from apps.chatbot.schemas import QueryUnderstandingOutput
from apps.leads.models import Message
from config.llm_config import get_llm

from pgvector.django import CosineDistance
from config.embedding_config import get_embedding_model
from apps.knowledgebase.models import Chunk, KnowledgeBaseSource

import os
from apps.leads.models import Lead
from apps.chatbot.sms import send_sms
from apps.chatbot.services import is_within_working_hours
from django.utils import timezone

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

        is_working_hours = is_within_working_hours()
        working_hours_context = (
            "در حال حاضر در ساعات کاری آموزشگاه هستیم و پشتیبانان آنلاین هستند."
            if is_working_hours else
            "در حال حاضر خارج از ساعات کاری آموزشگاه هستیم و پشتیبانان آفلاین هستند."
        )
        
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
            "working_hours_context": working_hours_context,
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


def run_routing_and_retrieval(message: Message, trace_id: uuid.UUID, query_output: dict[str, Any]) -> list[dict[str, Any]]:
    """
    Execute Routing and Retrieval stage based on the identified intent.
    
    Args:
        message: The user's Message object.
        trace_id: The unique ID tracking this pipeline execution.
        query_output: The output dictionary from run_query_understanding.
        
    Returns:
        A list of retrieved chunks (dictionaries with content and metadata).
    """
    start_time = time.time()
    stage = PipelineLog.Stage.RETRIEVAL
    intent = query_output.get("intent")
    clean_query = query_output.get("clean_query", "")
    
    retrieved_chunks = []
    
    try:
        if intent in [Intent.COURSE_SPECIFIC, Intent.INSTITUTION_FAQ]:
            embedding_model = get_embedding_model()
            query_vector = embedding_model.embed_query(clean_query)
            
            # Vector Search in pgvector
            chunks_qs = Chunk.objects.filter(
                source_type=(
                    KnowledgeBaseSource.COURSE if intent == Intent.COURSE_SPECIFIC 
                    else KnowledgeBaseSource.INSTITUTION_FAQ
                ),
                embedding__isnull=False
            ).annotate(
                distance=CosineDistance("embedding", query_vector)
            ).order_by("distance")[:3]  # Top 3 results
            
            retrieved_chunks = [
                {
                    "content": chunk.content,
                    "metadata": chunk.metadata,
                    "score": 1 - chunk.distance  # type: ignore[attr-defined], Convert distance to similarity score
                }
                for chunk in chunks_qs
            ]
            
        latency_ms = int((time.time() - start_time) * 1000)
        
        # Log successful execution
        PipelineLog.objects.create(
            message=message,
            trace_id=trace_id,
            stage=stage,
            intent=intent,
            outcome=PipelineLog.Outcome.SUCCESS,
            latency_ms=latency_ms,
            input_data={"intent": intent, "clean_query": clean_query},
            output_data={"retrieved_count": len(retrieved_chunks)},
            retrieved_chunk_ids=[c["metadata"].get("id") for c in retrieved_chunks if c["metadata"].get("id")],
            similarity_scores=[c["score"] for c in retrieved_chunks],
            decision_reason=f"Routed to vector search for intent: {intent}"
        )
        
        return retrieved_chunks

    except Exception as e:
        logger.error("Routing/Retrieval failed: %s", e)
        latency_ms = int((time.time() - start_time) * 1000)
        
        PipelineLog.objects.create(
            message=message,
            trace_id=trace_id,
            stage=stage,
            intent=intent,
            outcome=PipelineLog.Outcome.FAILED_HARD,
            latency_ms=latency_ms,
            error_message=str(e),
            input_data={"intent": intent, "clean_query": clean_query},
        )
        return []


def run_response_generation(
    message: Message, 
    trace_id: uuid.UUID, 
    query_output: dict[str, Any], 
    retrieved_chunks: list[dict[str, Any]]
) -> str:
    """
    Execute the Response Generation stage using retrieved context.
    
    Args:
        message: The user's Message object.
        trace_id: The unique ID tracking this pipeline execution.
        query_output: The output dictionary from run_query_understanding.
        retrieved_chunks: The list of chunks retrieved from the vector database.
        
    Returns:
        The generated bot response string.
    """
    start_time = time.time()
    stage = PipelineLog.Stage.RESPONSE_GENERATION
    clean_query = query_output.get("clean_query", "")
    
    try:
        persona = BotPersona.objects.filter(is_active=True).first()
        if not persona:
            raise ValueError("No active BotPersona found.")
            
        prompt_template = PromptTemplate.objects.filter(
            persona=persona,
            stage=PromptTemplate.Stage.RESPONSE_GENERATION
        ).first()
        
        if not prompt_template:
            raise ValueError("No RESPONSE_GENERATION PromptTemplate found.")

        llm = get_llm("response")
        
        # Format chunks into a single context string
        context_str = "\n\n".join([chunk["content"] for chunk in retrieved_chunks])
        
        prompt = ChatPromptTemplate.from_messages([
            ("system", prompt_template.system_prompt),
            ("human", prompt_template.human_prompt)
        ])
        
        chain = prompt | llm | StrOutputParser()
        
        response_text = chain.invoke({
            "identity_description": persona.identity_description,
            "tone_of_voice": persona.tone_of_voice,
            "context": context_str,
            "user_message": clean_query
        })
        
        latency_ms = int((time.time() - start_time) * 1000)
        
        # Log successful execution
        PipelineLog.objects.create(
            message=message,
            trace_id=trace_id,
            stage=stage,
            outcome=PipelineLog.Outcome.SUCCESS,
            model_name=llm.model,  # type: ignore[attr-defined]
            latency_ms=latency_ms,
            input_data={"user_message": clean_query, "context_length": len(context_str)},
            output_data={"response": response_text[:200]} # Log first 200 chars
        )
        
        return response_text.strip()

    except Exception as e:
        logger.error("Response Generation failed: %s", e)
        latency_ms = int((time.time() - start_time) * 1000)
        
        PipelineLog.objects.create(
            message=message,
            trace_id=trace_id,
            stage=stage,
            outcome=PipelineLog.Outcome.FAILED_HARD,
            latency_ms=latency_ms,
            error_message=str(e),
            input_data={"user_message": clean_query},
        )
        
        return "An error occurred while processing the response. Please try again later."


def trigger_human_handoff(message: Message, trace_id: uuid.UUID, reason: str = "unanswerable") -> None:
    """
    Trigger the Human Handoff backend process.
    Updates Lead status, checks working hours for SMS scheduling, and sends SMS.
    
    Args:
        message: The user's Message object.
        trace_id: The unique ID tracking this pipeline execution.
        reason: The reason for handoff.
    """
    start_time = time.time()
    stage = PipelineLog.Stage.HANDOFF
    
    try:
        lead = message.conversation.lead
        
        # 1. Update Lead Status
        lead.status = Lead.Status.NEEDS_FOLLOWUP
        lead.save()
        
        # 2. Check Working Hours for SMS Scheduling
        is_working_hours = is_within_working_hours()
        sms_schedule = None if is_working_hours else "next_working_day_morning"
        
        # 3. Send SMS to Support Team (Stub)
        support_contacts = ContactInfo.objects.filter(is_support_number=True)
        if not support_contacts.exists():
            logger.warning("No support numbers configured in ContactInfo.")
        else:
            sms_text = f"New Lead Followup Required!\nLead: {lead.first_name} {lead.last_name}\nPhone: {lead.phone_number}\nReason: {reason}\nQuestion: {message.content[:50]}"

            for contact in support_contacts:
                send_sms(contact.value, sms_text, sms_schedule)
        
        latency_ms = int((time.time() - start_time) * 1000)
        # Log successful execution
        PipelineLog.objects.create(
            message=message,
            trace_id=trace_id,
            stage=stage,
            intent=reason,
            outcome=PipelineLog.Outcome.SUCCESS,
            latency_ms=latency_ms,
            input_data={"user_message": message.content, "is_working_hours": is_working_hours},
            output_data={"sms_sent": True, "sms_schedule": sms_schedule},
            decision_reason=f"Handoff triggered due to: {reason}"
        )

    except Exception as e:
        logger.error("Human Handoff failed: %s", e)
        latency_ms = int((time.time() - start_time) * 1000)
        
        PipelineLog.objects.create(
            message=message,
            trace_id=trace_id,
            stage=stage,
            outcome=PipelineLog.Outcome.FAILED_HARD,
            latency_ms=latency_ms,
            error_message=str(e),
            input_data={"user_message": message.content},
        )
