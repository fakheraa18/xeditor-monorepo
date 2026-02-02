<template>
  <div class="editor-tabs row no-wrap items-center">
    <!-- Tab scroll container -->
    <div class="tabs-scroll-container col">
      <q-tabs
        v-model="activeTabId"
        inline-label
        dense
        no-caps
        shrink
        align="left"
        active-class="active-tab"
        class="editor-tabs-bar"
        @update:model-value="handleTabChange"
      >
        <q-tab
          v-for="tab in tabs"
          :key="tab.id"
          :name="tab.id"
          class="editor-tab"
          :class="{ 'tab-dirty': tab.isDirty }"
          draggable="true"
          @dragstart="handleDragStart($event, tab)"
        >
          <template v-slot:default>
            <div class="tab-content row items-center no-wrap">
              <!-- File type icon -->
              <q-icon
                :name="getFileIcon(tab.fileName).icon"
                :style="{ color: getFileIcon(tab.fileName).color }"
                size="16px"
                class="tab-file-icon"
              />
              <!-- File name -->
              <span class="tab-filename ellipsis">{{ tab.fileName }}</span>
              <!-- Modified indicator, preview toggle, and close button -->
              <div class="tab-actions">
                <q-icon v-if="tab.isDirty" name="circle" size="8px" class="dirty-indicator" />
                <q-btn
                  v-if="isTabPreviewable(tab)"
                  flat
                  dense
                  round
                  size="xs"
                  :icon="tab.viewMode === 'preview' ? 'code' : 'visibility'"
                  class="tab-preview-toggle-btn"
                  @click.stop="handleToggleViewMode(tab.id)"
                >
                  <q-tooltip :delay="300">
                    {{ tab.viewMode === 'preview' ? 'Show Code' : 'Show Preview' }}
                  </q-tooltip>
                </q-btn>
                <q-btn
                  flat
                  dense
                  round
                  size="xs"
                  icon="close"
                  class="tab-close-btn"
                  @click.stop="handleCloseTab(tab.id)"
                >
                  <q-tooltip :delay="500">Close</q-tooltip>
                </q-btn>
              </div>
            </div>
          </template>
        </q-tab>
      </q-tabs>
    </div>

    <!-- Actions bar -->
    <div class="tabs-actions row items-center no-wrap">
      <q-separator vertical class="q-mx-xs" />
      <q-btn
        flat
        dense
        round
        size="sm"
        icon="save"
        @click="handleSaveAll"
        :disable="!hasUnsavedChanges"
        class="action-btn"
      >
        <q-tooltip :delay="300">Save All ({{ unsavedCount }})</q-tooltip>
      </q-btn>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue';
import { useEditorStore } from '../../stores/editor';
import { useProjectStore } from '../../stores/project';
import { getFileIcon } from '../../utils/fileIcons';
import { isPreviewable, getFileExtension } from '../../config/previewable';

const editorStore = useEditorStore();
const projectStore = useProjectStore();

const tabs = computed(() => editorStore.tabs);
const activeTabId = computed({
  get: () => editorStore.activeTabId,
  set: (id) => editorStore.setActiveTab(id || ''),
});
const hasUnsavedChanges = computed(() => editorStore.hasUnsavedChanges);
const unsavedCount = computed(() => editorStore.tabs.filter((t) => t.isDirty).length);

function handleTabChange(tabId: string) {
  editorStore.setActiveTab(tabId);
}

async function handleCloseTab(tabId: string) {
  await editorStore.closeTabWithPrompt(tabId);
}

async function handleSaveAll() {
  await editorStore.saveAllTabs();
}

function isTabPreviewable(tab: { filePath: string }): boolean {
  const extension = getFileExtension(tab.filePath);
  return isPreviewable(extension);
}

function handleToggleViewMode(tabId: string) {
  editorStore.toggleViewMode(tabId);
}

