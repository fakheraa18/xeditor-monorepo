<template>
  <q-dialog ref="dialogRef" maximized @show="onDialogShow" @hide="handleDialogHide">
    <q-card class="column fit">
      <q-card-section class="row items-center q-pb-none">
        <q-icon name="compare_arrows" size="24px" class="q-mr-sm" />
        <div class="text-h6">File Changes</div>
        <q-space />
        <div v-if="filePath" class="text-caption text-grey-6 q-mr-md">
          {{ filePath }}
        </div>
        <q-btn icon="close" flat round dense @click="closeDialog" />
      </q-card-section>

      <q-card-section class="row items-center q-pt-sm q-pb-none">
        <q-chip
          :color="changeType === 'created' ? 'positive' : changeType === 'deleted' ? 'negative' : 'primary'"
          text-color="white"
          :icon="changeTypeIcon"
          size="sm"
        >
          {{ changeTypeLabel }}
        </q-chip>
        <q-space />
        <q-btn-group flat>
          <q-btn
            flat
            :color="viewMode === 'split' ? 'primary' : 'grey'"
            icon="view_column"
            size="sm"
            @click="viewMode = 'split'"
          >
            <q-tooltip>Side by Side</q-tooltip>
          </q-btn>
          <q-btn
            flat
            :color="viewMode === 'inline' ? 'primary' : 'grey'"
            icon="view_stream"
            size="sm"
            @click="viewMode = 'inline'"
          >
            <q-tooltip>Inline</q-tooltip>
          </q-btn>
        </q-btn-group>
      </q-card-section>

      <q-card-section class="col q-pa-none" style="min-height: 0;">
        <div ref="diffEditorContainer" class="fit" />
      </q-card-section>

      <q-separator />

      <q-card-actions align="right">
        <q-btn flat label="Close" color="grey-7" @click="closeDialog" />
        <q-btn
          v-if="!alreadyExecuted && changeType !== 'deleted'"
          label="Accept Changes"
          color="positive"
          @click="acceptChanges"
        />
        <q-btn
          v-if="!alreadyExecuted && changeType !== 'created' && changeType !== 'deleted'"
          label="Revert"
          color="negative"
          @click="revertChanges"
        />
      </q-card-actions>
    </q-card>
  </q-dialog>
</template>

<script setup lang="ts">
import { ref, computed, watch, onUnmounted, nextTick } from 'vue';
import { useDialogPluginComponent } from 'quasar';

// Dynamic import for Monaco to avoid blocking
// eslint-disable-next-line @typescript-eslint/consistent-type-imports
type MonacoModule = typeof import('monaco-editor');
let monaco: MonacoModule | null = null;

type ChangeType = 'created' | 'modified' | 'deleted';
type ViewMode = 'split' | 'inline';

const props = withDefaults(
  defineProps<{
    modelValue?: boolean;
    filePath?: string;
    originalContent?: string;
    modifiedContent?: string;
    changeType?: ChangeType;
    language?: string;
    alreadyExecuted?: boolean;
  }>(),
  {
    alreadyExecuted: true,
  },
);

defineEmits([...useDialogPluginComponent.emits]);

const { dialogRef, onDialogHide, onDialogOK, onDialogCancel } = useDialogPluginComponent();

const diffEditorContainer = ref<HTMLElement | null>(null);
const viewMode = ref<ViewMode>('split');
// eslint-disable-next-line @typescript-eslint/consistent-type-imports
let diffEditor: import('monaco-editor').editor.IStandaloneDiffEditor | null = null;
let isCreatingEditor = false; // Guard to prevent multiple simultaneous creations

const changeTypeIcon = computed(() => {
  switch (props.changeType) {
    case 'created':
      return 'add_circle';
    case 'deleted':
      return 'remove_circle';
    default:
      return 'edit';
  }
});

const changeTypeLabel = computed(() => {
  switch (props.changeType) {
    case 'created':
      return 'New File';
    case 'deleted':
      return 'Deleted';
    default:
      return 'Modified';
  }
});

