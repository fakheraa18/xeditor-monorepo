<template>
  <div ref="editorContainer" class="monaco-editor-container fit"></div>
</template>

<script setup lang="ts">
import { ref, onMounted, onUnmounted, watch } from 'vue';
import { useEditorStore } from '../../stores/editor';

// Dynamic import for Monaco
// eslint-disable-next-line @typescript-eslint/consistent-type-imports
type MonacoEditorType = import('monaco-editor').editor.IStandaloneCodeEditor;
// eslint-disable-next-line @typescript-eslint/consistent-type-imports
type MonacoTextModel = import('monaco-editor').editor.ITextModel;
// eslint-disable-next-line @typescript-eslint/consistent-type-imports
type MonacoModule = typeof import('monaco-editor');
let monaco: MonacoModule | null = null;

interface Props {
  tabId: string | null;
}

const props = defineProps<Props>();

const editorStore = useEditorStore();
const editorContainer = ref<HTMLDivElement | null>(null);
let editorInstance: MonacoEditorType | null = null;
let currentModel: MonacoTextModel | null = null;
let isDisposing = false;

/**
 * Handle unhandled promise rejections from Monaco Editor
 * These are expected when async operations are canceled during model switching
 */
function setupMonacoErrorHandler(): void {
  const originalHandler = window.onunhandledrejection;
  window.addEventListener('unhandledrejection', (event: PromiseRejectionEvent) => {
    const reason = event.reason;
    // Suppress Monaco Editor cancellation errors
    if (reason && typeof reason === 'object' && ('message' in reason || 'name' in reason)) {
      const message = String(reason.message || reason.name || '');
      if (message.includes('Canceled') || message === 'Canceled') {
        event.preventDefault();
        return;
      }
    }
    // Call original handler if it exists
    if (originalHandler) {
      originalHandler.call(window, event);
    }
  });
}

/**
 * Safely dispose of Monaco model, catching cancellation errors
 */
function safeDisposeModel(model: MonacoTextModel | null): void {
  if (!model || isDisposing) return;
  try {
    model.dispose();
  } catch (error) {
    // Ignore cancellation errors during disposal - they're expected
    if (error && typeof error === 'object' && 'message' in error) {
      const errorMessage = String(error.message);
      if (!errorMessage.includes('Canceled') && !errorMessage.includes('disposed')) {
        console.warn('Error disposing Monaco model:', error);
      }
    }
  }
}

/**
 * Safely dispose of Monaco editor instance, catching cancellation errors
 */
function safeDisposeEditor(editor: MonacoEditorType | null): void {
  if (!editor || isDisposing) return;
  try {
    editor.dispose();
  } catch (error) {
    // Ignore cancellation errors during disposal - they're expected
    if (error && typeof error === 'object' && 'message' in error) {
      const errorMessage = String(error.message);
      if (!errorMessage.includes('Canceled') && !errorMessage.includes('disposed')) {
        console.warn('Error disposing Monaco editor:', error);
      }
    }
  }
}

/**
 * Update the editor model based on the active tab
 */
function updateEditorModel(tabId: string | null): void {
  if (!editorInstance || !tabId || !monaco || isDisposing) {
    if (editorInstance && !tabId) {
      editorInstance.setValue('');
    }
    return;
  }

  const tab = editorStore.tabs.find((t) => t.id === tabId);
  if (!tab) return;

  // Dispose of the previous model if it exists
  safeDisposeModel(currentModel);
  currentModel = null;

  // Create new model
  currentModel = monaco.editor.createModel(tab.content, tab.language || 'plaintext');

  // Set model with error handling - wrap in setTimeout to allow previous operations to settle
  setTimeout(() => {
    if (editorInstance && currentModel && monaco && !isDisposing) {
      try {
        editorInstance.setModel(currentModel);
        // Update language
        monaco.editor.setModelLanguage(currentModel, tab.language || 'plaintext');
      } catch (error) {
        // Suppress cancellation errors during model switching
        if (error && typeof error === 'object' && 'message' in error) {
          const errorMessage = String(error.message);
          if (!errorMessage.includes('Canceled') && !errorMessage.includes('disposed')) {
            console.warn('Error setting Monaco model:', error);
          }
        }
      }
    }
  }, 0);
}

