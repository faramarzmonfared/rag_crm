from typing import List, Optional
from pydantic import BaseModel
from apps.chatbot.models import Intent


class QueryUnderstandingOutput(BaseModel):
    """Data contract for the Query Understanding pipeline stage."""
    intent: Intent  
    clean_query: str
    entities: List[str] = []
    direct_response: Optional[str] = None
    end_conversation: bool = False