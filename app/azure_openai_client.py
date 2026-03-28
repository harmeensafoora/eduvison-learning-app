"""
Azure OpenAI client configuration and utility functions
Handles authentication and low-level API interactions with Azure OpenAI service
"""

import logging
import os
from openai import AzureOpenAI
from tenacity import retry, stop_after_attempt, wait_exponential

logger = logging.getLogger(__name__)

# Initialize Azure OpenAI client
def init_azure_openai():
    """Initialize Azure OpenAI client from environment variables"""
    try:
        client = AzureOpenAI(
            api_key=os.getenv("AZURE_OPENAI_API_KEY"),
            api_version=os.getenv("AZURE_OPENAI_API_VERSION", "2024-02-15-preview"),
            azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT"),
        )
        logger.info("Azure OpenAI client initialized successfully")
        return client
    except Exception as e:
        logger.error(f"Failed to initialize Azure OpenAI client: {str(e)}")
        raise

# Global client instance
_azure_openai_client = None


def get_azure_openai_client():
    """Get or create Azure OpenAI client singleton"""
    global _azure_openai_client
    if _azure_openai_client is None:
        _azure_openai_client = init_azure_openai()
    return _azure_openai_client


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=10),
)
def call_azure_openai_completion(
    messages: list,
    model: str = None,
    temperature: float = 0.7,
    max_tokens: int = 2000,
    json_mode: bool = False,
) -> str:
    """
    Call Azure OpenAI API with exponential backoff retry logic

    Args:
        messages: List of message dicts with role and content
        model: Model deployment name (defaults to AZURE_OPENAI_MODEL)
        temperature: Sampling temperature (0.0 - 2.0)
        max_tokens: Maximum tokens in response
        json_mode: If True, response format is JSON

    Returns:
        str: Completion text from Azure OpenAI

    Raises:
        Exception: If API call fails after 3 retries
    """
    if model is None:
        model = os.getenv("AZURE_OPENAI_MODEL", "gpt-4")

    client = get_azure_openai_client()

    try:
        kwargs = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }

        # Add JSON mode if requested
        if json_mode:
            kwargs["response_format"] = {"type": "json_object"}

        response = client.chat.completions.create(**kwargs)

        content = response.choices[0].message.content
        logger.debug(f"Azure OpenAI API call successful. Tokens used: {response.usage.total_tokens}")
        return content

    except Exception as e:
        logger.error(f"Azure OpenAI API error: {str(e)}")
        raise


def validate_json_response(response_text: str, expected_keys: list = None) -> dict:
    """
    Validate and parse JSON response from Azure OpenAI

    Args:
        response_text: Raw response text from LLM
        expected_keys: List of required keys in JSON response

    Returns:
        dict: Parsed JSON response

    Raises:
        ValueError: If JSON parsing fails or required keys missing
    """
    import json

    try:
        # Try to extract JSON from markdown code blocks
        if "```json" in response_text:
            response_text = response_text.split("```json")[1].split("```")[0]
        elif "```" in response_text:
            response_text = response_text.split("```")[1].split("```")[0]

        parsed = json.loads(response_text.strip())

        # Validate required keys
        if expected_keys:
            missing_keys = [key for key in expected_keys if key not in parsed]
            if missing_keys:
                raise ValueError(f"Missing required keys: {missing_keys}")

        logger.debug("JSON response validated successfully")
        return parsed

    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse JSON response: {str(e)}")
        raise ValueError(f"Invalid JSON in LLM response: {str(e)}")
    except ValueError as e:
        logger.error(f"JSON validation failed: {str(e)}")
        raise
