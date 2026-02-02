import { defineStore } from 'pinia';
import { ref, computed, watch } from 'vue';
import { useQuasar } from 'quasar';
import type { EditorTab } from '../core/types';
import { useProjectStore } from './project';
import SaveChangesDialog, {
  type SaveChangesAction,
} from 'src/apps/CodeEditor/components/editor/SaveChangesDialog.vue';
import DiffView from 'src/apps/CodeEditor/components/editor/DiffView.vue';
import { isPreviewable, getFileExtension } from '../config/previewable';

export const useEditorStore = defineStore('editor', () => {
  const $q = useQuasar();
  const tabs = ref<EditorTab[]>([]);
  const activeTabId = ref<string | null>(null);
  const cursorPosition = ref<{ line: number; column: number } | null>(null);
  const selectedText = ref<string>('');
  const isDiffDialogOpen = ref(false); // Guard to prevent multiple diff dialogs

  const activeTab = computed(() => {
    if (!activeTabId.value) return null;
    return tabs.value.find((tab) => tab.id === activeTabId.value) || null;
  });

  const hasUnsavedChanges = computed(() => {
    return tabs.value.some((tab) => tab.isDirty);
  });

  async function openFile(filePath: string) {
    // Check if file is already open
    const existingTab = tabs.value.find((tab) => tab.filePath === filePath);
    if (existingTab) {
      activeTabId.value = existingTab.id;
      return existingTab.id;
    }

    // Read file content using editor I/O (full content, no chunking)
    const projectStore = useProjectStore();
    const content = await projectStore.readFileForEditor(filePath);

    // Determine language from extension
    const extension = filePath.split('.').pop()?.toLowerCase();
    const languageMap: Record<string, string> = {
      ts: 'typescript',
      tsx: 'typescript',
      js: 'javascript',
      jsx: 'javascript',
      vue: 'html', // Use HTML highlighting for Vue files as Monaco doesn't have native Vue support
      py: 'python',
      rs: 'rust',
      go: 'go',
      java: 'java',
      cpp: 'cpp',
      c: 'c',
      json: 'json',
      yaml: 'yaml',
      yml: 'yaml',
      md: 'markdown',
      html: 'html',
      css: 'css',
      scss: 'scss',
      sql: 'sql',
      sh: 'shell',
      xml: 'xml',
      svg: 'xml',
    };

    const language = languageMap[extension || ''] || 'plaintext';

    // Determine initial view mode: preview for previewable files, code otherwise
    const fileExtension = getFileExtension(filePath);
    const initialViewMode: 'code' | 'preview' = isPreviewable(fileExtension) ? 'preview' : 'code';

    const tab: EditorTab = {
      id: `tab-${Date.now()}-${Math.random()}`,
      filePath,
      fileName: filePath.split('/').pop() || filePath,
      content,
      originalContent: content,
      isDirty: false,
      language,
      viewMode: initialViewMode,
    };

    tabs.value.push(tab);
    activeTabId.value = tab.id;

    return tab.id;
  }

  function closeTab(tabId: string) {
    const index = tabs.value.findIndex((tab) => tab.id === tabId);
    if (index === -1) return;

    tabs.value.splice(index, 1);

    // If closed tab was active, switch to another tab
    if (activeTabId.value === tabId) {
      if (tabs.value.length > 0) {
        const nextTab = tabs.value[Math.max(0, index - 1)];
        if (nextTab) {
          activeTabId.value = nextTab.id;
        } else {
          activeTabId.value = null;
        }
      } else {
        activeTabId.value = null;
      }
    }
  }

  async function closeTabWithPrompt(tabId: string): Promise<void> {
    const tab = tabs.value.find((t) => t.id === tabId);
    if (!tab) return;

    // If tab has no unsaved changes, close immediately
    if (!tab.isDirty) {
      closeTab(tabId);
      return;
    }

    // Show a 3-button dialog: Don't Save & Close / Save & Close / Cancel
    return new Promise<void>((resolve) => {
      $q.dialog({
        component: SaveChangesDialog,
        componentProps: {
          fileName: tab.fileName,
        },
        persistent: true,
      })
        .onOk((action: SaveChangesAction) => {
          void (async () => {
            if (action === 'save') {
              await saveTab(tabId);
              closeTab(tabId);
            } else if (action === 'discard') {
              closeTab(tabId);
            }
            resolve();
          })();
        })
        .onCancel(() => {
          resolve();
        });
    });
  }

  function updateTabContent(tabId: string, content: string) {
    const tab = tabs.value.find((t) => t.id === tabId);
    if (tab) {
      tab.content = content;
      // Mark as dirty only if content differs from original
      tab.isDirty = tab.content !== tab.originalContent;
    }
  }

  async function saveTab(tabId: string) {
    const tab = tabs.value.find((t) => t.id === tabId);
    if (!tab || !tab.isDirty) return;

    const projectStore = useProjectStore();
    await projectStore.writeFileForEditor(tab.filePath, tab.content);
    tab.originalContent = tab.content;
    tab.isDirty = false;

    // Companion handles file watching and incremental indexing automatically
    // No need to manually trigger index update - companion detects file changes server-side
  }

  async function saveAllTabs() {
    await Promise.all(tabs.value.filter((t) => t.isDirty).map((t) => saveTab(t.id)));
  }

  function setActiveTab(tabId: string) {
    if (tabs.value.some((tab) => tab.id === tabId)) {
      activeTabId.value = tabId;
    }
  }

  function setCursorPosition(line: number, column: number) {
    cursorPosition.value = { line, column };
  }

  function setSelectedText(text: string) {
    selectedText.value = text;
  }

  function toggleViewMode(tabId: string) {
    const tab = tabs.value.find((t) => t.id === tabId);
    if (tab) {
      tab.viewMode = tab.viewMode === 'preview' ? 'code' : 'preview';
    }
  }

  function openDiffTab(
    filePath: string,
    beforeContent: string,
    afterContent: string,
    changeType: 'created' | 'modified' | 'deleted' = 'modified',
  ) {
    // Guard: prevent multiple dialogs
    if (isDiffDialogOpen.value) {
      return;
    }

    // Determine language from extension
    const extension = filePath.split('.').pop()?.toLowerCase();
    const languageMap: Record<string, string> = {
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

    const language = languageMap[extension || ''] || 'plaintext';

    isDiffDialogOpen.value = true;

    // Open DiffView dialog (full-screen diff view)
    // Use persistent: false to ensure proper cleanup
    $q.dialog({
      component: DiffView,
      componentProps: {
        modelValue: true,
        filePath,
        originalContent: beforeContent,
        modifiedContent: afterContent,
        changeType,
        language,
        alreadyExecuted: true, // All LLM tool file changes are already executed
      },
      persistent: false, // Allow closing with ESC/click outside
    })
      .onOk(() => {
        isDiffDialogOpen.value = false;
      })
      .onCancel(() => {
        isDiffDialogOpen.value = false;
      })
      .onDismiss(() => {
        isDiffDialogOpen.value = false;
      });

    // Return a placeholder ID (dialog doesn't create a tab)
    return `diff-dialog-${Date.now()}`;
  }

  async function openGitDiff(workspacePath: string, ref: string = 'HEAD'): Promise<void> {
    const projectStore = useProjectStore();

    try {
      // Get current working tree content
      const workingContent = await projectStore.readFileForEditor(workspacePath);

      // Get HEAD content
      const gitResult = await projectStore.getGitHeadContent(workspacePath, ref);

      if (!gitResult.existsInRef) {
        // File doesn't exist in HEAD, treat as new file
        openDiffTab(workspacePath, '', workingContent, 'created');
        return;
      }

      // Compare HEAD vs working tree
      const changeType: 'created' | 'modified' | 'deleted' =
        workingContent === gitResult.baseContent ? 'modified' : 'modified';

      openDiffTab(workspacePath, gitResult.baseContent, workingContent, changeType);
    } catch (error) {
      $q.notify({
        type: 'negative',
        message: 'Failed to show git diff',
        caption: error instanceof Error ? error.message : 'Unknown error',
        position: 'top',
        timeout: 5000,
      });
    }
  }

  function reset() {
    tabs.value = [];
    activeTabId.value = null;
    cursorPosition.value = null;
    selectedText.value = '';
  }

  // ─────────────────────────────────────────────────────────────────────────────
  // Persistence
  // ─────────────────────────────────────────────────────────────────────────────

  function saveState() {
    const activeTab = tabs.value.find((t) => t.id === activeTabId.value);
    const state = {
      openFiles: tabs.value.map((t) => t.filePath),
      activeFilePath: activeTab ? activeTab.filePath : null,
    };
    localStorage.setItem('xeditor-editor-state', JSON.stringify(state));
  }

  async function restoreState() {
    try {
      const stored = localStorage.getItem('xeditor-editor-state');
      if (!stored) return;

      const state = JSON.parse(stored);
      if (state.openFiles && Array.isArray(state.openFiles)) {
        // Clear existing tabs first to avoid duplicates
        tabs.value = [];
        activeTabId.value = null;

        // Restore opened files
        // Errors are caught individually so one failure doesn't stop others
        for (const filePath of state.openFiles) {
          try {
            await openFile(filePath);
          } catch (_e) {
            // Silently skip files that can't be opened (e.g., no active project, file deleted, etc.)
            // This prevents console errors on page reload when project isn't ready yet
            // The file will simply not be restored, which is acceptable
          }
        }

        // Restore active tab
        if (state.activeFilePath) {
          const tab = tabs.value.find((t) => t.filePath === state.activeFilePath);
          if (tab) {
            activeTabId.value = tab.id;
          }
        }
      }
    } catch (e) {
      console.warn('Failed to restore editor state', e);
    }
  }

  // Auto-save state on changes
  watch(
    [tabs, activeTabId],
    () => {
      saveState();
    },
    { deep: true },
  );

  // ─────────────────────────────────────────────────────────────────────────────
  // External File Change Handling
  // ─────────────────────────────────────────────────────────────────────────────

  async function handleExternalFileChanged(
    filePath: string,
    changeType: 'created' | 'modified' | 'deleted',
    isAbsolute: boolean = false,
  ): Promise<void> {
    // Find any open tab with matching file path
    const tab = tabs.value.find((t) => t.filePath === filePath);
    if (!tab) {
      // File not open, nothing to do
      return;
    }

    // Handle deleted files
    if (changeType === 'deleted') {
      if (!tab.isDirty) {
        // Clean tab - close it automatically
        closeTab(tab.id);
        $q.notify({
          type: 'warning',
          message: `File deleted: ${tab.fileName}`,
          position: 'top',
          timeout: 3000,
        });
      } else {
        // Dirty tab - warn user but don't close
        $q.notify({
          type: 'warning',
          message: `File deleted on disk: ${tab.fileName}`,
          caption: 'You have unsaved changes. Save or discard them before closing.',
          position: 'top',
          timeout: 5000,
        });
      }
      return;
    }

    // Handle created/modified files
    if (tab.isDirty) {
      // Tab has unsaved changes - notify user but don't overwrite
      $q.notify({
        type: 'info',
        message: `File changed on disk: ${tab.fileName}`,
        caption: 'You have unsaved changes. Reload to discard your edits?',
        position: 'top',
        timeout: 5000,
        actions: [
          {
            label: 'Reload',
            color: 'white',
            handler: () => {
              void reloadTabFromDisk(tab.id, filePath, isAbsolute);
            },
          },
        ],
      });
      return;
    }

    // Tab is clean - auto-reload from disk
    await reloadTabFromDisk(tab.id, filePath, isAbsolute);
  }

  async function reloadTabFromDisk(
    tabId: string,
    filePath: string,
    isAbsolute: boolean,
  ): Promise<void> {
    const tab = tabs.value.find((t) => t.id === tabId);
    if (!tab) return;

    try {
      let content: string;

      const projectStore = useProjectStore();
      if (isAbsolute) {
        // Read absolute path using editor I/O (full content, no chunking)
        content = await projectStore.readAbsoluteFileForEditor(filePath);
      } else {
        // Read workspace path using editor I/O (full content, no chunking)
        content = await projectStore.readFileForEditor(filePath);
      }

      // Update tab content and reset dirty state
      tab.content = content;
      tab.originalContent = content;
      tab.isDirty = false;
    } catch (error) {
      console.error('Failed to reload tab from disk:', error);
      $q.notify({
        type: 'negative',
        message: `Failed to reload file: ${tab.fileName}`,
        caption: error instanceof Error ? error.message : 'Unknown error',
        position: 'top',
        timeout: 5000,
      });
    }
  }

  return {
    tabs,
    activeTabId,
    activeTab,
    cursorPosition,
    selectedText,
    hasUnsavedChanges,
    openFile,
    closeTab,
    closeTabWithPrompt,
    updateTabContent,
    saveTab,
    saveAllTabs,
    setActiveTab,
    setCursorPosition,
    setSelectedText,
    toggleViewMode,
    openDiffTab,
    openGitDiff,
    reset,
    restoreState,
    handleExternalFileChanged,
  };
});
