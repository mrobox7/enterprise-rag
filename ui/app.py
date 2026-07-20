import sys
from pathlib import Path

import requests
import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.config.settings import settings
from app.models.query import QueryResponse

st.set_page_config(page_title=settings.app_name, page_icon="🤖")
st.title(settings.app_name)

if "messages" not in st.session_state:
    st.session_state.messages = []

for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])
        for source in message.get("sources", []):
            st.caption(f"📚 {source}")

query = st.chat_input("Ask a question...")

if query:
    st.session_state.messages.append({"role": "user", "content": query})
    with st.chat_message("user"):
        st.markdown(query)

    with st.chat_message("assistant"):
        try:
            with st.spinner("Thinking..."):
                http_response = requests.post(
                    f"{settings.backend_url}/query",
                    json={"q": query},
                    timeout=60,
                )
                http_response.raise_for_status()
                result = QueryResponse.model_validate(http_response.json())
        except requests.RequestException as e:
            st.error(f"Could not reach the backend at {settings.backend_url}: {e}")
            st.stop()

        st.markdown(result.answer)

        if result.thought_process:
            with st.expander("🧠 Thought process"):
                for step in result.thought_process:
                    st.markdown(f"- {step}")

        for source in result.sources:
            st.caption(f"📚 {source}")

    st.session_state.messages.append(
        {
            "role": "assistant",
            "content": result.answer,
            "sources": result.sources,
        }
    )
