<template>
  <div v-if="artifacts && artifacts.length > 0" class="artifacts-section">
    <div class="artifacts-header">
      <q-icon name="folder_special" size="14px" class="q-mr-xs text-grey-6" />
      <span class="text-grey-6"
        >{{ artifacts.length }} artifact{{ artifacts.length > 1 ? 's' : '' }}</span
      >
    </div>
    <div class="artifacts-list">
      <div
        v-for="artifact in artifacts"
        :key="artifact.path"
        class="artifact-chip"
        :title="artifact.path"
        @click="openArtifact(artifact)"
      >
        <q-icon :name="getArtifactIcon(artifact.type)" size="14px" class="artifact-icon" />
        <span class="artifact-name">{{ artifact.name }}</span>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { useQuasar } from 'quasar';
import { useEditorStore } from '../../../../stores/editor';
import { useProjectStore } from '../../../../stores/project';
import type { Artifact, EditorTab } from '../../../../core/types';
import { isPreviewable, getFileExtension } from '../../../../config/previewable';

defineProps<{
  artifacts: Artifact[] | undefined;
}>();

const $q = useQuasar();
const editorStore = useEditorStore();
const projectStore = useProjectStore();

function getArtifactIcon(type: string): string {
  switch (type) {
    case 'plan':
      return 'assignment';
    case 'file':
      return 'description';
    default:
      return 'insert_drive_file';
  }
}

async function openArtifact(artifact: Artifact): Promise<void> {
  try {
    // Check if file is already open (by absolute path)
    const existingTab = editorStore.tabs.find((tab) => tab.filePath === artifact.path);
    if (existingTab) {
      editorStore.setActiveTab(existingTab.id);
      return;
    }

    // Read file content using editor I/O (full content, no chunking)
    const content = await projectStore.readAbsoluteFileForEditor(artifact.path);

    // Determine language from extension
    const extension = artifact.path.split('.').pop()?.toLowerCase();
    const languageMap: Record<string, string> = {
      ts: 'typescript',
      tsx: 'typescript',
      js: 'javascript',
      jsx: 'javascript',
      vue: 'html',
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
    const fileExtension = getFileExtension(artifact.path);
    const initialViewMode: 'code' | 'preview' = isPreviewable(fileExtension) ? 'preview' : 'code';

    // Create tab manually
    const tab: EditorTab = {
      id: `tab-${Date.now()}-${Math.random()}`,
      filePath: artifact.path,
      fileName: artifact.name,
      content,
      originalContent: content,
      isDirty: false,
      language,
      viewMode: initialViewMode,
    };

    editorStore.tabs.push(tab);
    editorStore.setActiveTab(tab.id);
  } catch (error) {
    console.error('Error opening artifact:', error);
    $q.notify({
      type: 'negative',
      message: `Failed to open artifact: ${artifact.name}`,
      caption: error instanceof Error ? error.message : 'Unknown error',
      position: 'top',
      timeout: 3000,
    });
  }
}
</script>

<style scoped>
.artifacts-section {
  margin-top: 12px;
  border-top: 1px solid #f0f0f0;
  padding-top: 8px;
}

.artifacts-header {
  display: flex;
  align-items: center;
  margin-bottom: 8px;
  font-size: 11px;
}

.artifacts-list {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.artifact-chip {
  display: inline-flex;
  align-items: center;
  padding: 6px 12px;
  background: linear-gradient(135deg, #e8f5e9 0%, #c8e6c9 100%);
  border: 1px solid #a5d6a7;
  border-radius: 16px;
  font-size: 12px;
  cursor: pointer;
  transition: all 0.2s ease;
}

.artifact-chip:hover {
  background: linear-gradient(135deg, #c8e6c9 0%, #a5d6a7 100%);
  border-color: #81c784;
  transform: translateY(-1px);
  box-shadow: 0 2px 4px rgba(0, 0, 0, 0.1);
}

.artifact-icon {
  color: #388e3c;
  margin-right: 6px;
}

.artifact-name {
  color: #2e7d32;
  font-weight: 500;
  max-width: 200px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
</style>
