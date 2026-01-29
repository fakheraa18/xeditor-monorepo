<template>
  <div class="monaco-tool-editor-container">
    <div class="tool-interface-hint q-pa-sm bg-grey-2 text-caption">
      <div class="text-weight-medium q-mb-xs">Tool Interface:</div>
      <pre class="q-ma-none">
# TOOL_DESCRIPTOR is REQUIRED for prompt injection
TOOL_DESCRIPTOR = {
    "description": "What the tool does",
    "parameters": {"param_name": {"type": "string", "required": True, "description": "..."}}
}

async def tool_name(args: Dict[str, Any], context: ToolContext) -> Dict[str, Any]:
    return {"success": True, "result": {...}}</pre
      >
      <div class="q-mt-xs">
        <strong>Context methods:</strong> call_llm(), execute_tool(), get_context(),
        vector_search(), emit_tool_chunk()
      </div>
    </div>
    <div ref="editorContainer" class="monaco-tool-editor" :style="{ height: height }"></div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, onUnmounted, watch } from 'vue';

// Dynamic import for Monaco
// eslint-disable-next-line @typescript-eslint/consistent-type-imports
type MonacoEditorType = import('monaco-editor').editor.IStandaloneCodeEditor;
// eslint-disable-next-line @typescript-eslint/consistent-type-imports
type MonacoModule = typeof import('monaco-editor');
let monaco: MonacoModule | null = null;

interface Props {
  modelValue?: string;
  toolName?: string;
  height?: string;
}

const props = withDefaults(defineProps<Props>(), {
  modelValue: '',
  height: '400px',
});

const emit = defineEmits<{
  'update:modelValue': [value: string];
}>();

const editorContainer = ref<HTMLDivElement | null>(null);
let editorInstance: MonacoEditorType | null = null;

const getDefaultTemplate = (toolName: string = 'my_tool') => {
  return `"""Custom tool: ${toolName}"""

from typing import Dict, Any
from tools.context import ToolContext


# TOOL_DESCRIPTOR is required for the LLM to understand this tool.
# It defines the tool's description and parameters that will be injected into the prompt.
TOOL_DESCRIPTOR = {
    "description": "TODO: Describe what this tool does",
    "parameters": {
        "input": {
            "type": "string",
            "required": True,
            "description": "TODO: Describe this parameter",
        },
        # Add more parameters as needed
    },
}


async def ${toolName}(
    args: Dict[str, Any],
    context: ToolContext
) -> Dict[str, Any]:
    """
    Tool implementation.

    Args:
        args: Tool arguments from LLM (matches TOOL_DESCRIPTOR parameters)
        context: Framework context (project_root, llm_config, etc.)

    Returns:
        Dict with 'success', 'result', and optional 'error'
    """
    try:
        # Access parameters from args
        input_value = args.get("input", "")

        # TODO: Implement tool logic
        # Example: Access project root
        # project_root = context.project_root

        # Example: Call LLM (sub-agent)
        # result = await context.call_llm([...])

        # Example: Execute another tool
        # result = await context.execute_tool("read_file", {...})

        # Example: Vector search
        # results = await context.vector_search("query", limit=10)

        # Example: Stream output to UI
        # await context.emit_tool_chunk("Processing...")

        return {
            "success": True,
            "result": {
                "message": f"Tool executed with input: {input_value}",
            },
        }
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
        }
`;
};

onMounted(async () => {
  if (!editorContainer.value) return;

  // Dynamically import Monaco
  try {
    monaco = await import('monaco-editor');
  } catch (error) {
    console.error('Failed to load Monaco editor:', error);
    return;
  }
  
  if (!monaco || !editorContainer.value) return;

  // Ensure we always have a valid tool name and content
  const toolName = (props.toolName && props.toolName.trim()) || 'my_tool';
  const modelValue = props.modelValue ? String(props.modelValue).trim() : '';
  const initialValue = modelValue || getDefaultTemplate(toolName);

  // Ensure initialValue is never empty (safety check)
  const safeInitialValue = initialValue && initialValue.trim() 
    ? initialValue 
    : getDefaultTemplate(toolName);

  try {
    editorInstance = monaco.editor.create(editorContainer.value, {
      value: safeInitialValue,
      language: 'python',
      theme: 'vs',
      automaticLayout: true,
      fontFamily: "'JetBrains Mono', 'Fira Code', 'Cascadia Code', Consolas, monospace",
      fontSize: 14,
      minimap: { enabled: true },
      wordWrap: 'on',
      lineNumbers: 'on',
      scrollBeyondLastLine: false,
    });

    // Listen to content changes
    editorInstance.onDidChangeModelContent(() => {
      if (editorInstance) {
        const content = editorInstance.getValue();
        emit('update:modelValue', content);
      }
    });
  } catch (error) {
    console.error('Failed to create Monaco editor:', error);
  }
});

onUnmounted(() => {
  if (editorInstance) {
    editorInstance.dispose();
    editorInstance = null;
  }
});

watch(
  () => props.modelValue,
  (newValue) => {
    if (editorInstance) {
      const currentValue = editorInstance.getValue();
      const safeNewValue = (newValue && newValue.trim()) || '';
      // Only update if the value actually changed
      if (currentValue !== safeNewValue) {
        const toolName = (props.toolName && props.toolName.trim()) || 'my_tool';
        const valueToSet = safeNewValue || getDefaultTemplate(toolName);
        editorInstance.setValue(valueToSet);
      }
    }
  },
);

watch(
  () => props.toolName,
  (newName) => {
    if (editorInstance) {
      const currentContent = editorInstance.getValue();
      const hasContent = currentContent && currentContent.trim();
      // Only update template if there's no content (empty or just whitespace)
      if (!hasContent) {
        const toolName = (newName && newName.trim()) || 'my_tool';
        editorInstance.setValue(getDefaultTemplate(toolName));
      }
    }
  },
);
</script>

<style scoped>
.monaco-tool-editor-container {
  width: 100%;
}

.tool-interface-hint {
  border: 1px solid rgba(0, 0, 0, 0.12);
  border-bottom: none;
  border-radius: 4px 4px 0 0;
  font-family: 'JetBrains Mono', 'Fira Code', 'Cascadia Code', Consolas, monospace;
  font-size: 11px;
}

.monaco-tool-editor {
  width: 100%;
  border: 1px solid rgba(0, 0, 0, 0.12);
  border-radius: 0 0 4px 4px;
}

pre {
  font-size: 11px;
  line-height: 1.4;
}
</style>
