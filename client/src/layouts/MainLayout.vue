<template>
  <q-layout view="hHh lpR fFf" class="main-layout">
    <!-- Header -->
    <q-header class="app-header">
      <div class="header-content row items-center no-wrap">
        <!-- Logo & Title -->
        <router-link to="/" class="header-brand row items-center no-wrap">
          <q-icon name="code" size="20px" class="brand-icon" />
          <span class="brand-title">XEditor</span>
        </router-link>

        <q-space />

        <!-- Header Actions -->
        <div class="header-actions row items-center no-wrap">
          <!-- Toggle Explorer -->
          <q-btn
            flat
            round
            dense
            size="sm"
            icon="folder_open"
            :class="['header-btn', { 'header-btn-active': showExplorer }]"
            @click="toggleExplorer"
          >
            <q-tooltip :delay="300">Toggle Explorer (Ctrl+B)</q-tooltip>
          </q-btn>
          <!-- Toggle AI Panel -->
          <q-btn
            flat
            round
            dense
            size="sm"
            icon="smart_toy"
            :class="['header-btn', { 'header-btn-active': showAIPanel }]"
            @click="toggleAIPanel"
          >
            <q-tooltip :delay="300">Toggle AI Panel (Ctrl+L)</q-tooltip>
          </q-btn>
          <q-separator vertical class="header-separator" />
          <!-- Index Explorer -->
          <q-btn
            flat
            round
            dense
            size="sm"
            :icon="statusIcon"
            :class="['header-btn', indexingHeaderClass, { 'header-btn-active': isIndexExplorerOpen }]"
            @click="toggleIndexExplorer"
          >
            <q-tooltip :delay="300">
              <div class="text-center">
                <div>{{ statusText || 'Index Ready' }}</div>
                <div v-if="progress" class="text-caption">
                  {{ progress.filesProcessed }}/{{ progress.totalFiles }} files
                </div>
              </div>
            </q-tooltip>
            <q-badge
              v-if="isProcessing"
              :label="progressPercentage"
              color="primary"
              floating
              rounded
              class="index-badge"
            />
          </q-btn>
          <!-- Debug Mode Toggle -->
          <q-btn
            flat
            round
            dense
            size="sm"
            icon="bug_report"
            :class="['header-btn', { 'header-btn-debug-active': debugEnabled }]"
            @click="toggleDebugMode"
          >
            <q-tooltip :delay="300">
              Debug Mode: {{ debugEnabled ? 'ON' : 'OFF' }}
              <div class="text-caption">Shows inspect icon on chat messages</div>
            </q-tooltip>
          </q-btn>
          <!-- AI Settings -->
          <q-btn
            flat
            round
            dense
            size="sm"
            icon="settings"
            :class="['header-btn', { 'header-btn-active': isAISettingsOpen }]"
            @click="toggleAISettings"
          >
            <q-tooltip :delay="300">AI Settings</q-tooltip>
          </q-btn>
        </div>
      </div>
    </q-header>

    <q-page-container>
      <q-page class="fit">
        <!-- Main content area with conditional panels -->
        <div class="main-content absolute-full row no-wrap">
          <!-- File Tree Panel -->
          <div
            v-if="showExplorer"
            class="file-tree-panel"
            :style="{ width: explorerWidth + 'px' }"
          >
            <FileTree />
            <!-- Resize Handle -->
            <div
              class="resize-handle"
              @mousedown="startExplorerResize"
            ></div>
          </div>

          <!-- Editor Area -->
          <div class="editor-panel col">
            <router-view />
          </div>

          <!-- AI Panel -->
          <div
            v-if="showAIPanel"
            class="ai-panel-container"
            :style="{ width: aiPanelWidth + 'px' }"
          >
            <!-- Resize Handle -->
            <div
              class="resize-handle resize-handle-left"
              @mousedown="startAIPanelResize"
            ></div>
            <AIPanel />
          </div>
        </div>
      </q-page>
    </q-page-container>

    <!-- Status Bar -->
    <q-footer class="app-footer">
      <StatusBar />
    </q-footer>

    <!-- File Search Modal -->
    <FileSearchModal />

    <!-- Connection Overlay (shown when companion is disconnected) -->
    <ConnectionOverlay />
  </q-layout>
</template>

