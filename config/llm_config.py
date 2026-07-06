import os
from functools import lru_cache

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_openai import ChatOpenAI
from pydantic import SecretStr


@lru_cache(maxsize=1)
def get_llm(model_purpose: str) -> BaseChatModel:
    """
    Factory function to load LLM instances using OpenAI-compatible standard.
    
    Supports any provider that exposes an OpenAI-compatible API 
    (OpenAI, Ollama /v1, Groq, Together AI, vLLM, etc.).
    
    Args:
        model_purpose: Either 'query_understanding' or 'response'.
        
    Returns:
        A LangChain BaseChatModel instance.
    """
    if model_purpose == "query_understanding":
        model_name = os.environ["QUERY_UNDERSTANDING_LLM_MODEL"]
    elif model_purpose == "response":
        model_name = os.environ["RESPONSE_LLM_MODEL"]
    else:
        raise ValueError("Invalid model_purpose. Must be 'query_understanding' or 'response'.")

    return ChatOpenAI(
        model=model_name,
        api_key=SecretStr(os.environ.get("LLM_API_KEY", "dummy-key")),
        base_url=os.environ.get("LLM_BASE_URL", "http://localhost:11434/v1"),
        temperature=0.3,
    )