function handleDragStart(event: DragEvent, tab: { filePath: string }): void {
  if (!event.dataTransfer) return;

  try {
    let workspacePath: string | null = null;

    // Check if it's already a valid workspace path
    if (projectStore.resolveWorkspacePath(tab.filePath)) {
      workspacePath = tab.filePath;
    } else {
      // Try to resolve from absolute path
      workspacePath = projectStore.resolveAbsolutePath(tab.filePath);
    }

    if (!workspacePath) return;

    const relativePath = projectStore.copyRelativePath(workspacePath);
    const dragText = `@${relativePath}`;
    event.dataTransfer.setData('text/plain', dragText);
    event.dataTransfer.effectAllowed = 'copy';
  } catch (error) {
    console.error('Failed to prepare drag data:', error);
  }
}
</script>

<style scoped>
.editor-tabs {
  background: #f3f3f3;
  border-bottom: 1px solid #e0e0e0;
  height: 36px;
  min-height: 36px;
  max-height: 36px;
}

.tabs-scroll-container {
  overflow-x: auto;
  overflow-y: hidden;
  min-width: 0;
}

/* Hide scrollbar but keep functionality */
.tabs-scroll-container::-webkit-scrollbar {
  height: 0;
  display: none;
}

.editor-tabs-bar {
  height: 35px;
}

:deep(.q-tabs__content) {
  overflow: visible;
  justify-content: flex-start;
}

.editor-tab {
  padding: 0 4px !important;
  min-width: 80px !important;
  max-width: 300px;
  height: 35px;
  background: transparent;
  border-right: 1px solid #e0e0e0;
  transition: all 0.2s ease;
}

.editor-tab:hover {
  background: #e8e8e8;
}

:deep(.editor-tab .q-tab__indicator) {
  display: none;
}

:deep(.active-tab) {
  background: #ffffff !important;
  border-bottom: 2px solid #1976d2;
}

:deep(.active-tab:hover) {
  background: #ffffff !important;
}

.tab-content {
  padding: 0 10px;
  height: 100%;
  gap: 10px;
  width: 100%;
}

.tab-file-icon {
  flex-shrink: 0;
}

.tab-filename {
  font-size: 13px;
  font-weight: 400;
  color: #616161;
  max-width: 200px;
  letter-spacing: 0.01em;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  flex: 1 1 auto;
}

:deep(.active-tab) .tab-filename {
  color: #1a1a1a;
  font-weight: 500;
}

.tab-actions {
  display: flex;
  align-items: center;
  gap: 4px;
  flex-shrink: 0;
  justify-content: center;
}

.dirty-indicator {
  color: #fb8c00;
}

.tab-preview-toggle-btn {
  opacity: 0;
  width: 18px !important;
  height: 18px !important;
  min-width: 18px !important;
  min-height: 18px !important;
  color: #757575;
  transition:
    opacity 0.15s ease,
    background-color 0.15s ease;
}

.tab-preview-toggle-btn:hover {
  background: rgba(0, 0, 0, 0.1);
  color: #1976d2;
}

.tab-close-btn {
  opacity: 0;
  width: 18px !important;
  height: 18px !important;
  min-width: 18px !important;
  min-height: 18px !important;
  color: #757575;
  transition:
    opacity 0.15s ease,
    background-color 0.15s ease;
}

.tab-close-btn:hover {
  background: rgba(0, 0, 0, 0.1);
  color: #424242;
}

.editor-tab:hover .tab-preview-toggle-btn,
.editor-tab:hover .tab-close-btn {
  opacity: 1;
}

.editor-tab:hover .dirty-indicator {
  display: none;
}

.tab-dirty .tab-preview-toggle-btn,
.tab-dirty .tab-close-btn {
  opacity: 0;
}

.tab-dirty:hover .tab-preview-toggle-btn,
.tab-dirty:hover .tab-close-btn {
  opacity: 1;
}

.tabs-actions {
  background: #f3f3f3;
  padding: 0 4px;
  flex-shrink: 0;
}

.action-btn {
  color: #616161;
}

.action-btn:hover {
  color: #1976d2;
}

.action-btn:disabled {
  color: #bdbdbd;
}
</style>
