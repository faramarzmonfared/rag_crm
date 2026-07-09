import os
from langchain_core.embeddings import Embeddings
from langchain_openai import OpenAIEmbeddings
from pydantic import SecretStr


def get_embedding_model() -> Embeddings:
    """
    Factory function to load the embedding model using OpenAI-compatible standard.
    """
    return OpenAIEmbeddings(
        model=os.environ.get("EMBEDDING_MODEL_NAME", "bge-m3"),
        api_key=SecretStr(os.environ.get("EMBEDDING_API_KEY", "dummy-key")),
        base_url=os.environ.get("EMBEDDING_BASE_URL", "http://localhost:11434/v1"),
        model_kwargs={"encoding_format": "float"},
        check_embedding_ctx_length=False,
    )