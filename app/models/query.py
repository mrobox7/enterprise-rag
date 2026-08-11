from pydantic import BaseModel, Field

from app.agents.state import Message


class QueryRequest(BaseModel):
    q: str
    messages: list[Message] = Field(default_factory=list)
    """Prior conversation turns, oldest first, NOT including `q` itself."""


class QueryResponse(BaseModel):
    question: str
    answer: str
    thought_process: list[str]
    status: str
    sources: list[str]
