"""
Pure Python Agent Framework for XEditor Local Companion.
Provides agent system with tool execution, sub-agents, and context management.
No LangGraph dependency - pure Python functions.
"""

from typing import Dict, Any, List, Optional, Callable, Awaitable
from pathlib import Path
import json
import re

from apps.code_editor.tools.context import ToolContext
from apps.code_editor.tools.executor import get_tool_executor
from apps.code_editor.tools.registry import get_tool_registry
from apps.code_editor.tools.recording import get_tool_recorder, ContextPolicy
from apps.code_editor.parsers.base import ResponseParser, ParsedResponse
from apps.code_editor.project import get_project_manager
from apps.code_editor.providers import get_provider, LLMRequest


class Agent:
    """
    Pure Python agent that manages conversation loop with tool calling.
    """
    
    def __init__(
        self,
        project_id: str,
        chat_id: str,
        llm_config: Dict[str, Any],
        parser: ResponseParser,
        max_steps: int = 10,
    ):
        """
        Initialize agent.
        
        Args:
            project_id: Project ID
            chat_id: Chat ID
            llm_config: LLM configuration dict
            parser: Response parser instance
            max_steps: Maximum tool calling steps
        """
        self.project_id = project_id
        self.chat_id = chat_id
        self.llm_config = llm_config
        self.parser = parser
        self.max_steps = max_steps
        
        # Get project root
        project_manager = get_project_manager()
        project = project_manager.get_project(project_id)
        project_root = None
        if project:
            folders = project.get("folders", [])
            if folders and len(folders) > 0:
                project_root = Path(folders[0].get("systemPath"))
        
        self.project_root = project_root or Path.cwd()
        
        # Initialize tool context
        self.tool_context = ToolContext(
            project_root=self.project_root,
            project_id=project_id,
            llm_config=llm_config,
            chat_id=chat_id,
        )
        
        # Tool registry and executor
        self.tool_registry = get_tool_registry()
        self.tool_executor = get_tool_executor(str(self.project_root))
        self.tool_recorder = get_tool_recorder()
        
        # Conversation state
        self.messages: List[Dict[str, Any]] = []
        self.tool_calls: List[Dict[str, Any]] = []
    
    async def run_turn(
        self,
        user_message: str,
        user_context: List[Dict[str, Any]],
        system_prompt: str,
        on_event: Callable[[str, Dict[str, Any]], Awaitable[None]],
    ) -> Dict[str, Any]:
        """
        Run a single agent turn with tool calling support.
        
        Args:
            user_message: User's message
            user_context: Context items from frontend
            system_prompt: System prompt
            on_event: Callback for streaming events
        
        Returns:
            Dict with turn data
        """
        # Build initial messages
        self.messages = []
        if system_prompt:
            self.messages.append({
                "role": "system",
                "content": system_prompt,
            })
        
        # Add conversation history (simplified - in production, load from chat)
        # Add user context
        if user_context:
            context_text = "\n".join([
                f"- {item.get('type', 'item')}: {item.get('content', '')[:200]}"
                for item in user_context[:5]  # Limit context items
            ])
            if context_text:
                self.messages.append({
                    "role": "user",
                    "content": f"Context:\n{context_text}\n\nUser message: {user_message}",
                })
            else:
                self.messages.append({
                    "role": "user",
                    "content": user_message,
                })
        else:
            self.messages.append({
                "role": "user",
                "content": user_message,
            })
        
        self.tool_calls = []
        accumulated_content = ""
        thinking_content = ""
        final_text = ""
        current_step = 0
        
        # Agent loop
        while current_step < self.max_steps:
            current_step += 1
            
            # Emit step_start event for iterations after the first (processing tool results)
            if current_step > 1:
                await on_event("step_start", {
                    "step": current_step,
                    "reason": "processing_tool_result",
                })
            
            # Stream LLM response
            accumulated_content = ""
            thinking_content = ""
            thinking_started = False
            received_thinking_from_provider = False
            
            try:
                # Build provider config
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
                llm_request = LLMRequest(
                    model_id=self.llm_config.get("id", ""),
                    messages=self.messages,
                    temperature=self.llm_config.get("temperature", 0.7),
                    max_tokens=self.llm_config.get("maxTokens"),
                    extra_payload=self.llm_config.get("extraPayload", {}),
                    provider_params=self.llm_config.get("providerParams") or {},
                    provider=self.llm_config.get("provider", ""),
                    connection=self.llm_config.get("connection", {}),
                    auth=self.llm_config.get("connection", {}).get("auth", {}),
                    family=self.llm_config.get("family"),
                    version=self.llm_config.get("version"),
                    mode=self.llm_config.get("mode", "agent"),
                )
                
                # Get provider and stream
                provider = get_provider(provider_config)
                
                async for event in provider.stream(llm_request):
                    if event.type == "thinking":
                        # Provider emits structured thinking events directly
                        received_thinking_from_provider = True
                        if event.content:
                            if not thinking_started:
                                await on_event("thinking_start", {})
                                thinking_started = True
                            thinking_content += event.content
                            await on_event("thinking_chunk", {"content": event.content})
                    
                    elif event.type == "content":
                        content_chunk = event.content or ""
                        
                        # Guard: if provider already emitted structured thinking events,
                        # strip any thinking tags from content to prevent duplication
                        if received_thinking_from_provider:
                            # Simple strip of <think> tags if present
                            content_chunk = re.sub(r'<think>.*?</think>', '', content_chunk, flags=re.DOTALL | re.IGNORECASE)
                            if not content_chunk.strip():
                                # Chunk was only thinking content, skip it
                                continue
                        
                        accumulated_content += content_chunk
                        
                        # CRITICAL: Get streamable content FIRST to buffer partial tool tokens
                        # This prevents partial tool call tokens (like <|tool) from leaking into UI
                        safe_content, is_tool_pending = self.parser.get_streamable_content(accumulated_content)
                        
                        # Stream safe content (content before any partial tool tokens)
                        # Even if is_tool_pending is True, safe_content contains content that's safe to stream
                        if safe_content and len(safe_content) > len(final_text):
                            new_safe_content = safe_content[len(final_text):]
                            if new_safe_content:
                                # Guard: strip thinking tags if provider already emitted structured thinking
                                if received_thinking_from_provider:
                                    new_safe_content = re.sub(r'<think>.*?</think>', '', new_safe_content, flags=re.DOTALL | re.IGNORECASE)
                                    if not new_safe_content.strip():
                                        # Skip if content was only thinking
                                        pass
                                    else:
                                        await on_event("content_chunk", {"content": new_safe_content})
                                else:
                                    await on_event("content_chunk", {"content": new_safe_content})
                                final_text = safe_content
                        
                        # Parse incrementally for tool calls and patches
                        parsed = self.parser.parse(accumulated_content)
                        
                        # Fallback: if provider didn't emit thinking events,
                        # try to extract from content (for models that emit <think> tags)
                        if not received_thinking_from_provider and parsed.thinking:
                            if not thinking_started:
                                await on_event("thinking_start", {})
                                thinking_started = True
                            
                            if parsed.thinking != thinking_content:
                                new_thinking = parsed.thinking[len(thinking_content):]
                                thinking_content = parsed.thinking
                                if new_thinking:
                                    await on_event("thinking_chunk", {"content": new_thinking})
                        
                        # Check if tool call was detected - if so, stop streaming and break
                        if parsed.tool_call:
                            last_parsed = parsed
                            break
                    
                    elif event.type == "end":
                        usage = event.usage
                        
                        # Final parse
                        if accumulated_content:
                            parsed = self.parser.parse(accumulated_content)
                            if parsed.final_text:
                                final_text = parsed.final_text
                            if parsed.thinking and not received_thinking_from_provider:
                                thinking_content = parsed.thinking
                                if not thinking_started:
                                    await on_event("thinking_start", {})
                                await on_event("thinking_chunk", {"content": thinking_content})
                                await on_event("thinking_end", {})
                            elif received_thinking_from_provider and thinking_content:
                                await on_event("thinking_end", {})
                        
                        break
                    
                    elif event.type == "error":
                        await on_event("error", {"message": event.error or "Unknown LLM error"})
                        break
                
            except Exception as e:
                await on_event("error", {"message": str(e)})
                raise
            
            # Check for tool call
            parsed = self.parser.parse(accumulated_content)
            if parsed.tool_call:
                tool_call = parsed.tool_call
                tool_name = tool_call.get("tool", "")
                tool_args = tool_call.get("args", {})
                
                # Emit tool start event
                tool_call_id = str(id(tool_call))
                await on_event("tool_start", {
                    "tool": tool_name,
                    "args": tool_args,
                    "id": tool_call_id,
                })
                
                # Execute tool
                tool_result = await self._execute_tool(tool_name, tool_args, on_event, tool_call_id)
                
                # Record tool call
                record = self.tool_recorder.record_tool_call(
                    tool_name,
                    tool_args,
                    tool_result,
                )
                
                # Store tool call
                tool_call_data = {
                    "id": tool_call_id,
                    "tool": tool_name,
                    "args": tool_args,
                    "result": tool_result.get("result") if tool_result.get("success") else None,
                    "error": tool_result.get("error"),
                    "contextPolicy": record.context_policy,
                }
                self.tool_calls.append(tool_call_data)
                
                # Emit tool result event
                await on_event("tool_result", {
                    "tool": tool_name,
                    "result": tool_result.get("result") if tool_result.get("success") else None,
                    "error": tool_result.get("error"),
                    "id": tool_call_id,
                })
                
                # Add tool result to messages based on context policy
                if record.context_policy == "full":
                    result_str = json.dumps(tool_result.get("result")) if isinstance(tool_result.get("result"), dict) else str(tool_result.get("result"))
                    self.messages.append({
                        "role": "assistant",
                        "content": accumulated_content,
                    })
                    self.messages.append({
                        "role": "user",
                        "content": f"Tool Result: {result_str}",
                    })
                elif record.context_policy == "summarize":
                    summary = f"Tool {tool_name} executed {'successfully' if tool_result.get('success') else 'with error'}"
                    if tool_result.get("error"):
                        summary += f": {tool_result.get('error')}"
                    self.messages.append({
                        "role": "assistant",
                        "content": accumulated_content,
                    })
                    self.messages.append({
                        "role": "user",
                        "content": summary,
                    })
                # meta_only and exclude don't add to context
                
                # Continue loop
                continue
            
            # No tool call - final answer
            break
        
        return {
            "assistantMessage": final_text,
            "thinking": thinking_content,
            "toolCalls": self.tool_calls,
        }
    
    async def _execute_tool(
        self,
        tool_name: str,
        args: Dict[str, Any],
        on_event: Optional[Callable[[str, Dict[str, Any]], Awaitable[None]]] = None,
        tool_call_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Execute a tool (system or custom).
        
        Args:
            tool_name: Name of the tool
            args: Tool arguments
            on_event: Optional callback for streaming events (tool_chunk)
            tool_call_id: Optional tool call ID for event correlation
        
        Returns:
            Dict with 'success', 'result', and optional 'error'
        """
        # Check if it's a system tool
        if self.tool_registry.is_system_tool(tool_name):
            # Use tool executor
            tool_result = await self.tool_executor.execute(tool_name, args, on_event, tool_call_id)
            return {
                "success": tool_result.success,
                "result": tool_result.result,
                "error": tool_result.error,
            }
        
        # Try to load custom tool
        # Get set_id, family, mode from llm_config
        set_id = self.llm_config.get("setId", "default")
        family = self.llm_config.get("family", "")
        mode = self.llm_config.get("mode", "agent")
        version = self.llm_config.get("version")
        
        tool_module = self.tool_registry.load_tool_module(
            tool_name,
            mode,
            set_id,
            family,
            version,
        )
        
        if tool_module:
            # Tool module should have a function with the tool name
            if hasattr(tool_module, tool_name):
                tool_func = getattr(tool_module, tool_name)
                try:
                    # Call tool with context
                    result = await tool_func(args, self.tool_context)
                    return result
                except Exception as e:
                    return {
                        "success": False,
                        "error": str(e),
                    }
        
        return {
            "success": False,
            "error": f"Tool not found: {tool_name}",
        }


class SubAgent:
    """
    Sub-agent that can be called from apps.code_editor.tools.
    Uses a smaller/faster LLM for quick tasks.
    """
    
    def __init__(
        self,
        llm_config: Dict[str, Any],
        parser: ResponseParser,
    ):
        """
        Initialize sub-agent.
        
        Args:
            llm_config: LLM configuration (can be different from main agent)
            parser: Response parser
        """
        self.llm_config = llm_config
        self.parser = parser
    
    async def call(
        self,
        messages: List[Dict[str, Any]],
        on_event: Optional[Callable[[str, Dict[str, Any]], Awaitable[None]]] = None,
    ) -> Dict[str, Any]:
        """
        Call the sub-agent with messages.
        
        Args:
            messages: List of message dicts
            on_event: Optional event callback
        
        Returns:
            Dict with 'success', 'content', and optional 'error'
        """
        accumulated_content = ""
        accumulated_thinking = ""
        
        try:
            # Build provider config
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
            llm_request = LLMRequest(
                model_id=self.llm_config.get("id", ""),
                messages=messages,
                temperature=self.llm_config.get("temperature", 0.7),
                max_tokens=self.llm_config.get("maxTokens", 1000),
                extra_payload=self.llm_config.get("extraPayload", {}),
                provider_params=self.llm_config.get("providerParams") or {},
                provider=self.llm_config.get("provider", ""),
                connection=self.llm_config.get("connection", {}),
                auth=self.llm_config.get("connection", {}).get("auth", {}),
                family=self.llm_config.get("family"),
                version=self.llm_config.get("version"),
            )
            
            # Get provider and stream
            provider = get_provider(provider_config)
            
            async for event in provider.stream(llm_request):
                if event.type == "thinking":
                    if event.content:
                        accumulated_thinking += event.content
                        if on_event:
                            await on_event("chunk", {"content": event.content})
                
                elif event.type == "content":
                    if event.content:
                        accumulated_content += event.content
                        if on_event:
                            await on_event("chunk", {"content": event.content})
                
                elif event.type == "end":
                    break
                
                elif event.type == "error":
                    return {
                        "success": False,
                        "error": event.error or "Unknown LLM error",
                    }
            
            # Parse accumulated content
            parsed = self.parser.parse(accumulated_content)
            
            # Use parsed thinking if available, otherwise use accumulated thinking
            thinking = parsed.thinking if parsed.thinking else accumulated_thinking
            
            return {
                "success": True,
                "content": parsed.final_text,
                "thinking": thinking,
            }
        
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
            }