<script setup lang="ts">
import { ref, computed, watch, onMounted, onUnmounted } from 'vue';
import { useRouter, useRoute } from 'vue-router';
import { storeToRefs } from 'pinia';
import FileTree from '../components/editor/FileTree.vue';
import FileSearchModal from '../components/editor/FileSearchModal.vue';
import AIPanel from '../components/ai/AIPanel/AIPanel.vue';
import StatusBar from '../components/editor/StatusBar.vue';
import ConnectionOverlay from '../components/ConnectionOverlay.vue';
import { useProjectStore } from '../stores/project';
import { useAiConfigStore } from '../stores/aiConfig';
import { useSearchStore } from '../stores/search';
import { useEditorStore } from '../stores/editor';
import { useIndexingStore } from '../stores/indexing';
import { shortcutManager } from '../core/shortcuts/ShortcutManager';

const router = useRouter();
const route = useRoute();

const projectStore = useProjectStore();
const aiConfig = useAiConfigStore();
const searchStore = useSearchStore();
const editorStore = useEditorStore();
const indexingStore = useIndexingStore();

const { debugEnabled } = storeToRefs(aiConfig);

const {
  progress,
  statusText,
  statusIcon,
  isProcessing,
} = storeToRefs(indexingStore);

function toggleDebugMode() {
  void aiConfig.setDebugEnabled(!debugEnabled.value);
}

const indexingHeaderClass = computed(() => {
  if (!progress.value) return '';

  switch (progress.value.phase) {
    case 'scanning':
    case 'parsing':
    case 'embedding':
      return 'header-btn-indexing';
    case 'complete':
      return 'header-btn-success';
    case 'error':
      return 'header-btn-error';
    default:
      return '';
  }
});

const progressPercentage = computed(() => {
  if (!progress.value || progress.value.totalFiles === 0) {
    return '';
  }
  const percent = Math.round(
    (progress.value.filesProcessed / progress.value.totalFiles) * 100,
  );
  return `${percent}%`;
});

// Panel visibility
const storedShowExplorer = localStorage.getItem('xeditor-layout-explorer-visible');
const showExplorer = ref(storedShowExplorer !== null ? storedShowExplorer === 'true' : true);

const storedShowAIPanel = localStorage.getItem('xeditor-layout-ai-visible');
const showAIPanel = ref(storedShowAIPanel !== null ? storedShowAIPanel === 'true' : true);

// Track previous panel states for restoration when closing AISettings
const previousExplorerState = ref<boolean | null>(null);
const previousAIPanelState = ref<boolean | null>(null);

// Track previous panel states for restoration when closing Index Explorer
const previousExplorerStateForIndex = ref<boolean | null>(null);
const previousAIPanelStateForIndex = ref<boolean | null>(null);

// Check if AI Settings page is currently open
const isAISettingsOpen = computed(() => route.path === '/settings/ai');

// Check if Index Explorer page is currently open
const isIndexExplorerOpen = computed(() => route.path === '/index-explorer');

// Panel widths (in pixels)
const storedExplorerWidth = localStorage.getItem('xeditor-layout-explorer-width');
const explorerWidth = ref(storedExplorerWidth ? parseInt(storedExplorerWidth) : 220);

const storedAiPanelWidth = localStorage.getItem('xeditor-layout-ai-width');
const aiPanelWidth = ref(storedAiPanelWidth ? parseInt(storedAiPanelWidth) : 380);

// Persistence watchers
watch(showExplorer, (val) => localStorage.setItem('xeditor-layout-explorer-visible', String(val)));
watch(showAIPanel, (val) => localStorage.setItem('xeditor-layout-ai-visible', String(val)));
watch(explorerWidth, (val) => localStorage.setItem('xeditor-layout-explorer-width', String(val)));
watch(aiPanelWidth, (val) => localStorage.setItem('xeditor-layout-ai-width', String(val)));

// Resize state
let isResizing = false;
let resizeType: 'explorer' | 'aiPanel' | null = null;

function toggleExplorer() {
  showExplorer.value = !showExplorer.value;
}

function toggleAIPanel() {
  showAIPanel.value = !showAIPanel.value;
}

function toggleAISettings() {
  if (isAISettingsOpen.value) {
    void router.push('/');
  } else {
    void router.push('/settings/ai');
  }
}

function toggleIndexExplorer() {
  if (isIndexExplorerOpen.value) {
    void router.push('/');
  } else {
    void router.push('/index-explorer');
  }
}

