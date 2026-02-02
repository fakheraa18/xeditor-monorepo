import type { TraceEvent } from '../../../../core/types';

export function useTraceEvents() {
  function getTraceEventLabel(event: TraceEvent): string {
    switch (event.type) {
      case 'context_retrieval':
        return `Context: ${event.contextType}`;
      case 'tool_call':
        return `Tool: ${event.toolName}`;
      case 'tool_chunk':
        return `Tool Output`;
      case 'tool_result':
        return `Tool Result`;
      case 'thinking':
        return 'Thinking';
      case 'assistant_message':
        return 'Assistant';
      case 'sub_agent_start':
        return `Sub-Agent: ${event.agentName}`;
      case 'sub_agent_end':
        return 'Sub-Agent End';
      default:
        return 'Unknown Event';
    }
  }

  function getThinkingContent(event: TraceEvent): string {
    if (event.type === 'thinking') {
      return event.content;
    }
    return '';
  }

  function generateTraceId(): string {
    if (typeof crypto !== 'undefined' && typeof crypto.randomUUID === 'function') {
      return crypto.randomUUID();
    }
    return `trace-${Date.now()}-${Math.random().toString(16).slice(2)}`;
  }

  function hasVisibleArgs(args: Record<string, unknown>): boolean {
    const keys = Object.keys(args);
    return keys.length > 0;
  }

  function formatArgs(args: Record<string, unknown>): string {
    const entries = Object.entries(args);
    if (entries.length === 0) return '';

    // Show first 2 key args, truncated
    const visible = entries.slice(0, 2).map(([key, value]) => {
      let valueStr = '';
      if (typeof value === 'string') {
        valueStr = value.length > 40 ? value.substring(0, 40) + '...' : value;
      } else if (typeof value === 'number' || typeof value === 'boolean') {
        valueStr = String(value);
      } else if (value === null) {
        valueStr = 'null';
      } else {
        valueStr = '[object]';
      }
      return `${key}: ${valueStr}`;
    });

    const suffix = entries.length > 2 ? ` (+${entries.length - 2} more)` : '';
    return visible.join(', ') + suffix;
  }

  function formatTime(timestamp: number): string {
    const date = new Date(timestamp);
    return date.toLocaleTimeString('en-US', {
      hour: '2-digit',
      minute: '2-digit',
      second: '2-digit',
      hour12: false,
    });
  }

  return {
    getTraceEventLabel,
    getThinkingContent,
    generateTraceId,
    hasVisibleArgs,
    formatArgs,
    formatTime,
  };
}
