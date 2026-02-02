"""
Tool Recording for XEditor Local Companion.
Tracks tool calls and their results with context policies.
"""

from typing import Dict, Any, Optional, List, Literal
from dataclasses import dataclass, asdict
from datetime import datetime
import json


ContextPolicy = Literal["full", "summarize", "meta_only", "exclude"]


@dataclass
class ToolCallRecord:
    """Record of a tool call."""
    
    tool_name: str
    args: Dict[str, Any]
    result: Dict[str, Any]
    timestamp: int
    context_policy: ContextPolicy
    success: bool
    error: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "toolName": self.tool_name,
            "args": self.args,
            "result": self.result,
            "timestamp": self.timestamp,
            "contextPolicy": self.context_policy,
            "success": self.success,
            "error": self.error,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ToolCallRecord":
        """Create from dictionary."""
        return cls(
            tool_name=data.get("toolName", ""),
            args=data.get("args", {}),
            result=data.get("result", {}),
            timestamp=data.get("timestamp", int(datetime.now().timestamp() * 1000)),
            context_policy=data.get("contextPolicy", "meta_only"),
            success=data.get("success", False),
            error=data.get("error"),
        )


class ToolRecorder:
    """Records tool calls and manages context policies."""
    
    def __init__(self):
        self.records: List[ToolCallRecord] = []
        self._default_policies: Dict[str, ContextPolicy] = {
            "read_file": "full",
            "write_file": "meta_only",
            "search_code": "summarize",
            "list_dir": "summarize",
            "run_command": "summarize",
            "create_file": "meta_only",
            "delete_file": "meta_only",
            "file_exists": "meta_only",
        }
    
    def record_tool_call(
        self,
        tool_name: str,
        args: Dict[str, Any],
        result: Dict[str, Any],
        context_policy: Optional[ContextPolicy] = None,
    ) -> ToolCallRecord:
        """
        Record a tool call.
        
        Args:
            tool_name: Name of the tool
            args: Arguments passed to the tool
            result: Result from tool execution
            context_policy: Override context policy (uses default if not provided)
        
        Returns:
            ToolCallRecord instance
        """
        if context_policy is None:
            context_policy = self._default_policies.get(tool_name, "meta_only")
        
        success = result.get("success", False)
        error = result.get("error")
        
        record = ToolCallRecord(
            tool_name=tool_name,
            args=args,
            result=result,
            timestamp=int(datetime.now().timestamp() * 1000),
            context_policy=context_policy,
            success=success,
            error=error,
        )
        
        self.records.append(record)
        return record
    
    def get_records(
        self,
        tool_name: Optional[str] = None,
        policy: Optional[ContextPolicy] = None,
    ) -> List[ToolCallRecord]:
        """
        Get recorded tool calls.
        
        Args:
            tool_name: Filter by tool name (optional)
            policy: Filter by context policy (optional)
        
        Returns:
            List of ToolCallRecord instances
        """
        records = self.records
        
        if tool_name:
            records = [r for r in records if r.tool_name == tool_name]
        
        if policy:
            records = [r for r in records if r.context_policy == policy]
        
        return records
    
    def get_context_summary(self, limit: Optional[int] = None) -> str:
        """
        Get a summary of tool calls for LLM context.
        Only includes records with policy 'full' or 'summarize'.
        
        Args:
            limit: Maximum number of records to include
        
        Returns:
            Formatted string summary
        """
        relevant_records = [
            r for r in self.records
            if r.context_policy in ("full", "summarize")
        ]
        
        if limit:
            relevant_records = relevant_records[-limit:]
        
        if not relevant_records:
            return ""
        
        lines = ["Tool calls:"]
        for record in relevant_records:
            if record.context_policy == "full":
                # Include full result
                result_str = json.dumps(record.result, indent=2)
                lines.append(f"- {record.tool_name}({json.dumps(record.args)}): {result_str}")
            else:
                # Summarize
                success_str = "✓" if record.success else "✗"
                error_str = f" - {record.error}" if record.error else ""
                lines.append(f"- {success_str} {record.tool_name}({json.dumps(record.args)}){error_str}")
        
        return "\n".join(lines)
    
    def get_metadata(self) -> List[Dict[str, Any]]:
        """
        Get all tool call records as metadata (for chat history).
        
        Returns:
            List of record dictionaries
        """
        return [r.to_dict() for r in self.records]
    
    def clear(self) -> None:
        """Clear all records."""
        self.records.clear()
    
    def set_default_policy(self, tool_name: str, policy: ContextPolicy) -> None:
        """Set default context policy for a tool."""
        self._default_policies[tool_name] = policy
    
    def get_default_policy(self, tool_name: str) -> ContextPolicy:
        """Get default context policy for a tool."""
        return self._default_policies.get(tool_name, "meta_only")


# Singleton instance
_recorder: Optional[ToolRecorder] = None


def get_tool_recorder() -> ToolRecorder:
    """Get the singleton ToolRecorder instance."""
    global _recorder
    if _recorder is None:
        _recorder = ToolRecorder()
    return _recorder
