<template>
  <div class="file-tree column no-wrap fit">
    <!-- Folder Picker Dialog -->
    <FolderPickerDialog
      v-model="showFolderPicker"
      @select="handleFolderSelected"
      @cancel="handleFolderPickerCancel"
    />
    <div class="file-tree-header row items-center justify-between border-b full-width no-wrap">
      <div class="row items-center q-gutter-x-sm no-wrap col" style="min-width: 0">
        <div class="text-weight-bold row no-wrap items-center">Explorer</div>
        <q-select
          v-model="selectedProjectId"
          :options="projectOptions"
          option-label="name"
          option-value="id"
          emit-value
          map-options
          dense
          borderless
          class="project-selector col"
          behavior="menu"
          :placeholder="projects.length === 0 ? 'No projects' : undefined"
        >
          <template v-slot:selected-item="scope">
            <div class="ellipsis text-weight-bold text-primary">
              {{ scope.opt.name }}
            </div>
          </template>
          <template v-slot:option="{ itemProps, opt }">
            <q-item v-bind="itemProps">
              <q-item-section v-if="opt.id === '__create_new__'">
                <q-item-label class="text-primary">
                  <q-icon name="add" class="q-mr-sm" />
                  Create New Project...
                </q-item-label>
              </q-item-section>
              <q-item-section v-else>
                <q-item-label>{{ opt.name }}</q-item-label>
                <q-item-label caption
                  >{{ opt.folderCount }} folder{{ opt.folderCount !== 1 ? 's' : '' }}</q-item-label
                >
              </q-item-section>
              <q-item-section v-if="opt.id !== '__create_new__'" side>
                <q-btn
                  flat
                  dense
                  round
                  size="sm"
                  icon="delete"
                  color="negative"
                  class="delete-project-btn"
                  @click.stop="handleDeleteProject(opt.id)"
                >
                  <q-tooltip>Delete project</q-tooltip>
                </q-btn>
              </q-item-section>
            </q-item>
          </template>
        </q-select>
      </div>
      <div class="row q-gutter-xs no-wrap flex-shrink-0">
        <q-btn
          flat
          dense
          round
          size="sm"
          :icon="showHiddenFiles ? 'visibility' : 'visibility_off'"
          :color="showHiddenFiles ? 'primary' : 'grey'"
          @click="handleToggleHiddenFiles"
        >
          <q-tooltip>{{ showHiddenFiles ? 'Hide hidden files' : 'Show hidden files' }}</q-tooltip>
        </q-btn>
        <q-btn
          flat
          dense
          round
          size="sm"
          icon="add_box"
          @click="handleAddFolder"
          :loading="isLoading"
          :disable="!hasActiveProject"
        >
          <q-tooltip>
            {{ hasActiveProject ? 'Add Folder to Workspace' : 'Create or open a project first' }}
          </q-tooltip>
        </q-btn>
        <q-btn flat dense round size="sm" icon="refresh" @click="refreshTree" :loading="isLoading">
          <q-tooltip>Refresh File Tree</q-tooltip>
        </q-btn>
        <q-btn
          v-if="isIndexing && indexingProgress?.phase !== 'paused'"
          flat
          dense
          round
          size="sm"
          icon="pause"
          @click="handlePauseIndexing"
          :disable="!hasFolders"
        >
          <q-tooltip>Pause Indexing</q-tooltip>
        </q-btn>
        <q-btn
          v-if="isIndexing"
          flat
          dense
          round
          size="sm"
          icon="stop"
          @click="handleCancelIndexing"
          :disable="!hasFolders"
        >
          <q-tooltip>Cancel Indexing</q-tooltip>
        </q-btn>
      </div>
    </div>

    <q-scroll-area class="file-tree-body">
      <div v-if="!hasActiveProject" class="file-tree-empty q-pa-md text-center">
        <div class="text-grey-7 q-mb-md">No project selected</div>
        <q-btn
          color="primary"
          label="Create Project"
          @click="handleCreateProject"
          :disable="!companionStore.isConnected"
        />
        <div v-if="!companionStore.isConnected" class="q-mt-md text-warning">
          Local Companion is not connected. Please connect to create projects.
        </div>
      </div>

      <div v-else-if="hasActiveProject && !hasFolders" class="file-tree-empty q-pa-md text-center">
        <div class="text-grey-7 q-mb-md">No folders in project</div>
        <q-btn
          color="primary"
          label="Add Folder"
          @click="handleAddFolder"
          :disable="!companionStore.isConnected"
        />
        <div v-if="!companionStore.isConnected" class="q-mt-md text-warning">
          Local Companion is not connected. Please connect to add folders.
        </div>
      </div>

      <q-virtual-scroll
        v-if="hasFolders"
        :items="flattenedNodes"
        :virtual-scroll-item-size="24"
        class="q-pa-sm"
      >
        <template v-slot="{ item }">
          <div
            :class="[
              'tree-item row items-center no-wrap cursor-pointer relative-position group',
              { 'tree-item-root': item.isRoot },
            ]"
            :style="{ paddingLeft: `${item.level * 16 + 8}px` }"
            draggable="true"
            @dragstart="handleDragStart($event, item)"
            @click="handleItemClick(item)"
            @dblclick="handleItemDoubleClick(item)"
            @contextmenu.prevent="handleContextMenu($event, item)"
          >
            <q-icon
              v-if="item.type === 'directory' && item.hasChildren"
              :name="item.isExpanded ? 'expand_more' : 'chevron_right'"
              class="q-mr-xs tree-arrow"
              size="16px"
              @click.stop="toggleExpand(item)"
            />
            <span v-else class="q-mr-xs tree-arrow-spacer"></span>

            <q-icon
              :name="
                item.type === 'directory'
                  ? getFolderIcon(item.isExpanded, item.isRoot).icon
                  : getFileIcon(item.label).icon
              "
              :style="{
                color:
                  item.type === 'directory'
                    ? getFolderIcon(item.isExpanded, item.isRoot).color
                    : getFileIcon(item.label).color,
              }"
              size="16px"
              class="tree-item-icon"
            />

            <span :class="{ 'text-weight-bold': item.isRoot }" class="ellipsis">
              {{ item.label }}
            </span>

            <q-space />

            <q-btn
              v-if="item.isRoot"
              flat
              dense
              round
              size="xs"
              :icon="folderConnected(item.path) ? 'close' : 'link'"
              class="show-on-hover"
              @click.stop="handleRootAction(item.path)"
            >
              <q-tooltip>
                {{
                  folderConnected(item.path)
                    ? 'Remove folder from workspace'
                    : 'Reconnect folder permission'
                }}
              </q-tooltip>
            </q-btn>
          </div>
        </template>
      </q-virtual-scroll>
    </q-scroll-area>

    <!-- Context Menu -->
    <q-menu ref="contextMenuRef" @hide="contextNode = null" touch-position context-menu>
      <q-list style="min-width: 200px; max-height: none">
        <q-item clickable v-close-popup @click="handleCopyRelativePath">
          <q-item-section avatar>
            <q-icon name="content_copy" size="16px" />
          </q-item-section>
          <q-item-section>Copy Relative Path</q-item-section>
        </q-item>
        <q-item clickable v-close-popup @click="handleCopyAbsolutePath">
          <q-item-section avatar>
            <q-icon name="content_copy" size="16px" />
          </q-item-section>
          <q-item-section>Copy Absolute Path</q-item-section>
        </q-item>
        <q-separator />
        <q-item v-if="contextNode?.type === 'file'" clickable v-close-popup @click="handleShowDiff">
          <q-item-section avatar>
            <q-icon name="compare_arrows" size="16px" />
          </q-item-section>
          <q-item-section>Show Diff vs HEAD</q-item-section>
        </q-item>
        <q-separator />
        <q-item clickable v-close-popup @click="handleDelete">
          <q-item-section avatar>
            <q-icon name="delete" size="16px" color="negative" />
          </q-item-section>
          <q-item-section>
            <q-item-label>Delete</q-item-label>
            <q-item-label caption v-if="contextNode?.type === 'directory'">
              Delete recursively
            </q-item-label>
          </q-item-section>
        </q-item>
      </q-list>
    </q-menu>
  </div>
