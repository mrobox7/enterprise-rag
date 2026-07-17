import logfire


def configure_logging() -> None:
    _ = logfire.configure(service_name="enterprise-rag")
    logfire.instrument_pydantic(include=("app.*",))
