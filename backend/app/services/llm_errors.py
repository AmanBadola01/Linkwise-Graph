"""Maps LLM provider failures to a friendly, retryable error.

Provider exceptions carry raw JSON payloads (quota, model internals) that
must never reach API clients. Synthesizers raise SynthesisUnavailableError;
the query endpoint maps it to HTTP 503 with a plain message.
"""


class SynthesisUnavailableError(RuntimeError):
    """The answer-synthesis model is temporarily unavailable."""

    friendly_message = (
        "The AI model is temporarily unavailable. Please try again in a moment."
    )