</template>

<script setup lang="ts">
import { computed, ref, watch, nextTick } from 'vue';
import { storeToRefs } from 'pinia';
import { useQuasar } from 'quasar';
import { useEditorStore } from '../../stores/editor';
import { useProjectStore } from '../../stores/project';
import { useIndexingStore } from '../../stores/indexing';
import { useLocalCompanionStore } from '../../../../stores/localCompanion';
import { getFileIcon, getFolderIcon } from '../../utils/fileIcons';
import FolderPickerDialog from './FolderPickerDialog.vue';
import type { FileNode } from '../../core/types';

interface FlattenedNode {
  label: string;
  path: string;
  type: 'file' | 'directory';
  level: number;
  isRoot: boolean;
  isExpanded: boolean;
  hasChildren: boolean;
}

const editorStore = useEditorStore();
const projectStore = useProjectStore();
const indexingStore = useIndexingStore();
const companionStore = useLocalCompanionStore();
const $q = useQuasar();

const {
  hasActiveProject,
  hasFolders,
  fileTree,
  isLoading,
  projects,
  activeProjectId,
  activeProject,
  showHiddenFiles,
} = storeToRefs(projectStore);
const { progress: indexingProgress, isIndexing } = storeToRefs(indexingStore);
const expandedPaths = ref<Set<string>>(new Set());

