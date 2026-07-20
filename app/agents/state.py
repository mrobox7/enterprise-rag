# state.py
import operator
from typing import Annotated

from pydantic import BaseModel, Field


class Message(BaseModel):
    role: str
    content: str


class AgentState(BaseModel):
    messages: Annotated[list[Message], operator.add] = Field(default_factory=list)
    current_query: str
    documents: list[str] = Field(default_factory=list)
    plan: list[str] = Field(default_factory=list)
    status: str = "pending"
    final_answer: str = ""
