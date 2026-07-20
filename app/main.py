from app.config.logging import configure_logging

configure_logging()

from typing import cast

import logfire
from fastapi import FastAPI
from fastapi.responses import JSONResponse, Response

from app.agents.graph import rag_agent
from app.agents.state import AgentState, Message
from app.config.settings import settings
from app.models.query import QueryRequest, QueryResponse

app = FastAPI(title=settings.app_name)


@app.get("/")
def home() -> dict[str, str]:
    return {"message": f"{settings.app_name} is live."}


@app.get("/graph")
def get_graph_image() -> Response:
    """Returns the Mermaid PNG of the agent's LangGraph workflow."""
    try:
        png_bytes = rag_agent.get_graph().draw_mermaid_png()
        return Response(content=png_bytes, media_type="image/png")
    except Exception as e:
        logfire.error(f"❌ Could not generate graph image: {e}")
        return JSONResponse(content={"error": str(e)}, status_code=500)


@app.post("/query")
def query(request: QueryRequest) -> QueryResponse:
    """
    Executes the LangGraph RAG flow via a POST request.
    No conversation memory yet — every call starts from a blank slate.
    """
    initial_state = AgentState(
        messages=[Message(role="user", content=request.q)],
        current_query=request.q,
        documents=[],
        plan=["Start"],
        status="Initializing Graph...",
    )

    with logfire.span("🚀 Query received", question=request.q):
        try:
            raw_output = cast(
                dict[str, object],
                rag_agent.invoke(initial_state),  # pyright: ignore[reportUnknownMemberType]
            )

            return QueryResponse.model_validate(
                {
                    "question": request.q,
                    "answer": raw_output.get("final_answer"),
                    "thought_process": raw_output.get("plan"),
                    "status": raw_output.get("status"),
                    "sources": raw_output.get("documents"),
                }
            )

        except Exception as e:
            logfire.error(f"❌ Backend execution failed: {e}")
            return QueryResponse(
                question=request.q,
                answer=(
                    "I apologize, but I encountered an internal error while "
                    "processing your request. Please try again later."
                ),
                thought_process=["Error encountered during execution."],
                status="error",
                sources=[],
            )