// Folder picker dialog state
const showFolderPicker = ref(false);

// Context menu state
const contextNode = ref<FlattenedNode | null>(null);
const contextMenuRef = ref<{ show: (evt?: Event) => void; hide: () => void } | null>(null);

const projectOptions = computed(() => {
  const options = [...projects.value];
  // Always include "Create New Project..." option
  options.push({
    id: '__create_new__',
    name: 'Create New Project...',
    folderCount: 0,
    updatedAt: 0,
  });
  return options;
});
const selectedProjectId = ref<string | null>(activeProjectId.value);

watch(
  () => activeProjectId.value,
  (next) => {
    selectedProjectId.value = next;
  },
);

watch(
  () => selectedProjectId.value,
  (next) => {
    if (!next) return;
    if (next === '__create_new__') {
      selectedProjectId.value = activeProjectId.value; // Reset to current project
      handleCreateProject();
      return;
    }
    if (next === activeProjectId.value) return;
    void projectStore.setActiveProject(next);
  },
);

const flattenedNodes = computed<FlattenedNode[]>(() => {
  const result: FlattenedNode[] = [];

  function flatten(nodes: FileNode[], level = 0): void {
    for (const node of nodes) {
      const isRoot = level === 0;
      const children = node.type === 'directory' ? node.children : undefined;
      const hasChildren = !!children && children.length > 0;
      const isExpanded = expandedPaths.value.has(node.path);

      result.push({
        label: node.name,
        path: node.path,
        type: node.type,
        level,
        isRoot,
        isExpanded,
        hasChildren,
      });

      if (node.type === 'directory' && hasChildren && isExpanded) {
        flatten(children, level + 1);
      }
    }
  }

  flatten(fileTree.value);
  return result;
});

function handleAddFolder(): void {
  // Always use companion folder picker (backend-only)
  if (!companionStore.isConnected) {
    $q.notify({
      type: 'warning',
      message: 'Local Companion is not connected. Please connect to add folders.',
      position: 'top',
    });
    return;
  }

  if (!hasActiveProject.value) {
    $q.notify({
      type: 'warning',
      message: 'No active project. Create or open a project first.',
      position: 'top',
    });
    return;
  }

  showFolderPicker.value = true;
}

async function handleFolderSelected(systemPath: string) {
  showFolderPicker.value = false;

  try {
    await projectStore.addFolder(systemPath);
    $q.notify({
      type: 'positive',
      message: 'Folder added successfully',
      position: 'top',
    });
  } catch (error) {
    $q.notify({
      type: 'negative',
      message: error instanceof Error ? error.message : 'Failed to add folder',
      position: 'top',
    });
  }
}

function handleFolderPickerCancel() {
  showFolderPicker.value = false;
}

function folderConnected(folderId: string): boolean {
  // With backend-only, folders are always connected if they exist
  return activeProject.value?.folders.some((f) => f.id === folderId) ?? false;
}

function handleRootAction(folderId: string): void {
  // Always allow removal (no reconnect needed with backend-only)
  confirmRemoveFolder(folderId);
}

function handleCreateProject() {
  $q.dialog({
    title: 'New Project',
    message: 'Project name',
    prompt: {
      model: '',
      type: 'text',
      isValid: (val: string) => val.trim().length > 0,
    },
    cancel: true,
    persistent: true,
  }).onOk((val: string) => {
    const name = val.trim();
    if (!name) return;
    void projectStore.createProject(name);
  });
}

function handleDeleteProject(projectId: string) {
  const project = projects.value.find((p) => p.id === projectId);
  if (!project) return;

  // Prevent deletion if it's the last project
  if (projects.value.length <= 1) {
    $q.notify({
      type: 'warning',
      message: 'Cannot delete the last project',
      position: 'top',
    });
    return;
  }

  $q.dialog({
    title: 'Delete Project',
    message: `Are you sure you want to delete "${project.name}"? This will permanently delete all project data including indexes, vectors, and cache. This action cannot be undone.`,
    persistent: true,
    ok: {
      label: 'Delete',
      color: 'negative',
      flat: true,
    },
    cancel: {
      label: 'Cancel',
      flat: true,
    },
  }).onOk(() => {
    void projectStore.deleteProjectById(projectId);
  });
}

