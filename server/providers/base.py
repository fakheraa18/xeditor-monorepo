"""
Base class for LLM providers.

Each provider implements the LLMProvider interface to normalize different
LLM APIs (OpenAI, Gemini, LM Studio, vLLM, etc.) into a common event stream.
"""

from abc import ABC, abstractmethod
from typing import AsyncGenerator, Dict, Any

from .events import LLMEvent, LLMResponse, LLMRequest


class LLMProvider(ABC):
    """
    Abstract base class for all LLM providers.
    
    Providers are responsible for:
    - Handling authentication specific to their API
    - Converting messages to their wire format
    - Making HTTP requests to their endpoints
    - Normalizing responses into LLMEvent streams
    - Extracting thinking/reasoning from provider-specific formats
    """
    
    def __init__(self, config: Dict[str, Any]):
        """
        Initialize the provider with configuration.
        
        Args:
            config: Model configuration including connection, auth, etc.
        """
        self.config = config
        self.connection = config.get("connection", {})
        self.auth = config.get("auth", {})
    
    @abstractmethod
    async def stream(self, request: LLMRequest) -> AsyncGenerator[LLMEvent, None]:
        """
        Stream response as normalized LLMEvents.
        
        This is the primary method that consumers should use.
        
        Args:
            request: Normalized LLM request
            
        Yields:
            LLMEvent objects (thinking, content, end, error)
        """
        # This is needed to make it a generator even though it's abstract
        if False:
            yield LLMEvent(type="end")
    
    async def chat(self, request: LLMRequest) -> LLMResponse:
        """
        Non-streaming request.
        
        Default implementation collects stream into LLMResponse.
        Providers can override for more efficient non-streaming calls.
        
        Args:
            request: Normalized LLM request
            
        Returns:
            LLMResponse with complete content
        """
        content_parts: list[str] = []
        thinking_parts: list[str] = []
        usage = None
        finish_reason = None
        error = None
        
        async for event in self.stream(request):
            if event.type == "content" and event.content:
                content_parts.append(event.content)
            elif event.type == "thinking" and event.content:
                thinking_parts.append(event.content)
            elif event.type == "end":
                usage = event.usage
                finish_reason = event.finish_reason
            elif event.type == "error":
                error = event.error
                break
        
        return LLMResponse(
            content="".join(content_parts),
            thinking="".join(thinking_parts) if thinking_parts else None,
            usage=usage,
            finish_reason=finish_reason,
            error=error,
        )
    
    def get_base_url(self) -> str:
        """Get the base URL from connection config."""
        return self.connection.get("baseUrl", "")
    
    def get_path(self) -> str:
        """Get the API path from connection config."""
        return self.connection.get("path", "")
    
    def build_url(self, path_override: str | None = None) -> str:
        """Build full URL from base URL and path."""
        base_url = self.get_base_url().rstrip("/")
        path = (path_override or self.get_path()).lstrip("/")
        
        if path:
            return f"{base_url}/{path}"
        return base_url
    
    def get_headers(self) -> Dict[str, str]:
        """Get headers from connection config."""
        headers = dict(self.connection.get("headers", {}))
        headers.setdefault("Content-Type", "application/json")
        return headers
    
    def apply_auth(self, headers: Dict[str, str], url: str) -> tuple[Dict[str, str], str]:
        """
        Apply authentication to headers and URL.
        
        Supports: none, bearer, header, query_param, multi_header
        
        Args:
            headers: Request headers to modify
            url: Request URL (may be modified for query_param auth)
            
        Returns:
            Tuple of (modified_headers, modified_url)
        """
        auth_type = self.auth.get("type", "none")
        
        if auth_type == "bearer" and self.auth.get("apiKey"):
            headers["Authorization"] = f"Bearer {self.auth['apiKey']}"
        
        elif auth_type == "header" and self.auth.get("headerName"):
            value = self.auth.get("value", "")
            if value:
                headers[self.auth["headerName"]] = value
        
        elif auth_type == "query_param" and self.auth.get("paramName"):
            value = self.auth.get("value", "")
            if value:
                from urllib.parse import urlencode, parse_qs, urlparse, urlunparse
                parsed = urlparse(url)
                query_params = parse_qs(parsed.query)
                query_params[self.auth["paramName"]] = [value]
                new_query = urlencode(query_params, doseq=True)
                url = urlunparse((
                    parsed.scheme,
                    parsed.netloc,
                    parsed.path,
                    parsed.params,
                    new_query,
                    parsed.fragment
                ))
        
        elif auth_type == "multi_header" and self.auth.get("headers"):
            for header in self.auth["headers"]:
                name = header.get("name", "")
                value = header.get("value", "")
                if name and value:
                    headers[name] = value
        
        return headers, url
