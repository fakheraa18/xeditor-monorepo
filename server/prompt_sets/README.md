# Prompt Sets Documentation

This directory contains prompt sets for different model families and modes. Prompt sets allow you to customize system prompts, response parsers, and tools for specific models and use cases.

## Directory Structure

```
prompt_sets/
├── default/              # Built-in prompt sets (bundled with XEditor)
│   ├── gpt/             # GPT family prompts
│   │   ├── parser.py    # Shared parser (used by all modes)
│   │   ├── agent/       # Agent mode
│   │   │   ├── prompt.py
│   │   │   ├── tools.json   # Tool allowlist
│   │   │   └── tools/       # Custom tools (optional)
│   │   ├── ask/         # Ask mode
│   │   │   ├── prompt.py
│   │   │   └── tools.json
│   │   └── plan/        # Plan mode
│   │       ├── prompt.py
│   │       └── tools.json
│   ├── claude/          # Claude family prompts
│   │   ├── parser.py    # Shared parser
│   │   └── ...
│   └── ...
```

**Community/User Prompt Sets** are stored in:
```
~/.xeditor/llm/
├── {username}/
│   └── {set-name}/
│       ├── __init__.py      # Contains SET_METADATA
│       ├── gpt/
│       │   ├── parser.py    # Shared parser (used by all modes)
│       │   ├── agent/
│       │   │   ├── prompt.py
│       │   │   ├── tools.json
│       │   │   └── tools/
│       │   ├── ask/
│       │   │   ├── prompt.py
│       │   │   └── tools.json
│       │   └── plan/
│       │       ├── prompt.py
│       │       └── tools.json
│       └── ...
```

## Creating a Prompt Set

### 1. Set Metadata

Each prompt set requires an `__init__.py` file with `SET_METADATA`:

```python
"""My Custom Prompt Set"""

SET_METADATA = {
    "id": "username/my-custom-set",
    "name": "My Custom Prompt Set",
    "author": "Your Name",
    "version": "1.0.0",
    "description": "Description of your prompt set",
    "modes": ["agent", "ask", "plan"],
    "family": "gpt",
    "families": ["gpt", "claude"],
    "isBuiltIn": False
}
```

### 2. Prompt Files

Create prompt files for each mode you want to support:

**File**: `{family}/{mode}/prompt.py`

```python
"""System prompt for {mode} mode"""

SYSTEM_PROMPT = """You are an AI assistant.

Operating System: {{system_info.os}}
Workspace: {{system_info.workspace}}

# Available Tools

{{tools}}

Follow these guidelines:
- Be helpful and concise
- Use tools when needed
"""

PARAMETERS = {
    "temperature": 0.7,
    "maxTokens": 4000,
}
```

### 3. Tool Allowlist (tools.json)

**Important**: Tools are NOT automatically available. You must explicitly specify which tools are allowed for each mode using a `tools.json` file.

**File**: `{family}/{mode}/tools.json`

```json
{
  "tools": [
    "read_file",
    "write_file",
    "search_code",
    "list_dir",
    "my_custom_tool"
  ]
}
```

Only tools listed in this file will be:
- Injected into the `{{tools}}` variable in your prompt
- Allowed to execute when the LLM calls them

If `tools.json` doesn't exist, the system falls back to legacy behavior (all system tools + all custom tools in the mode's tools/ directory).

### 4. Template Variables

You can use template variables in your prompts that will be automatically replaced:

#### System Information

- `{{system_info.os}}` - Operating system (e.g., "Linux", "Windows", "Darwin")
- `{{system_info.osVersion}}` - OS version/release
- `{{system_info.shell}}` - Default shell path (e.g., "/bin/zsh")
- `{{system_info.home}}` - Home directory path
- `{{system_info.workspace}}` - Current workspace directory

#### Tools

- `{{tools}}` - Complete formatted tool definitions section with descriptions and parameters

This will be replaced with detailed markdown documentation of all **allowed** tools (from tools.json), including:
- Tool names and descriptions
- Parameter documentation

#### Project Information

- `{{project_info.name}}` - Project name (if available)
- `{{project_info.root}}` - Primary project root path (if available)
- `{{project_info.folderCount}}` - Number of folders in the project

**Note**: Project info is only available when a project is active.

#### User Context

- `{{user_context_summary}}` - Summary of user-provided context items (files, selected code, etc.)

### 5. Response Parsers

Create a parser file for the family (shared across all modes):

**File**: `{family}/parser.py` (or `{family}/{version}/parser.py` for version-specific parsers)

```python
"""Response parser for {family} family (shared across modes)"""

from parsers.base import ResponseParser, ParsedResponse

class CustomParser(ResponseParser):
    family = "my_family"
    
    def parse(self, content: str) -> ParsedResponse:
        # Parse the LLM response
        # Extract thinking, tool calls, final text, etc.
        return ParsedResponse(
            thinking=None,
            tool_call=None,
            final_text=content,
        )
    
    def strip_tags(self, content: str) -> str:
        return content.strip()

parser = CustomParser()
```

