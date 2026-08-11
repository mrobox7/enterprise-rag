"""Import this before anything imports `ragas`.

Two compatibility shims, both needed only because ragas 0.3.x predates
Python 3.14 and this project's already-pinned langchain-community:

1. ragas unconditionally does `from langchain_community.chat_models.vertexai
   import ChatVertexAI` at module load time, but that class was deleted from
   langchain-community in the version this project pins (>=0.4.2). We never
   use VertexAI (Groq is our LLM), so the symbol just needs to exist.

2. `ragas.executor` calls `nest_asyncio.apply()` at import time to support
   nested event loops (e.g. notebooks). nest_asyncio's monkeypatched Task
   isn't compatible with Python 3.14's asyncio internals and breaks
   `asyncio.wait_for` with `RuntimeError: Timeout should be used inside a
   task`. We always run this as a plain top-level script, never inside an
   already-running loop, so nested-loop support is never needed — no-op it.
"""

import sys
import types

if "langchain_community.chat_models.vertexai" not in sys.modules:
    _vertexai_stub = types.ModuleType("langchain_community.chat_models.vertexai")

    class ChatVertexAI:  # noqa: D101
        pass

    _vertexai_stub.ChatVertexAI = ChatVertexAI  # pyright: ignore[reportAttributeAccessIssue]
    sys.modules["langchain_community.chat_models.vertexai"] = _vertexai_stub

if "nest_asyncio" not in sys.modules:
    _nest_asyncio_stub = types.ModuleType("nest_asyncio")
    _nest_asyncio_stub.apply = lambda *args, **kwargs: None  # pyright: ignore[reportAttributeAccessIssue]
    sys.modules["nest_asyncio"] = _nest_asyncio_stub
