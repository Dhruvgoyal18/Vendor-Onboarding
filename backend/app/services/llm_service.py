import base64
import json
import logging
from typing import Optional, Union

from anthropic import Anthropic
from groq import Groq

from app.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

# Initialize clients if keys are present
anthropic_client = Anthropic(api_key=settings.anthropic_api_key) if settings.anthropic_api_key else None
groq_client = Groq(api_key=settings.groq_api_key) if settings.groq_api_key else None

def _safe_json_parse(text: str) -> dict | list:
    """Safely parse JSON from LLM response, handling markdown code blocks."""
    text = text.strip()
    if text.startswith("```"):
        lines = text.split("\n")
        # Find the first line that is a code block marker and remove it, and same for the end
        if lines[0].startswith("```"):
            lines = lines[1:]
        if lines[-1].startswith("```"):
            lines = lines[:-1]
        text = "\n".join(lines).strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse JSON: {e}\nText: {text[:500]}")
        return {}


def call_anthropic(system: str, user_message: str, max_tokens: int = 2000) -> str:
    if not anthropic_client:
        raise ValueError("Anthropic API key is not configured.")
    resp = anthropic_client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=max_tokens,
        system=system,
        messages=[{"role": "user", "content": user_message}],
    )
    return resp.content[0].text


def call_groq(system: str, user_message: str, max_tokens: int = 2000) -> str:
    if not groq_client:
        raise ValueError("Groq API key is not configured.")
    
    # Groq handles system prompts via messages array
    messages = [
        {"role": "system", "content": system},
        {"role": "user", "content": user_message}
    ]
    
    resp = groq_client.chat.completions.create(
        model="llama-3.3-70b-versatile",  # Best for complex extraction and reasoning
        messages=messages,
        max_tokens=max_tokens,
        temperature=0.1,  # Keep deterministic for JSON
    )
    return resp.choices[0].message.content or ""


def call_llm(system: str, user_message: str, max_tokens: int = 2000) -> str:
    """Generic LLM call returning raw text, toggling based on provider."""
    provider = settings.llm_provider.lower()
    
    try:
        if provider == "groq":
            return call_groq(system, user_message, max_tokens)
        else:
            return call_anthropic(system, user_message, max_tokens)
    except Exception as e:
        logger.error(f"LLM call failed (Provider: {provider}): {e}")
        # Optional fallback could go here
        raise


def call_llm_json(system: str, user_message: str, max_tokens: int = 2000) -> dict | list:
    """Generic LLM call returning parsed JSON."""
    # Ensure the model knows we expect JSON output
    system_json_instruction = f"{system}\n\nIMPORTANT: You must return ONLY valid JSON without any markdown formatting or explanations."
    raw = call_llm(system_json_instruction, user_message, max_tokens)
    return _safe_json_parse(raw)


def call_groq_vision_json(
    system: str,
    user_message: str,
    images: list[bytes],
    max_tokens: int = 2000,
) -> dict | list:
    """
    Call Groq Llama 4 Scout vision with one or more JPEG image bytes + text prompt.
    Used as OCR fallback when Tesseract is unavailable (e.g. Vercel serverless).
    Images should be JPEG bytes rendered from the document (via pypdfium2 or PIL).
    """
    if not groq_client:
        raise ValueError("Groq API key is not configured — cannot use vision fallback.")

    image_blocks = [
        {
            "type": "image_url",
            "image_url": {"url": f"data:image/jpeg;base64,{base64.standard_b64encode(img).decode()}"},
        }
        for img in images
    ]

    system_with_json = (
        f"{system}\n\n"
        "IMPORTANT: You must return ONLY valid JSON without any markdown formatting or explanations."
    )

    resp = groq_client.chat.completions.create(
        model="meta-llama/llama-4-scout-17b-16e-instruct",
        messages=[
            {"role": "system", "content": system_with_json},
            {"role": "user", "content": [*image_blocks, {"type": "text", "text": user_message}]},
        ],
        max_tokens=max_tokens,
        temperature=0.1,
    )
    return _safe_json_parse(resp.choices[0].message.content or "")
