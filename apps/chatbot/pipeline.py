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

from pgvector.django import CosineDistance
from config.embedding_config import get_embedding_model
from apps.knowledgebase.models import Chunk, KnowledgeBaseSource

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