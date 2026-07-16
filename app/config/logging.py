import logfire

logger = logfire.configure(
    service_name="enterprise-rag",
)

logfire.instrument_pydantic()