function toggleExpand(item: FlattenedNode): void {
  if (item.type !== 'directory' || !item.hasChildren) return;
  if (expandedPaths.value.has(item.path)) {
    expandedPaths.value.delete(item.path);
  } else {
    expandedPaths.value.add(item.path);
  }
}

function handleDragStart(event: DragEvent, item: FlattenedNode): void {
  if (!event.dataTransfer) return;

  try {
    const relativePath = projectStore.copyRelativePath(item.path);
    const dragText = `@${relativePath}`;
    event.dataTransfer.setData('text/plain', dragText);
    event.dataTransfer.effectAllowed = 'copy';
  } catch (error) {
    console.error('Failed to prepare drag data:', error);
  }
}

function handleItemClick(item: FlattenedNode): void {
  // Close context menu if open
  if (contextMenuRef.value && contextNode.value) {
    contextMenuRef.value.hide();
    contextNode.value = null;
  }

  if (item.type === 'directory' && item.hasChildren) {
    toggleExpand(item);
  }
}

function handleItemDoubleClick(item: FlattenedNode): void {
  if (item.type === 'file') {
    void editorStore.openFile(item.path);
  }
}

function confirmRemoveFolder(folderId: string): void {
  const folder = activeProject.value?.folders.find((f) => f.id === folderId);
  if (!folder) return;

  $q.dialog({
    title: 'Remove Folder',
    message: `Are you sure you want to remove "${folder.name}" from the workspace? This will remove the folder from the workspace and delete its indexed data/vectors. Files on disk are not deleted.`,
    persistent: true,
    ok: {
      label: 'Remove',
      color: 'negative',
      flat: true,
    },
    cancel: {
      label: 'Cancel',
      flat: true,
    },
  }).onOk(() => {
    removeFolder(folderId);
  });
}

function removeFolder(folderName: string) {
  // Clear expanded paths for this root and its children
  const next = new Set<string>();
  for (const p of expandedPaths.value) {
    if (p === folderName || p.startsWith(`${folderName}/`)) continue;
    next.add(p);
  }
  expandedPaths.value = next;
  void projectStore.removeFolder(folderName);
}

function refreshTree() {
  void projectStore.refreshFileTree();
}

async function handleToggleHiddenFiles() {
  await projectStore.toggleHiddenFiles();
}

function handlePauseIndexing() {
  indexingStore.pauseIndexing();
}

function handleCancelIndexing() {
  indexingStore.cancelIndexing();
}

function handleContextMenu(event: MouseEvent, item: FlattenedNode): void {
  // Only show menu on right-click (button 2) or contextmenu event
  // Check if this is actually a right-click (button 2) or contextmenu event
  if (event.type === 'click' && event.button !== 2) {
    return; // Ignore left-clicks
  }

  // Prevent default browser context menu
  event.preventDefault();
  event.stopPropagation();

  contextNode.value = item;

  // Show menu immediately at cursor position
  // Quasar's QMenu will use event.clientX and event.clientY for positioning
  if (contextMenuRef.value) {
    contextMenuRef.value.show(event);
  } else {
    // If ref not ready, wait for it
    void nextTick(() => {
      if (contextMenuRef.value) {
        contextMenuRef.value.show(event);
      }
    });
  }
}

async function handleCopyRelativePath(): Promise<void> {
  if (!contextNode.value) return;

  try {
    const path = projectStore.copyRelativePath(contextNode.value.path);
    const pathString = String(path); // Ensure it's a string
    await navigator.clipboard.writeText(pathString);
    // Close menu after copying
    if (contextMenuRef.value) {
      contextMenuRef.value.hide();
    }
    $q.notify({
      type: 'positive',
      message: 'Relative path copied to clipboard',
      position: 'bottom',
      timeout: 1500,
    });
  } catch (error) {
    $q.notify({
      type: 'negative',
      message: 'Failed to copy relative path',
      caption: error instanceof Error ? error.message : 'Unknown error',
      position: 'top',
      timeout: 3000,
    });
  }
}

async function handleCopyAbsolutePath(): Promise<void> {
  if (!contextNode.value) return;

  try {
    const path = projectStore.copyAbsolutePath(contextNode.value.path);
    const pathString = String(path); // Ensure it's a string
    await navigator.clipboard.writeText(pathString);
    // Close menu after copying
    if (contextMenuRef.value) {
      contextMenuRef.value.hide();
    }
    $q.notify({
      type: 'positive',
      message: 'Absolute path copied to clipboard',
      position: 'bottom',
      timeout: 1500,
    });
  } catch (error) {
    $q.notify({
      type: 'negative',
      message: 'Failed to copy absolute path',
      caption: error instanceof Error ? error.message : 'Unknown error',
      position: 'top',
      timeout: 3000,
    });
  }
}