// Watch for route changes to handle panel collapse/restore
watch(isAISettingsOpen, (isOpen) => {
  if (isOpen) {
    // Opening AISettings - save current panel states and collapse panels
    previousExplorerState.value = showExplorer.value;
    previousAIPanelState.value = showAIPanel.value;
    showExplorer.value = false;
    showAIPanel.value = false;
  } else {
    // Closing AISettings - restore panel states
    if (previousExplorerState.value !== null) {
      showExplorer.value = previousExplorerState.value;
      previousExplorerState.value = null;
    }
    if (previousAIPanelState.value !== null) {
      showAIPanel.value = previousAIPanelState.value;
      previousAIPanelState.value = null;
    }
  }
});

// Watch for route changes to handle panel collapse/restore for Index Explorer
watch(isIndexExplorerOpen, (isOpen) => {
  if (isOpen) {
    // Opening Index Explorer - save current panel states and collapse panels
    previousExplorerStateForIndex.value = showExplorer.value;
    previousAIPanelStateForIndex.value = showAIPanel.value;
    showExplorer.value = false;
    showAIPanel.value = false;
  } else {
    // Closing Index Explorer - restore panel states
    if (previousExplorerStateForIndex.value !== null) {
      showExplorer.value = previousExplorerStateForIndex.value;
      previousExplorerStateForIndex.value = null;
    }
    if (previousAIPanelStateForIndex.value !== null) {
      showAIPanel.value = previousAIPanelStateForIndex.value;
      previousAIPanelStateForIndex.value = null;
    }
  }
});

function startExplorerResize(e: MouseEvent) {
  isResizing = true;
  resizeType = 'explorer';
  document.addEventListener('mousemove', handleResize);
  document.addEventListener('mouseup', stopResize);
  e.preventDefault();
}

function startAIPanelResize(e: MouseEvent) {
  isResizing = true;
  resizeType = 'aiPanel';
  document.addEventListener('mousemove', handleResize);
  document.addEventListener('mouseup', stopResize);
  e.preventDefault();
}

function handleResize(e: MouseEvent) {
  if (!isResizing) return;

  if (resizeType === 'explorer') {
    const newWidth = Math.max(150, Math.min(400, e.clientX));
    explorerWidth.value = newWidth;
  } else if (resizeType === 'aiPanel') {
    // Calculate available width: window width - explorer width - minimum editor width (200px)
    const explorerW = showExplorer.value ? explorerWidth.value : 0;
    const minEditorWidth = 200;
    const maxWidth = window.innerWidth - explorerW - minEditorWidth;
    const newWidth = Math.max(280, Math.min(maxWidth, window.innerWidth - e.clientX));
    aiPanelWidth.value = newWidth;
  }
}

function stopResize() {
  isResizing = false;
  resizeType = null;
  document.removeEventListener('mousemove', handleResize);
  document.removeEventListener('mouseup', stopResize);
}

// Set up global keyboard handler
const handleKeyDown = (e: KeyboardEvent) => {
  void shortcutManager.handleKeyDown(e);
};

// Browser unload protection for unsaved changes
const handleBeforeUnload = (e: BeforeUnloadEvent) => {
  if (editorStore.hasUnsavedChanges) {
    e.preventDefault();
    // Modern browsers require setting returnValue
    e.returnValue = '';
    return '';
  }
};

onMounted(async () => {
  // Initialize stores
  indexingStore.initialize();
  // Initialize project store first (required for editor state restoration)
  await projectStore.initialize();
  // Then initialize other stores and restore editor state in parallel
  await Promise.all([
    aiConfig.initialize(),
    editorStore.restoreState(),
  ]);

  // Register Ctrl+P / Cmd+P for Quick Open
  shortcutManager.register({
    id: 'quick-open',
    combo: 'ctrl+p',
    scope: 'global',
    handler: () => {
      searchStore.toggleSearchModal();
    },
  });

  // Register Cmd+P for Mac
  shortcutManager.register({
    id: 'quick-open-mac',
    combo: 'cmd+p',
    scope: 'global',
    handler: () => {
      searchStore.toggleSearchModal();
    },
  });

  // Register Ctrl+W / Cmd+W to close active tab
  shortcutManager.register({
    id: 'close-tab',
    combo: 'ctrl+w',
    scope: 'global',
    handler: async () => {
      if (editorStore.activeTabId) {
        await editorStore.closeTabWithPrompt(editorStore.activeTabId);
      }
    },
  });

  // Register Cmd+W for Mac
  shortcutManager.register({
    id: 'close-tab-mac',
    combo: 'cmd+w',
    scope: 'global',
    handler: async () => {
      if (editorStore.activeTabId) {
        await editorStore.closeTabWithPrompt(editorStore.activeTabId);
      }
    },
  });

  // Register Ctrl+B / Cmd+B to toggle explorer
  shortcutManager.register({
    id: 'toggle-explorer',
    combo: 'ctrl+b',
    scope: 'global',
    handler: () => {
      toggleExplorer();
    },
  });

  shortcutManager.register({
    id: 'toggle-explorer-mac',
    combo: 'cmd+b',
    scope: 'global',
    handler: () => {
      toggleExplorer();
    },
  });

  // Register Ctrl+L / Cmd+L to toggle AI panel
  shortcutManager.register({
    id: 'toggle-ai-panel',
    combo: 'ctrl+l',
    scope: 'global',
    handler: () => {
      toggleAIPanel();
    },
  });

  shortcutManager.register({
    id: 'toggle-ai-panel-mac',
    combo: 'cmd+l',
    scope: 'global',
    handler: () => {
      toggleAIPanel();
    },
  });

  window.addEventListener('keydown', handleKeyDown);
  window.addEventListener('beforeunload', handleBeforeUnload);
});

