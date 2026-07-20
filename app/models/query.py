from pydantic import BaseModel


class QueryRequest(BaseModel):
    q: str


class QueryResponse(BaseModel):
    question: str
    answer: str
    thought_process: list[str]
    status: str
    sources: list[str]
