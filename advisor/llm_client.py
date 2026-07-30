"""Thin wrapper around the Gemini API (free tier): one function in, raw text out or a clear error."""

import os

from dotenv import load_dotenv

load_dotenv()

MODEL = "gemini-flash-latest"


class LLMClientError(Exception):
    """Raised when the Gemini API call fails or the API key is missing."""


def call_llm(system_prompt: str, user_prompt: str, timeout: float = 60.0, retries: int = 1) -> str:
    """Call Gemini with the given system/user prompts and return the raw text response.

    Retries once on a timeout (free-tier latency is occasionally slow) before giving
    up. Raises LLMClientError on missing API key or any API failure so callers can
    show a friendly fallback instead of crashing.
    """
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise LLMClientError("GEMINI_API_KEY is not set.")

    try:
        from google import genai
        from google.genai import types
    except ImportError as exc:
        raise LLMClientError("The 'google-genai' package is not installed.") from exc

    client = genai.Client(api_key=api_key)
    config = types.GenerateContentConfig(
        system_instruction=system_prompt,
        http_options=types.HttpOptions(timeout=int(timeout * 1000)),
    )

    last_error: Exception | None = None
    for attempt in range(retries + 1):
        try:
            response = client.models.generate_content(model=MODEL, contents=user_prompt, config=config)
            return response.text or ""
        except Exception as exc:  # the SDK raises several distinct exception types
            last_error = exc

    raise LLMClientError(f"Gemini API call failed after {retries + 1} attempt(s): {last_error}")
