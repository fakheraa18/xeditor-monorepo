<template>
  <div class="diff-preview">
    <q-expansion-item
      dense
      :default-opened="false"
      header-class="diff-preview-header"
      expand-icon-class="diff-preview-expand-icon"
      @show="onExpansionShow"
      @hide="onExpansionHide"
    >
      <template v-slot:header>
        <div class="row items-center full-width">
          <q-icon :name="changeTypeIcon" size="14px" class="q-mr-xs" :color="changeTypeColor" />
          <span class="diff-file-path">{{ filePath }}</span>
          <q-chip :color="changeTypeColor" text-color="white" size="xs" dense class="q-ml-sm">
            {{ changeTypeLabel }}
          </q-chip>
          <q-space />
          <q-btn
            flat
            dense
            size="sm"
            icon="open_in_new"
            class="diff-open-btn"
            @click.stop="openInEditor"
          >
            <q-tooltip>Open in diff editor</q-tooltip>
          </q-btn>
        </div>
      </template>

      <div class="diff-preview-content">
        <div v-if="changeType === 'deleted'" class="diff-deleted-message">
          <q-icon name="delete" size="16px" class="q-mr-xs" />
          File was deleted
        </div>
        <div v-else-if="changeType === 'created'" class="diff-created-preview">
          <div class="diff-preview-header-text">New file content:</div>
          <pre class="diff-code-preview">{{ afterContent }}</pre>
        </div>
        <div v-else-if="beforeContent && afterContent" ref="diffContainer" class="diff-container" />
        <div v-else class="diff-no-preview">
          <q-icon name="info" size="14px" class="q-mr-xs" />
          Diff preview not available
        </div>
      </div>
    </q-expansion-item>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onUnmounted } from 'vue';
import { useEditorStore } from '../../../../stores/editor';
import type { TraceEventFileChange } from 'src/apps/CodeEditor/core/types';

// Dynamic import for Monaco
// eslint-disable-next-line @typescript-eslint/consistent-type-imports
type MonacoModule = typeof import('monaco-editor');
// eslint-disable-next-line @typescript-eslint/consistent-type-imports
type MonacoDiffEditorType = import('monaco-editor').editor.IStandaloneDiffEditor;
let monaco: MonacoModule | null = null;
let diffEditor: MonacoDiffEditorType | null = null;
let isCreatingEditor = false; // Guard to prevent multiple simultaneous creations

const props = defineProps<{
  fileChange: TraceEventFileChange;
}>();

const editorStore = useEditorStore();
const diffContainer = ref<HTMLElement | null>(null);

const filePath = computed(() => props.fileChange.path);
const changeType = computed(() => props.fileChange.changeType);
const beforeContent = computed(() => props.fileChange.beforeContent);
const afterContent = computed(() => props.fileChange.afterContent);

const changeTypeIcon = computed(() => {
  switch (changeType.value) {
    case 'created':
      return 'add_circle';
    case 'deleted':
      return 'remove_circle';
    default:
      return 'edit';
  }
});

const changeTypeColor = computed(() => {
  switch (changeType.value) {
    case 'created':
      return 'positive';
    case 'deleted':
      return 'negative';
    default:
      return 'primary';
  }
});

const changeTypeLabel = computed(() => {
  switch (changeType.value) {
    case 'created':
      return 'New';
    case 'deleted':
      return 'Deleted';
    default:
      return 'Modified';
  }
});

function getLanguageFromPath(path: string): string {
  const ext = path.split('.').pop()?.toLowerCase();
  const langMap: Record<string, string> = {
    ts: 'typescript',
    tsx: 'typescript',
    js: 'javascript',
    jsx: 'javascript',
    vue: 'vue',
    py: 'python',
    rs: 'rust',
    go: 'go',
    java: 'java',
    cpp: 'cpp',
    c: 'c',
    cs: 'csharp',
    rb: 'ruby',
    php: 'php',
    html: 'html',
    css: 'css',
    scss: 'scss',
    json: 'json',
    yaml: 'yaml',
    yml: 'yaml',
    md: 'markdown',
    sql: 'sql',
    sh: 'shell',
    bash: 'shell',
  };
  return langMap[ext || ''] || 'plaintext';
}