**Note**: Parsers are shared across all modes (ask, plan, agent) for a given family. If you need version-specific parsing behavior, you can create `{family}/{version}/parser.py` instead of `{family}/parser.py`.

### 6. Custom Tools

You can add custom tools specific to your prompt set. Custom tools **must** include a `TOOL_DESCRIPTOR` for the LLM to understand them.

**File**: `{family}/{mode}/tools/my_tool.py`

```python
"""Custom tool example"""

from typing import Dict, Any
from tools.context import ToolContext


# REQUIRED: TOOL_DESCRIPTOR defines how the tool appears in prompts
TOOL_DESCRIPTOR = {
    "description": "Performs a custom operation on the given input.",
    "parameters": {
        "input": {
            "type": "string",
            "required": True,
            "description": "The input to process",
        },
        "format": {
            "type": "string",
            "required": False,
            "description": "Output format (json or text)",
        },
    },
}


async def my_tool(
    args: Dict[str, Any],
    context: ToolContext
) -> Dict[str, Any]:
    """
    Tool implementation.
    
    Args:
        args: Tool arguments from LLM (matches TOOL_DESCRIPTOR parameters)
        context: Framework context
    
    Returns:
        Dict with 'success', 'result', and optional 'error'
    """
    input_value = args.get("input", "")
    output_format = args.get("format", "text")
    
    try:
        # Your tool logic here
        result = f"Processed: {input_value}"
        
        # Stream output to UI (optional)
        await context.emit_tool_chunk(f"Processing {input_value}...")
        
        return {
            "success": True,
            "result": {"output": result, "format": output_format},
        }
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
        }
```

**Remember**: Add your custom tool name to `tools.json` for it to be available!

### ToolContext Methods

Custom tools receive a `ToolContext` with these methods:

- `await context.call_llm(messages, temperature, max_tokens)` - Call the LLM
- `await context.execute_tool(tool_name, args)` - Execute another tool
- `await context.vector_search(query, limit)` - Semantic code search
- `context.get_context()` - Get conversation context
- `await context.emit_tool_chunk(content)` - Stream output to UI
- `context.project_root` - Path to project root

## Available System Tools

These tools are provided by XEditor. Include them in your `tools.json` to make them available:

| Tool | Description |
|------|-------------|
| `read_file` | Read file contents with optional line range |
| `write_file` | Write/create files |
| `search_code` | Search codebase using ripgrep |
| `list_dir` | List directory contents |
| `run_command` | Execute shell commands |
| `create_file` | Create new files |
| `delete_file` | Delete files |
| `file_exists` | Check file/directory existence |
| `search_replace` | Find and replace text in files |
| `todo_write` | Manage task lists |
| `semantic_search` | Vector-based code search |

## Example: Complete Prompt Set

```
my-custom-set/
├── __init__.py           # SET_METADATA
├── gpt/
│   ├── parser.py         # Shared parser (used by all modes)
│   ├── agent/
│   │   ├── prompt.py
│   │   ├── tools.json    # ["read_file", "write_file", "my_tool"]
│   │   └── tools/
│   │       └── my_tool.py
│   ├── ask/
│   │   ├── prompt.py
│   │   └── tools.json    # []  (no tools for ask mode)
│   └── plan/
│       ├── prompt.py
│       └── tools.json    # []  (no tools for plan mode)
└── claude/
    ├── parser.py         # Shared parser
    └── agent/
        ├── prompt.py
        └── tools.json
```

## Importing/Exporting Sets

You can export prompt sets as ZIP files and import them into other XEditor installations. This makes it easy to share prompt sets with the community.

## Best Practices

1. **Explicit Tool Lists**: Always create a `tools.json` for each mode. This gives you precise control over what tools are available.

2. **Include TOOL_DESCRIPTOR**: Always add `TOOL_DESCRIPTOR` to custom tools so the LLM understands how to use them.

3. **Use Template Variables**: Leverage `{{system_info}}`, `{{tools}}`, and other variables to make prompts dynamic.

4. **Mode-Specific Configuration**: Different modes have different needs:
   - `ask` / `plan`: Usually no tools needed
   - `agent`: Full tool access for coding tasks
   - `debug`: Read-only tools for investigation

5. **Test Thoroughly**: Test your prompts with different models and scenarios.

## Community Prompt Sets

We encourage the community to create and share prompt sets! When creating a prompt set:

1. Use clear, descriptive names
2. Include comprehensive `TOOL_DESCRIPTOR` for custom tools
3. Create appropriate `tools.json` files for each mode
4. Test with multiple models if possible
5. Follow the directory structure conventions
6. Use semantic versioning for updates

## Support

For questions or issues with prompt sets, please refer to the main XEditor documentation or open an issue on the project repository.