onUnmounted(() => {
  window.removeEventListener('keydown', handleKeyDown);
  window.removeEventListener('beforeunload', handleBeforeUnload);
  shortcutManager.unregister('quick-open');
  shortcutManager.unregister('quick-open-mac');
  shortcutManager.unregister('close-tab');
  shortcutManager.unregister('close-tab-mac');
  shortcutManager.unregister('toggle-explorer');
  shortcutManager.unregister('toggle-explorer-mac');
  shortcutManager.unregister('toggle-ai-panel');
  shortcutManager.unregister('toggle-ai-panel-mac');
});
</script>

<style scoped>
.main-layout {
  background: #f5f5f5;
}

/* Header Styling */
.app-header {
  background: #323233 !important;
  height: 32px;
  min-height: 32px;
}

.header-content {
  height: 32px;
  padding: 0 12px;
}

.header-brand {
  text-decoration: none;
  color: #ffffff;
  gap: 8px;
}

.brand-icon {
  color: #1976d2;
}

.brand-title {
  font-size: 13px;
  font-weight: 600;
  letter-spacing: 0.5px;
  color: #e0e0e0;
}

.header-actions {
  gap: 4px;
}

.header-separator {
  height: 16px;
  margin: 0 6px;
  background: rgba(255, 255, 255, 0.2);
}

.header-btn {
  color: #808080;
  width: 28px;
  height: 28px;
  transition: color 0.15s ease, background-color 0.15s ease;
}

.header-btn:hover {
  color: #ffffff;
  background: rgba(255, 255, 255, 0.1);
}

.header-btn-active {
  color: #1976d2 !important;
}

.header-btn-active:hover {
  color: #42a5f5 !important;
}

.header-btn-indexing {
  color: #1976d2 !important;
  animation: pulse 1.5s ease-in-out infinite;
}

.header-btn-debug-active {
  color: #ff9800 !important;
}

.header-btn-debug-active:hover {
  color: #ffb74d !important;
}

.header-btn-success {
  color: #4caf50 !important;
}

.header-btn-error {
  color: #f44336 !important;
}

.index-badge {
  font-size: 9px;
  min-height: 14px;
  padding: 0 4px;
}

@keyframes pulse {
  0%,
  100% {
    opacity: 1;
  }
  50% {
    opacity: 0.5;
  }
}

/* Footer (Status Bar) */
.app-footer {
  background: transparent !important;
  border: none !important;
}

/* Main Content Area */
.main-content {
  background: #f5f5f5;
}

/* Panel Containers */
.file-tree-panel {
  height: 100%;
  display: flex;
  flex-direction: column;
  background: #f8f9fa;
  border-right: 1px solid #e0e0e0;
  overflow: hidden;
  position: relative;
  flex-shrink: 0;
}

.editor-panel {
  height: 100%;
  display: flex;
  flex-direction: column;
  background: #ffffff;
  overflow: hidden;
  min-width: 200px;
}

.ai-panel-container {
  height: 100%;
  display: flex;
  flex-direction: column;
  background: #fafafa;
  border-left: 1px solid #e0e0e0;
  overflow: hidden;
  position: relative;
  flex-shrink: 0;
}

/* Resize Handles */
.resize-handle {
  position: absolute;
  top: 0;
  right: 0;
  width: 4px;
  height: 100%;
  cursor: ew-resize;
  background: transparent;
  z-index: 10;
  transition: background-color 0.15s ease;
}

.resize-handle:hover {
  background: #1976d2;
}

.resize-handle-left {
  left: 0;
  right: auto;
}
</style>
