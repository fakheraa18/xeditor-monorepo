<template>
  <div ref="editorContainer" class="monaco-parser-editor" :style="{ height: height }"></div>
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
  modelValue: string;
  family?: string;
  mode?: string;
  height?: string;
}

const props = withDefaults(defineProps<Props>(), {
  height: '400px',
});

const emit = defineEmits<{
  'update:modelValue': [value: string];
}>();

const editorContainer = ref<HTMLDivElement | null>(null);
let editorInstance: MonacoEditorType | null = null;

const getDefaultTemplate = (family: string = 'default', mode: string = 'agent') => {
  const Family = family.charAt(0).toUpperCase() + family.slice(1);
  const Mode = mode.charAt(0).toUpperCase() + mode.slice(1);

  return `"""Parser for ${family} ${mode} mode responses"""

from parsers.base import ResponseParser, ParsedResponse
import re
import json

class ${Family}${Mode}Parser(ResponseParser):
    """Parser for ${family} ${mode} mode."""

    family = "${family}"

    def parse(self, content: str) -> ParsedResponse:
        """Parse the response content."""
        # Extract thinking/reasoning
        thinking = None
        think_match = re.search(r'<think>([\\s\\S]*?)</think>', content, re.IGNORECASE)
        if think_match:
            thinking = think_match.group(1).strip()

        # Extract tool calls
        tool_call = None
        tool_match = re.search(r'<tool_code>([\\s\\S]*?)</tool_code>', content, re.IGNORECASE)
        if tool_match:
            try:
                parsed = json.loads(tool_match.group(1).strip())
                if isinstance(parsed, dict) and "tool" in parsed and "args" in parsed:
                    tool_call = {
                        "tool": parsed["tool"],
                        "args": parsed["args"],
                    }
            except (json.JSONDecodeError, KeyError):
                pass

        # Final text is content with tags stripped
        final_text = self.strip_tags(content)

        return ParsedResponse(
            thinking=thinking,
            tool_call=tool_call,
            final_text=final_text,
        )

    def strip_tags(self, content: str) -> str:
        """Strip internal tags from content."""
        result = content
        result = re.sub(r'<think>[\\s\\S]*?</think>', '', result, flags=re.IGNORECASE)
        result = re.sub(r'<tool_code>[\\s\\S]*?</tool_code>', '', result, flags=re.IGNORECASE)
        return result.strip()

parser = ${Family}${Mode}Parser()
`;
};

onMounted(async () => {
  if (!editorContainer.value) return;

  // Dynamically import Monaco
  monaco = await import('monaco-editor');
  if (!monaco || !editorContainer.value) return;

  const initialValue = props.modelValue || getDefaultTemplate(props.family, props.mode);

  editorInstance = monaco.editor.create(editorContainer.value, {
    value: initialValue,
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
    if (editorInstance && editorInstance.getValue() !== newValue) {
      editorInstance.setValue(newValue || getDefaultTemplate(props.family, props.mode));
    }
  },
);
</script>

<style scoped>
.monaco-parser-editor {
  width: 100%;
  border: 1px solid rgba(0, 0, 0, 0.12);
  border-radius: 4px;
}
</style>