onMounted(async () => {
  if (!editorContainer.value) return;

  // Setup error handler for Monaco cancellation errors
  setupMonacoErrorHandler();

  // Dynamically import Monaco
  monaco = await import('monaco-editor');
  if (!monaco || !editorContainer.value) return;

  editorInstance = monaco.editor.create(editorContainer.value, {
    value: '',
    language: 'typescript',
    theme: 'vs',
    automaticLayout: true,

    // Font settings for better readability
    fontFamily:
      "'JetBrains Mono', 'Fira Code', 'Cascadia Code', Consolas, 'Courier New', monospace",
    fontSize: 14,
    fontLigatures: true,
    fontWeight: '400',
    letterSpacing: 0.5,

    // Minimap configuration
    minimap: {
      enabled: true,
      renderCharacters: false,
      showSlider: 'mouseover',
      maxColumn: 80,
      scale: 1,
    },

    // Scrolling behavior
    scrollBeyondLastLine: false,
    smoothScrolling: true,
    mouseWheelScrollSensitivity: 1,
    fastScrollSensitivity: 5,

    // Cursor and selection
    cursorBlinking: 'smooth',
    cursorSmoothCaretAnimation: 'on',
    cursorStyle: 'line',
    cursorWidth: 2,

    // Line settings
    renderLineHighlight: 'all',
    renderLineHighlightOnlyWhenFocus: false,
    lineNumbers: 'on',
    lineNumbersMinChars: 4,
    lineDecorationsWidth: 10,

    // Bracket matching
    bracketPairColorization: { enabled: true },
    matchBrackets: 'always',

    // Editor padding
    padding: { top: 12, bottom: 12 },

    // Word wrap
    wordWrap: 'on',
    wordWrapColumn: 120,

    // Whitespace and formatting
    renderWhitespace: 'selection',
    renderControlCharacters: false,

    // Indentation guides
    guides: {
      indentation: true,
      bracketPairs: true,
      highlightActiveBracketPair: true,
      highlightActiveIndentation: true,
    },

    // Suggestions and hover
    quickSuggestions: true,
    suggestOnTriggerCharacters: true,
    hover: { enabled: true, delay: 300 },

    // Scrollbar styling
    scrollbar: {
      vertical: 'auto',
      horizontal: 'auto',
      verticalScrollbarSize: 12,
      horizontalScrollbarSize: 12,
      useShadows: false,
      verticalSliderSize: 12,
      horizontalSliderSize: 12,
    },

    // Performance
    formatOnPaste: false,
    formatOnType: false,

    // Folding
    folding: true,
    foldingStrategy: 'auto',
    showFoldingControls: 'mouseover',

    // Find widget
    find: {
      addExtraSpaceOnTop: false,
      autoFindInSelection: 'multiline',
      seedSearchStringFromSelection: 'selection',
    },
  });

  // Listen to cursor position changes
  editorInstance.onDidChangeCursorPosition((e) => {
    editorStore.setCursorPosition(e.position.lineNumber, e.position.column);
  });

  // Listen to selection changes
  editorInstance.onDidChangeCursorSelection((e) => {
    const selectedText = editorInstance?.getModel()?.getValueInRange(e.selection) || '';
    editorStore.setSelectedText(selectedText);
  });

  // Listen to content changes
  editorInstance.onDidChangeModelContent(() => {
    if (props.tabId && editorInstance) {
      const content = editorInstance.getValue();
      editorStore.updateTabContent(props.tabId, content);
    }
  });

  // Load the model if there's an active tab (fixes blank editor on back navigation)
  if (props.tabId) {
    updateEditorModel(props.tabId);
  }
});

onUnmounted(() => {
  isDisposing = true;

  // Dispose model first, then editor
  // Add small delay to allow async operations to complete
  setTimeout(() => {
    safeDisposeModel(currentModel);
    currentModel = null;

    safeDisposeEditor(editorInstance);
    editorInstance = null;
  }, 0);
});

watch(
  () => props.tabId,
  (newTabId) => {
    updateEditorModel(newTabId);
  },
  { immediate: true },
);

watch(
  () => editorStore.activeTab?.content,
  (newContent) => {
    if (!editorInstance || !props.tabId) return;
    const currentValue = editorInstance.getValue();
    if (currentValue !== newContent) {
      editorInstance.setValue(newContent || '');
    }
  },
);
</script>

<style scoped>
.monaco-editor-container {
  background-color: #ffffff;
}

/* Override Monaco's default selection colors for better visibility */
:deep(.monaco-editor .selected-text) {
  background-color: rgba(173, 214, 255, 0.5) !important;
}

/* Better scrollbar styling */
:deep(.monaco-editor .scrollbar) {
  background-color: transparent !important;
}

:deep(.monaco-editor .slider) {
  background-color: rgba(100, 100, 100, 0.3) !important;
  border-radius: 6px !important;
}

:deep(.monaco-editor .slider:hover) {
  background-color: rgba(100, 100, 100, 0.5) !important;
}

/* Line number styling */
:deep(.monaco-editor .line-numbers) {
  color: #999999 !important;
}

:deep(.monaco-editor .current-line ~ .line-numbers) {
  color: #1976d2 !important;
}

/* Minimap styling */
:deep(.monaco-editor .minimap) {
  background-color: #fafafa;
}

/* Active line highlight */
:deep(.monaco-editor .view-overlays .current-line) {
  background-color: rgba(25, 118, 210, 0.04) !important;
  border: none !important;
}

/* Cursor line number highlight */
:deep(.monaco-editor .margin-view-overlays .current-line-margin) {
  background-color: rgba(25, 118, 210, 0.04) !important;
}
</style>