async function handleShowDiff(): Promise<void> {
  if (!contextNode.value || contextNode.value.type !== 'file') return;

  try {
    await editorStore.openGitDiff(contextNode.value.path);
  } catch (error) {
    // Error handling is done in openGitDiff
    console.error('Failed to show git diff:', error);
  }
}

function handleDelete(): void {
  if (!contextNode.value) return;

  const item = contextNode.value;
  const itemName = item.label;
  const isDirectory = item.type === 'directory';

  $q.dialog({
    title: isDirectory ? 'Delete Directory' : 'Delete File',
    message: isDirectory
      ? `Are you sure you want to delete "${itemName}" and all its contents? This action cannot be undone.`
      : `Are you sure you want to delete "${itemName}"? This action cannot be undone.`,
    persistent: true,
    ok: {
      label: 'Delete',
      color: 'negative',
      flat: true,
    },
    cancel: {
      label: 'Cancel',
      flat: true,
    },
  }).onOk(() => {
    void (async () => {
      try {
        await projectStore.deletePath(item.path, { recursive: isDirectory });
        $q.notify({
          type: 'positive',
          message: `${isDirectory ? 'Directory' : 'File'} deleted successfully`,
          position: 'top',
          timeout: 2000,
        });
        // File tree will refresh automatically via file_changed events
      } catch (error) {
        $q.notify({
          type: 'negative',
          message: `Failed to delete ${isDirectory ? 'directory' : 'file'}`,
          caption: error instanceof Error ? error.message : 'Unknown error',
          position: 'top',
          timeout: 5000,
        });
      }
    })();
  });
}
</script>

<style scoped>
.file-tree {
  background: #f8f9fa;
  color: #333333;
  height: 100%;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.file-tree-header {
  padding: 0 8px;
  height: 35px;
  flex-shrink: 0;
  background: #f3f3f3;
  border-bottom: 1px solid #e0e0e0;
}

.file-tree-header .text-weight-bold {
  font-size: 11px;
  text-transform: uppercase;
  letter-spacing: 0.5px;
  color: #616161;
}

.project-selector {
  font-size: 12px;
  min-width: 60px;
  max-width: 140px;
}

:deep(.project-selector .q-field__control),
:deep(.project-selector .q-field__native) {
  min-height: 24px;
  padding: 0;
}

.flex-shrink-0 {
  flex-shrink: 0;
}

.file-tree-body {
  flex: 1;
  min-height: 0;
  width: 100%;
  background: #ffffff;
}

.file-tree-empty {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: flex-start;
  padding-top: 40px;
}

.border-b {
  border-bottom: 1px solid #e0e0e0;
}

.tree-item {
  min-height: 22px;
  padding-top: 1px;
  padding-bottom: 1px;
  padding-right: 8px;
  border-radius: 0;
  font-size: 13px;
  transition: background-color 0.1s ease;
}

.tree-item:hover {
  background-color: rgba(0, 0, 0, 0.04);
}

.tree-item-root {
  background-color: transparent;
  margin-top: 4px;
}

.tree-item-root:first-child {
  margin-top: 0;
}

.tree-item-icon {
  flex-shrink: 0;
  margin-right: 6px;
}

.tree-arrow {
  cursor: pointer;
  color: #757575;
  transition: transform 0.15s ease;
  flex-shrink: 0;
}

.tree-arrow:hover {
  color: #424242;
}

.tree-arrow-spacer {
  width: 16px;
  display: inline-block;
  flex-shrink: 0;
}

.tree-item .ellipsis {
  color: #424242;
  line-height: 1.4;
}

.tree-item:hover .ellipsis {
  color: #1a1a1a;
}

.tree-item-root .ellipsis {
  font-weight: 600;
  color: #1976d2;
  font-size: 12px;
  text-transform: uppercase;
  letter-spacing: 0.3px;
}

.show-on-hover {
  opacity: 0;
  transition: opacity 0.15s ease;
}

.group:hover .show-on-hover {
  opacity: 1;
}

.rotate {
  animation: rotate 2s linear infinite;
}

/* Indexing progress styling */
.q-linear-progress {
  border-radius: 2px;
  height: 3px;
}

@keyframes rotate {
  from {
    transform: rotate(0deg);
  }
  to {
    transform: rotate(360deg);
  }
}

/* Selected file indicator - when file is open in editor */
.tree-item-selected {
  background-color: rgba(25, 118, 210, 0.08);
}

.tree-item-selected .ellipsis {
  color: #1976d2;
  font-weight: 500;
}
</style>