async function createDiffEditor() {
  // Guard: prevent multiple simultaneous creations
  if (isCreatingEditor) {
    return;
  }

  // Dispose existing editor before creating a new one
  const existingEditor = diffEditor;
  if (existingEditor) {
    try {
      existingEditor.dispose();
    } catch (error) {
      console.warn('Error disposing existing editor:', error);
    }
    diffEditor = null;
  }

  if (!diffEditorContainer.value) return;

  // Limit file size to prevent crashes (1MB limit)
  const originalSize = props.originalContent?.length || 0;
  const modifiedSize = props.modifiedContent?.length || 0;
  const maxSize = 1024 * 1024; // 1MB
  if (originalSize > maxSize || modifiedSize > maxSize) {
    console.warn('File too large for diff view, skipping editor creation');
    return;
  }

  isCreatingEditor = true;

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

  // Ensure monaco is loaded
  if (!monaco) {
    isCreatingEditor = false;
    return;
  }

  // Capture monaco in a const to help TypeScript narrowing
  const monacoEditor = monaco;

  // Determine language from file path or use provided language
  let language = props.language || 'plaintext';
  if (props.filePath) {
    const ext = props.filePath.split('.').pop()?.toLowerCase();
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
    language = langMap[ext || ''] || 'plaintext';
  }

  // Create models
  const originalModel = monacoEditor.editor.createModel(
    props.originalContent || '',
    language,
  );

  const modifiedModel = monacoEditor.editor.createModel(
    props.modifiedContent || '',
    language,
  );

  // Create diff editor
  diffEditor = monacoEditor.editor.createDiffEditor(diffEditorContainer.value, {
    automaticLayout: true,
    readOnly: true,
    renderSideBySide: viewMode.value === 'split',
    enableSplitViewResizing: true,
    originalEditable: false,
    minimap: { enabled: false },
    scrollBeyondLastLine: false,
    fontSize: 13,
    lineNumbers: 'on',
    renderWhitespace: 'selection',
  });

  diffEditor.setModel({
    original: originalModel,
    modified: modifiedModel,
  });

  isCreatingEditor = false;
}

function updateViewMode() {
  if (diffEditor) {
    diffEditor.updateOptions({
      renderSideBySide: viewMode.value === 'split',
    });
  }
}

function acceptChanges() {
  onDialogOK();
}

function revertChanges() {
  onDialogCancel();
}

function closeDialog() {
  onDialogCancel();
}

async function onDialogShow() {
  // Dispose any existing editor first
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

  // Wait for DOM to be ready - use multiple ticks to ensure dialog is fully rendered
  await nextTick();
  await nextTick();
  await nextTick();

  // Check if container is visible before creating editor
  if (!diffEditorContainer.value) {
    setTimeout(() => {
      void onDialogShow();
    }, 50);
    return;
  }

  // Use setTimeout to give browser time to render dialog
  setTimeout(() => {
    if (!isCreatingEditor && !diffEditor && diffEditorContainer.value) {
      // Check container is actually visible
      const rect = diffEditorContainer.value.getBoundingClientRect();
      if (rect.width > 0 && rect.height > 0) {
        void createDiffEditor();
      } else {
        setTimeout(() => {
          void onDialogShow();
        }, 50);
      }
    }
  }, 150);
}

function handleDialogHide() {
  // Dispose when dialog closes
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
  // Call Quasar's onDialogHide to properly clean up
  onDialogHide();
}

watch(viewMode, () => {
  updateViewMode();
});

watch(
  () => [props.originalContent, props.modifiedContent, props.filePath],
  () => {
    // Editor creation is handled by @show event
    if (!isCreatingEditor && !diffEditor && diffEditorContainer.value) {
      // Defer to avoid blocking
      requestAnimationFrame(() => {
        requestAnimationFrame(() => {
          if (!isCreatingEditor && !diffEditor && diffEditorContainer.value) {
            void createDiffEditor();
          }
        });
      });
    }
  },
);

// Note: Editor creation is handled by @show event, not onMounted

onUnmounted(() => {
  isCreatingEditor = false;
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
    } catch (error) {
      console.warn('Error disposing diff editor:', error);
    }
    diffEditor = null;
  }
});
</script>

<style scoped>
/* Ensure the diff editor fills the container */
:deep(.monaco-diff-editor) {
  height: 100%;
}
</style>
