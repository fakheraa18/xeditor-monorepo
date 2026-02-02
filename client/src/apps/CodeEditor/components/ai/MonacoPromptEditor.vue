<template>
  <div ref="editorContainer" class="monaco-prompt-editor" :style="{ height: height }"></div>
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

const defaultTemplate = `"""System prompt for {mode} mode"""

SYSTEM_PROMPT = """You are an AI assistant.
"""

PARAMETERS = {
    "temperature": 0.7,
    "maxTokens": 2000,
}
`;

onMounted(async () => {
  if (!editorContainer.value) return;

  // Dynamically import Monaco
  monaco = await import('monaco-editor');
  if (!monaco || !editorContainer.value) return;

  const initialValue = props.modelValue || defaultTemplate;

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
      editorInstance.setValue(newValue || defaultTemplate);
    }
  }
);
</script>

<style scoped>
.monaco-prompt-editor {
  width: 100%;
  border: 1px solid rgba(0, 0, 0, 0.12);
  border-radius: 4px;
}
</style>
