<template>
  <q-page class="fit editor-page">
    <!-- Editor Area -->
    <div class="column no-wrap fit">
      <!-- Tabs Bar -->
      <EditorTabs class="editor-tabs-bar" />

      <!-- Breadcrumb Navigation -->
      <div v-if="breadcrumbParts.length > 0" class="breadcrumb-bar row items-center no-wrap">
        <template v-for="(part, index) in breadcrumbParts" :key="index">
          <q-icon v-if="index > 0" name="chevron_right" size="14px" class="breadcrumb-separator" />
          <span
            class="breadcrumb-item"
            :class="{ 'breadcrumb-current': index === breadcrumbParts.length - 1 }"
          >
            <q-icon v-if="index === 0" name="folder" size="14px" class="breadcrumb-icon" />
            <q-icon
              v-else-if="index === breadcrumbParts.length - 1"
              :name="getFileIcon(part).icon"
              :style="{ color: getFileIcon(part).color }"
              size="14px"
              class="breadcrumb-icon"
            />
            {{ part }}
          </span>
        </template>
      </div>

      <!-- Editor or Preview -->
      <div class="editor-container">
        <FilePreview
          v-if="activeTab?.viewMode === 'preview'"
          :content="activeTab.content"
          :file-path="activeTab.filePath"
        />
        <MonacoEditor v-else :tab-id="activeTabId" />
      </div>

      <!-- Empty State -->
      <div v-if="!activeTabId" class="empty-editor column items-center justify-center">
        <q-icon name="description" size="64px" color="grey-4" />
        <div class="empty-title">No file open</div>
        <div class="empty-subtitle">
          Open a file from the explorer or use
          <kbd>Ctrl</kbd>+<kbd>P</kbd> to search
        </div>
      </div>
    </div>
  </q-page>
</template>

<script setup lang="ts">
import { computed } from 'vue';
import EditorTabs from '../components/editor/EditorTabs.vue';
import MonacoEditor from '../components/editor/MonacoEditor.vue';
import FilePreview from '../components/editor/FilePreview.vue';
import { useEditorStore } from '../stores/editor';
import { useProjectStore } from '../stores/project';
import { getFileIcon } from '../utils/fileIcons';

const editorStore = useEditorStore();
const projectStore = useProjectStore();
const activeTabId = computed(() => editorStore.activeTabId);
const activeTab = computed(() => editorStore.activeTab);

const breadcrumbParts = computed((): string[] => {
  const activeTab = editorStore.activeTab;
  if (!activeTab) return [];

  const filePath = activeTab.filePath;
  // Split by / and filter out empty parts
  const parts = filePath.split('/').filter((p) => p.length > 0);

  if (parts.length === 0) return [];

  // Replace first part (folder UUID) with folder name
  const folderId = parts[0];
  if (!folderId) return [];

  const folder = projectStore.activeProject?.folders.find((f) => f.id === folderId);
  const folderName: string = folder?.name || folderId;
  const displayParts: string[] = [folderName, ...parts.slice(1)];

  // Limit to last 5 parts for better UX
  if (displayParts.length > 5) {
    return ['...', ...displayParts.slice(-4)];
  }

  return displayParts;
});
</script>

<style scoped>
.editor-page {
  background: #ffffff;
  height: 100%;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.editor-page > .column {
  height: 100%;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.editor-tabs-bar {
  flex: 0 0 auto;
}

.breadcrumb-bar {
  flex: 0 0 auto;
  height: 22px;
  min-height: 22px;
  padding: 0 12px;
  background: #fafafa;
  border-bottom: 1px solid #e8e8e8;
  font-size: 12px;
  color: #616161;
  overflow: hidden;
}

.breadcrumb-separator {
  color: #bdbdbd;
  margin: 0 2px;
}

.breadcrumb-item {
  display: flex;
  align-items: center;
  gap: 4px;
  padding: 2px 4px;
  border-radius: 3px;
  white-space: nowrap;
  transition: background-color 0.15s ease;
}

.breadcrumb-item:hover {
  background: rgba(0, 0, 0, 0.04);
}

.breadcrumb-current {
  color: #1a1a1a;
  font-weight: 500;
}

.breadcrumb-icon {
  flex-shrink: 0;
}

.editor-container {
  flex: 1 1 auto;
  position: relative;
  min-height: 0;
}

.empty-editor {
  position: absolute;
  inset: 0;
  background: #fafafa;
  z-index: 1;
}

.empty-title {
  margin-top: 16px;
  font-size: 18px;
  font-weight: 500;
  color: #616161;
}

.empty-subtitle {
  margin-top: 8px;
  font-size: 13px;
  color: #9e9e9e;
}

.empty-subtitle kbd {
  display: inline-block;
  padding: 2px 6px;
  background: #f0f0f0;
  border: 1px solid #d0d0d0;
  border-radius: 3px;
  font-family: inherit;
  font-size: 11px;
  color: #424242;
}
</style>
