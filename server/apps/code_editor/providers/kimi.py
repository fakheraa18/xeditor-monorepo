"""
Kimi provider for Kimi API endpoints.

Handles Kimi-specific reasoning extraction from OpenAI-compatible API responses.
Kimi API uses "reasoning" field in the delta to provide thinking/reasoning content.
"""

from typing import AsyncGenerator, Dict, Any
from urllib.parse import urlparse

from .http import GenericHTTPProvider
from .events import LLMEvent


def is_kimi_endpoint(base_url: str, path: str = "") -> bool:
    """Check if this is a Kimi API endpoint."""
    if not base_url:
        return False
    try:
        parsed = urlparse(base_url)
        host = parsed.netloc.lower()
        # Check for Kimi domain patterns
        if "kimi-k2.ai" in host or "kimi.moonshot.cn" in host:
            return True
    except Exception:
        pass
    return False


class KimiProvider(GenericHTTPProvider):
    """
    Provider for Kimi API endpoints.
    
    Extends GenericHTTPProvider to handle Kimi-specific reasoning extraction.
    Kimi API returns reasoning content in the "reasoning" field of the delta.
    """
    
    async def _parse_delta(self, delta: Dict[str, Any], data: Dict[str, Any]) -> AsyncGenerator[LLMEvent, None]:
        """
        Parse delta from Kimi API streaming response.
        
        Overrides parent method to extract reasoning field specific to Kimi API.
        """
        # Extract reasoning from delta (Kimi API uses "reasoning" field)
        if "reasoning" in delta and delta["reasoning"]:
            reasoning_chunk = delta["reasoning"]
            yield LLMEvent(type="thinking", content=reasoning_chunk)
        
        # Call parent to handle standard content extraction
        async for event in super()._parse_delta(delta, data):
            yield event
