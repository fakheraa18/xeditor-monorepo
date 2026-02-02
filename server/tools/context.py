"""
Tool Context for XEditor Local Companion.
Provides tools with access to project context, LLM calling, and other tools.
"""

from pathlib import Path
from typing import Dict, Any, Optional, List, Callable, Awaitable
from dataclasses import dataclass

from tools.executor import execute_tool, ToolExecutor
from apps.code_editor.indexing_builder import handle_retrieve_chunks
from providers import get_provider, LLMRequest


@dataclass
class ToolContext:
    """
    Context provided to tools during execution.
    Gives tools access to project information, LLM calling, and other tools.
    """
    
    project_root: Path
    project_id: str
    llm_config: Dict[str, Any]
    chat_id: Optional[str] = None
    conversation_context: Optional[List[Dict[str, Any]]] = None
    tool_call_id: Optional[str] = None
    emit_event: Optional[Callable[[str, Dict[str, Any]], Awaitable[None]]] = None
    
    def __init__(
        self,
        project_root: Path,
        project_id: str,
        llm_config: Dict[str, Any],
        chat_id: Optional[str] = None,
        conversation_context: Optional[List[Dict[str, Any]]] = None,
        tool_call_id: Optional[str] = None,
        emit_event: Optional[Callable[[str, Dict[str, Any]], Awaitable[None]]] = None,
    ):
        self.project_root = Path(project_root) if isinstance(project_root, str) else project_root
        self.project_id = project_id
        self.llm_config = llm_config
        self.chat_id = chat_id
        self.conversation_context = conversation_context or []
        self.tool_call_id = tool_call_id
        self.emit_event = emit_event
    
    async def emit_tool_chunk(self, content: str) -> None:
        """
        Emit a tool chunk event for streaming tool output.
        
        Args:
            content: Incremental output content from the tool
        """
        if self.emit_event and self.tool_call_id:
            await self.emit_event("tool_chunk", {
                "id": self.tool_call_id,
                "content": content,
            })
    
    async def call_llm(
        self,
        messages: List[Dict[str, Any]],
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        **kwargs: Any
    ) -> Dict[str, Any]:
        """
        Call the LLM with the given messages.
        Uses the current LLM configuration from context.
        
        Args:
            messages: List of message dicts with 'role' and 'content'
            temperature: Override temperature (uses llm_config default if not provided)
            max_tokens: Override max_tokens (uses llm_config default if not provided)
            **kwargs: Additional parameters to pass to LLM
        
        Returns:
            Dict with 'success', 'content', and optional 'error'
        """
        # Build provider config from llm_config
        provider_config = {
            "provider": self.llm_config.get("provider", ""),
            "id": self.llm_config.get("id", ""),
            "connection": self.llm_config.get("connection", {}),
            "auth": self.llm_config.get("connection", {}).get("auth", {}),
            "localCompanion": self.llm_config.get("localCompanion", {}),
            "family": self.llm_config.get("family"),
            "version": self.llm_config.get("version"),
        }
        
        # Build LLM request
        request = LLMRequest(
            model_id=self.llm_config.get("id", ""),
            messages=messages,
            temperature=temperature if temperature is not None else self.llm_config.get("temperature", 0.7),
            max_tokens=max_tokens if max_tokens is not None else self.llm_config.get("maxTokens"),
            extra_payload=kwargs,
            provider_params=self.llm_config.get("providerParams") or {},
            provider=self.llm_config.get("provider", ""),
            connection=self.llm_config.get("connection", {}),
            auth=self.llm_config.get("connection", {}).get("auth", {}),
            family=self.llm_config.get("family"),
            version=self.llm_config.get("version"),
            mode=self.llm_config.get("mode"),
        )
        
        try:
            provider = get_provider(provider_config)
            response = await provider.chat(request)
            
            if response.error:
                return {
                    "success": False,
                    "error": response.error,
                }
            else:
                return {
                    "success": True,
                    "content": response.content,
                }
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
            }
    
    async def execute_tool(
        self,
        tool_name: str,
        args: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Execute another tool by name.
        
        Args:
            tool_name: Name of the tool to execute
            args: Arguments to pass to the tool
        
        Returns:
            Dict with 'success', 'result', and optional 'error'
        """
        return await execute_tool(
            tool_name,
            args,
            str(self.project_root)
        )
    
    def get_context(self) -> List[Dict[str, Any]]:
        """
        Get the current conversation context.
        
        Returns:
            List of message dicts from the conversation
        """
        return self.conversation_context.copy() if self.conversation_context else []
    
    async def vector_search(
        self,
        query: str,
        limit: int = 10,
        folder_ids: Optional[List[str]] = None,
        embedding_model_id: Optional[str] = None,
        hf_token: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Perform vector search on the project index.
        
        Args:
            query: Search query text
            limit: Maximum number of results to return
            folder_ids: Optional list of folder IDs to limit search scope
            embedding_model_id: Optional embedding model ID (uses project default if not provided)
            hf_token: Optional HuggingFace token for gated models
        
        Returns:
            Dict with 'success', 'chunks' (list of results), and optional 'error'
        """
        payload = {
            "projectId": self.project_id,
            "query": query,
            "limit": limit,
        }
        
        if folder_ids:
            payload["folderIds"] = folder_ids
        
        if embedding_model_id:
            payload["embeddingModelId"] = embedding_model_id
        
        if hf_token:
            payload["hfToken"] = hf_token
        
        try:
            response = await handle_retrieve_chunks(payload)
            
            if response.get("success"):
                return {
                    "success": True,
                    "chunks": response.get("chunks", []),
                }
            else:
                return {
                    "success": False,
                    "error": response.get("error", "Unknown search error"),
                    "chunks": [],
                }
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "chunks": [],
            }