async function createDiffEditor() {
  // Guard: prevent multiple simultaneous creations
  if (isCreatingEditor) {
    return;
  }

  if (!diffContainer.value || !beforeContent.value || !afterContent.value) return;

  // Limit file size to prevent crashes (1MB limit)
  const beforeSize = beforeContent.value?.length || 0;
  const afterSize = afterContent.value?.length || 0;
  const maxSize = 1024 * 1024; // 1MB
  if (beforeSize > maxSize || afterSize > maxSize) {
    console.warn('File too large for diff preview, skipping editor creation');
    return;
  }

  isCreatingEditor = true;

  // Dispose existing editor first if it exists
  const existingEditor: MonacoDiffEditorType | null = diffEditor;
  if (existingEditor) {
    try {
      const models = existingEditor.getModel();
      existingEditor.dispose();
      if (models?.original) {
        models.original.dispose();
      }
      if (models?.modified) {
        models.modified.dispose();
      }
    } catch (_error) {
      // Ignore disposal errors
    }
    diffEditor = null;
  }

  // Load Monaco if not already loaded
  if (!monaco) {
    try {
      monaco = await import('monaco-editor');
    } catch (error) {
      console.error('Failed to load Monaco editor:', error);
      isCreatingEditor = false;
      return;
    }
  }

  const language = getLanguageFromPath(filePath.value);

  // Ensure monaco is loaded
  if (!monaco) return;

  // Create models
  const originalModel = monaco.editor.createModel(beforeContent.value, language);
  const modifiedModel = monaco.editor.createModel(afterContent.value, language);

  // Create diff editor
  diffEditor = monaco.editor.createDiffEditor(diffContainer.value, {
    automaticLayout: true,
    readOnly: true,
    renderSideBySide: false, // Inline view for preview
    enableSplitViewResizing: false,
    originalEditable: false,
    minimap: { enabled: false },
    scrollBeyondLastLine: false,
    fontSize: 12,
    lineNumbers: 'on',
    renderWhitespace: 'selection',
    scrollbar: {
      vertical: 'auto',
      horizontal: 'auto',
    },
  });

  diffEditor.setModel({
    original: originalModel,
    modified: modifiedModel,
  });

  isCreatingEditor = false;
}

function openInEditor() {
  // Dispose inline editor before opening dialog to free memory
  if (diffEditor) {
    try {
      const models = diffEditor.getModel();
      diffEditor.dispose();
      if (models?.original) {
        models.original.dispose();
      }
      if (models?.modified) {
        models.modified.dispose();
      }
    } catch (_error) {
      // Ignore disposal errors
    }
    diffEditor = null;
    isCreatingEditor = false;
  }

  if (beforeContent.value && afterContent.value) {
    editorStore.openDiffTab(filePath.value, beforeContent.value, afterContent.value);
  }
}

function onExpansionShow() {
  // Only create editor when expansion item is actually opened
  if (
    diffContainer.value &&
    beforeContent.value &&
    afterContent.value &&
    changeType.value === 'modified' &&
    !diffEditor &&
    !isCreatingEditor
  ) {
    // Defer to avoid blocking
    requestAnimationFrame(() => {
      void createDiffEditor();
    });
  }
}

function onExpansionHide() {
  // Dispose editor when collapsed to free memory
  if (diffEditor) {
    try {
      const models = diffEditor.getModel();
      diffEditor.dispose();
      if (models?.original) {
        models.original.dispose();
      }
      if (models?.modified) {
        models.modified.dispose();
      }
    } catch (_error) {
      // Ignore disposal errors
    }
    diffEditor = null;
    isCreatingEditor = false;
  }
}

onUnmounted(() => {
  isCreatingEditor = false;
  if (diffEditor) {
    try {
      // Get models before disposing editor
      const models = diffEditor.getModel();
      // Dispose editor first
      diffEditor.dispose();
      // Then dispose models
      if (models?.original) {
        models.original.dispose();
      }
      if (models?.modified) {
        models.modified.dispose();
      }
    } catch (_error) {
      // Ignore disposal errors
    }
    diffEditor = null;
  }
});
</script>

<style scoped>
.diff-preview {
  margin: 8px 0;
  border: 1px solid #e0e0e0;
  border-radius: 6px;
  background: #fafafa;
  overflow: hidden;
}

:deep(.diff-preview-header) {
  padding: 8px 12px !important;
  min-height: unset !important;
  background: #ffffff;
  border-bottom: 1px solid #e0e0e0;
}

.diff-file-path {
  font-family: 'JetBrains Mono', 'Fira Code', Consolas, monospace;
  font-size: 12px;
  color: #424242;
  font-weight: 500;
}

.diff-open-btn {
  opacity: 0.6;
  transition: opacity 0.2s;
}

.diff-open-btn:hover {
  opacity: 1;
}

.diff-preview-content {
  padding: 12px;
  background: #ffffff;
}

.diff-deleted-message {
  display: flex;
  align-items: center;
  color: #d32f2f;
  font-size: 13px;
  padding: 8px;
  background: #ffebee;
  border-radius: 4px;
}

.diff-created-preview {
  padding: 8px;
}

.diff-preview-header-text {
  font-size: 11px;
  font-weight: 600;
  text-transform: uppercase;
  color: #616161;
  margin-bottom: 8px;
  letter-spacing: 0.5px;
}

.diff-code-preview {
  font-family: 'JetBrains Mono', 'Fira Code', Consolas, monospace;
  font-size: 11px;
  color: #333333;
  white-space: pre-wrap;
  word-break: break-word;
  margin: 0;
  padding: 8px;
  background: #f5f5f5;
  border-radius: 4px;
  max-height: 300px;
  overflow-y: auto;
  border: 1px solid #e0e0e0;
}

.diff-container {
  height: 300px;
  min-height: 200px;
  border: 1px solid #e0e0e0;
  border-radius: 4px;
  overflow: hidden;
}

.diff-no-preview {
  display: flex;
  align-items: center;
  color: #757575;
  font-size: 12px;
  padding: 8px;
  font-style: italic;
}

:deep(.monaco-diff-editor) {
  height: 100%;
}

:deep(.monaco-editor .margin-view-overlays .line-numbers) {
  font-size: 11px;
}
</style>
