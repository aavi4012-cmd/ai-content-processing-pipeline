import time
import json
import logging
from typing import Dict
from openai import OpenAI, APITimeoutError, RateLimitError
from app.config import settings
from app.schemas.submission_schema import LLMOutput

logger = logging.getLogger(__name__)

# System prompt kept separate for maintainability and prompt versioning
SYSTEM_PROMPT = "You are a helpful analyst. Always respond with valid JSON only. No markdown, no code fences."

USER_PROMPT_TEMPLATE = """Analyze the following text and return a JSON object with exactly these keys:
{{
    "sentiment": one of "positive", "negative", or "neutral",
    "topic": the primary subject of the text,
    "summary": a concise one-sentence summary
}}

Text to analyze:
\"\"\"
{text}
\"\"\"
"""


class LLMService:
    """
    Encapsulates all LLM provider logic. If no API key is configured,
    falls back to a deterministic mock response for testing.
    """

    def __init__(self):
        if settings.OPENAI_API_KEY:
            self.client = OpenAI(
                api_key=settings.OPENAI_API_KEY,
                timeout=settings.LLM_TIMEOUT,
            )
        else:
            self.client = None

    def process_content(self, text: str) -> Dict:
        """
        Sends text to the LLM, validates the response through Pydantic,
        and returns a structured dictionary.

        Raises on failure to allow the Celery retry mechanism to handle it.
        """
        start_time = time.time()

        if not self.client:
            return self._mock_response(text)

        try:
            response = self.client.chat.completions.create(
                model=settings.LLM_MODEL,
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": USER_PROMPT_TEMPLATE.format(text=text)},
                ],
                response_format={"type": "json_object"},
                temperature=0.2,  # Lower temperature for more deterministic structured output
            )

            latency = time.time() - start_time
            raw_content = response.choices[0].message.content
            parsed_content = json.loads(raw_content)

            # Pydantic validation — rejects hallucinated schemas
            validated = LLMOutput(**parsed_content)

            result = validated.model_dump()
            result["latency"] = f"{latency:.3f}s"
            logger.info(f"LLM call succeeded in {latency:.3f}s")
            return result

        except (APITimeoutError, RateLimitError) as e:
            logger.warning(f"LLM transient error (will retry): {type(e).__name__}: {e}")
            raise  # Celery autoretry handles this

        except json.JSONDecodeError as e:
            logger.error(f"LLM returned non-JSON response: {e}")
            raise  # Triggers retry — LLMs are probabilistic

        except Exception as e:
            logger.error(f"LLM processing failed: {type(e).__name__}: {e}")
            raise  # Propagate for worker retry

    def _mock_response(self, text: str) -> Dict:
        """Deterministic mock for local development without an API key."""
        logger.warning("OPENAI_API_KEY not set — returning mock LLM response.")
        time.sleep(0.5)  # Simulate network latency
        return {
            "sentiment": "neutral",
            "topic": "Simulated Analysis",
            "summary": f"Mock summary of: {text[:50]}...",
            "latency": "0.500s",
        }