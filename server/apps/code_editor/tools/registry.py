"""
Tool Registry for XEditor Local Companion.
Manages system tools (always available) and per-mode tools from prompt sets.
"""

from pathlib import Path
from typing import Dict, List, Optional, Any, Callable
import importlib.util
import inspect

from apps.code_editor.sets.manager import get_set_manager
from apps.code_editor.tools.context import ToolContext


# System tools (always available)
SYSTEM_TOOLS = [
    "read_file",
    "write_file",
    "search_code",
    "list_dir",
    "run_command",
    "create_file",
    "delete_file",
    "file_exists",
    "search_replace",
    "todo_write",
    "semantic_search",
    "create_plan",
    "ask_question",
    "delegate_task",
]


class ToolRegistry:
    """Registry for managing tools (system + set-specific)."""
    
    def __init__(self):
        self._loaded_tools: Dict[str, Any] = {}
    
    def get_tools_for_mode(
        self,
        mode: str,
        set_id: str = "default",
        family: Optional[str] = None,
        version: Optional[str] = None,
    ) -> List[str]:
        """
        Get all tools available for a mode.
        
        If a tools.json allowlist exists for this set/family/mode/version,
        returns exactly that list (explicit-only mode).
        Otherwise, falls back to legacy behavior: all system tools + all set tool files.
        """
        set_manager = get_set_manager()
        set_obj = set_manager.get_set(set_id)
        
        # Check for tools.json allowlist first (explicit-only mode)
        if set_obj and family:
            tools_config = set_obj.read_tools_config(family, mode, version)
            if tools_config is not None:
                # Explicit allowlist exists - return exactly those tools
                return tools_config
        
        # Legacy fallback: all system tools + all set tool files
        tools = list(SYSTEM_TOOLS)
        
        if set_obj and family:
            tools_path = set_obj.get_tools_path(family, version)
            if tools_path:
                # Load tools from the directory
                set_tools = self._load_tools_from_directory(tools_path)
                tools.extend(set_tools)
        
        return tools
    
    def get_available_custom_tools(
        self,
        set_id: str,
        family: str,
        version: Optional[str] = None,
    ) -> List[str]:
        """Get list of custom tool files available for a set/family (shared across modes, not the allowlist)."""
        set_manager = get_set_manager()
        set_obj = set_manager.get_set(set_id)
        
        if not set_obj:
            return []
        
        tools_path = set_obj.get_tools_path(family, version)
        if tools_path:
            return self._load_tools_from_directory(tools_path)
        
        return []
    
    def _load_tools_from_directory(self, tools_dir: Path) -> List[str]:
        """Load tool names from a tools directory."""
        tools = []
        
        for tool_file in tools_dir.glob("*.py"):
            if tool_file.stem == "__init__":
                continue
            
            tool_name = tool_file.stem
            tools.append(tool_name)
        
        return tools
    
    def load_tool_module(
        self,
        tool_name: str,
        mode: str,
        set_id: str = "default",
        family: Optional[str] = None,
        version: Optional[str] = None,
    ) -> Optional[Any]:
        """Load a tool module for execution."""
        # Check cache (tools are shared across modes, so cache key doesn't include mode)
        cache_key = f"{set_id}:{family}:{version}:{tool_name}"
        if cache_key in self._loaded_tools:
            return self._loaded_tools[cache_key]
        
        # System tools are handled by executor
        if tool_name in SYSTEM_TOOLS:
            return None  # Executor handles these
        
        # Try to load from set (family-level, shared across modes)
        set_manager = get_set_manager()
        set_obj = set_manager.get_set(set_id)
        if set_obj and family:
            tools_path = set_obj.get_tools_path(family, version)
            if tools_path:
                tool_file = tools_path / f"{tool_name}.py"
                if tool_file.exists():
                    try:
                        spec = importlib.util.spec_from_file_location(
                            f"tool_{cache_key}",
                            tool_file
                        )
                        if spec and spec.loader:
                            module = importlib.util.module_from_spec(spec)
                            spec.loader.exec_module(module)
                            
                            # Validate tool interface
                            is_valid, error = self.validate_tool_module(module, tool_name)
                            if not is_valid:
                                print(f"Tool {tool_name} validation failed: {error}")
                                # Still return module but log warning
                                # In production, you might want to raise an exception
                            
                            self._loaded_tools[cache_key] = module
                            return module
                    except Exception as e:
                        print(f"Failed to load tool {tool_name}: {e}")
        
        return None
    
    def is_system_tool(self, tool_name: str) -> bool:
        """Check if a tool is a system tool."""
        return tool_name in SYSTEM_TOOLS
    
    def is_tool_allowed(
        self,
        tool_name: str,
        mode: str,
        set_id: str = "default",
        family: Optional[str] = None,
        version: Optional[str] = None,
    ) -> bool:
        """Check if a tool is allowed for the given set/mode configuration."""
        allowed_tools = self.get_tools_for_mode(mode, set_id, family, version)
        return tool_name in allowed_tools
    
    def validate_tool_interface(
        self,
        tool_func: Callable,
        tool_name: str,
    ) -> tuple[bool, Optional[str]]:
        """
        Validate that a tool function matches the standard interface.
        
        Expected signature:
        async def tool_name(args: Dict[str, Any], context: ToolContext) -> Dict[str, Any]
        
        Args:
            tool_func: The tool function to validate
            tool_name: Name of the tool (for error messages)
        
        Returns:
            Tuple of (is_valid, error_message)
        """
        if not callable(tool_func):
            return False, f"Tool {tool_name} is not callable"
        
        # Check if it's async
        if not inspect.iscoroutinefunction(tool_func):
            return False, f"Tool {tool_name} must be an async function"
        
        # Get signature
        try:
            sig = inspect.signature(tool_func)
            params = list(sig.parameters.values())
            
            # Check parameter count (should have 2: args and context)
            if len(params) < 2:
                return False, f"Tool {tool_name} must have 2 parameters: args and context"
            
            # Check first parameter (args)
            args_param = params[0]
            if args_param.annotation != inspect.Signature.empty:
                # Check if it's Dict[str, Any] or compatible
                if not (hasattr(args_param.annotation, '__origin__') and 
                        args_param.annotation.__origin__ is dict):
                    return False, f"Tool {tool_name} first parameter 'args' should be Dict[str, Any]"
            
            # Check second parameter (context)
            context_param = params[1]
            if context_param.annotation != inspect.Signature.empty:
                # Check if it's ToolContext or compatible
                if not (inspect.isclass(context_param.annotation) and 
                        issubclass(context_param.annotation, ToolContext)):
                    # Allow Any or empty annotation too
                    if context_param.annotation not in (Any, inspect.Signature.empty):
                        return False, f"Tool {tool_name} second parameter 'context' should be ToolContext"
            
            # Check return type annotation (should be Dict[str, Any])
            return_annotation = sig.return_annotation
            if return_annotation != inspect.Signature.empty:
                if not (hasattr(return_annotation, '__origin__') and 
                        return_annotation.__origin__ is dict):
                    return False, f"Tool {tool_name} should return Dict[str, Any]"
            
            return True, None
        
        except Exception as e:
            return False, f"Error validating tool {tool_name}: {str(e)}"
    
    def validate_tool_module(
        self,
        tool_module: Any,
        tool_name: str,
    ) -> tuple[bool, Optional[str]]:
        """
        Validate that a tool module has a valid tool function.
        
        Args:
            tool_module: The loaded tool module
            tool_name: Name of the tool
        
        Returns:
            Tuple of (is_valid, error_message)
        """
        if not hasattr(tool_module, tool_name):
            return False, f"Tool module does not have function '{tool_name}'"
        
        tool_func = getattr(tool_module, tool_name)
        return self.validate_tool_interface(tool_func, tool_name)


# Singleton instance
_tool_registry: Optional[ToolRegistry] = None


def get_tool_registry() -> ToolRegistry:
    """Get the singleton ToolRegistry instance."""
    global _tool_registry
    if _tool_registry is None:
        _tool_registry = ToolRegistry()
    return _tool_registry
