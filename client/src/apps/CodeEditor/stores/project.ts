import { defineStore } from 'pinia';
import { ref, computed } from 'vue';
import type {
  EmbeddingModelId,
  FileNode,
  FolderRuntimeState,
  ProjectFolderId,
  ProjectFolderRecord,
  ProjectId,
  ProjectRecord,
  ProjectSummary,
} from '../core/types';
import {
  createProject as createCompanionProject,
  deleteProject as deleteCompanionProject,
  getProject as getCompanionProject,
  listProjects as listCompanionProjects,
  updateProject as updateCompanionProject,
} from '../core/persistence/companionProjects';
import { getLastOpenedProjectId, setLastOpenedProjectId } from '../core/persistence/indexedDb';
import { useLocalCompanionStore } from '../../../stores/localCompanion';
import { indexOrchestrator } from '../core/indexing/IndexOrchestrator';
import { useIndexingStore } from './indexing';
import { useChatStore } from './chat';

const STORAGE_KEY_SHOW_HIDDEN = 'xeditor.showHiddenFiles';

function loadShowHiddenFiles(): boolean {
  if (typeof window === 'undefined' || !window.localStorage) {
    return false;
  }
  const stored = window.localStorage.getItem(STORAGE_KEY_SHOW_HIDDEN);
  return stored === 'true';
}

function saveShowHiddenFiles(value: boolean): void {
  if (typeof window === 'undefined' || !window.localStorage) {
    return;
  }
  window.localStorage.setItem(STORAGE_KEY_SHOW_HIDDEN, String(value));
}

/**
 * Sanitize folder name for path usage (matches server-side sanitization)
 */
function sanitizeFolderName(name: string): string {
  let sanitized = name
    .replace(/\//g, '_')
    .replace(/\\/g, '_')
    .replace(/:/g, '_')
    .replace(/\*/g, '_')
    .replace(/\?/g, '_')
    .replace(/"/g, '_')
    .replace(/</g, '_')
    .replace(/>/g, '_')
    .replace(/\|/g, '_')
    .trim();

  // Remove leading/trailing dots and spaces
  sanitized = sanitized.replace(/^[.\s]+|[.\s]+$/g, '');

  // Replace multiple consecutive underscores
  sanitized = sanitized.replace(/_+/g, '_');

  return sanitized || 'folder';
}

/**
 * Resolve folder identifier (UUID or folder name) to folder ID
 * Supports both legacy UUID format and new folder name format
 */
function resolveFolderId(
  folderIdentifier: string,
  folders: ProjectFolderRecord[],
): ProjectFolderId | null {
  if (!folderIdentifier) {
    return null;
  }

  // Check if it's a UUID (legacy format: 8-4-4-4-12 hex digits)
  const uuidPattern = /^[\w-]{8}-[\w-]{4}-[\w-]{4}-[\w-]{4}-[\w-]{12}$/;
  if (uuidPattern.test(folderIdentifier)) {
    // Legacy format: it's already a folder ID
    const folder = folders.find((f) => f.id === folderIdentifier);
    return folder ? folder.id : null;
  }

  // New format: it's a folder name, find matching folder
  const sanitizedIdentifier = sanitizeFolderName(folderIdentifier);
  const folder = folders.find((f) => {
    const sanitizedName = sanitizeFolderName(f.name);
    return sanitizedName === sanitizedIdentifier;
  });

  return folder ? folder.id : null;
}

export const useProjectStore = defineStore('project', () => {
  const fileTree = ref<FileNode[]>([]);
  const isLoading = ref(false);
  const projects = ref<ProjectSummary[]>([]);
  const activeProject = ref<ProjectRecord | null>(null);
  const folderRuntimeState = ref<Record<ProjectFolderId, FolderRuntimeState>>({});
  const showHiddenFiles = ref(loadShowHiddenFiles());

  const hasActiveProject = computed(() => activeProject.value !== null);
  const hasFolders = computed(() => (activeProject.value?.folders.length ?? 0) > 0);
  const hasConnectedFolders = computed(() => {
    // With backend-only, folders are always "connected" if they exist
    return hasFolders.value;
  });

  const activeProjectId = computed<ProjectId | null>(() => activeProject.value?.id ?? null);

  // No longer needed - companion handles persistence

  function generateId(): string {
    if (typeof crypto !== 'undefined' && typeof crypto.randomUUID === 'function') {
      return crypto.randomUUID();
    }
    return `id-${Date.now()}-${Math.random().toString(16).slice(2)}`;
  }

  async function initialize(): Promise<void> {
    isLoading.value = true;
    try {
      projects.value = await listCompanionProjects();
      const lastId = await getLastOpenedProjectId();

      const candidateId =
        (lastId && projects.value.some((p) => p.id === lastId) ? lastId : null) ??
        projects.value[0]?.id ??
        null;

      if (!candidateId) {
        activeProject.value = null;
        fileTree.value = [];
        folderRuntimeState.value = {};
        return;
      }

      await setActiveProject(candidateId);
    } finally {
      isLoading.value = false;
    }
  }

  async function createProject(name: string): Promise<ProjectRecord> {
    const projectId = generateId();
    const project = await createCompanionProject(projectId, name, []);
    projects.value = await listCompanionProjects();
    await setLastOpenedProjectId(project.id);
    activeProject.value = project;
    fileTree.value = [];
    folderRuntimeState.value = {};
    return project;
  }

  async function setActiveProject(projectId: ProjectId): Promise<void> {
    const project = await getCompanionProject(projectId);
    if (!project) {
      await setLastOpenedProjectId(null);
      activeProject.value = null;
      fileTree.value = [];
      folderRuntimeState.value = {};
      projects.value = await listCompanionProjects();
      return;
    }

    activeProject.value = project;
    await setLastOpenedProjectId(projectId);
    projects.value = await listCompanionProjects();

    // Initialize folder runtime state (all folders are "connected" with backend-only)
    const next: Record<ProjectFolderId, FolderRuntimeState> = {};
    for (const folder of project.folders) {
      next[folder.id] = {
        folderId: folder.id,
        permission: 'granted',
        connected: true,
        lastCheckedAt: Date.now(),
      };
    }
    folderRuntimeState.value = next;

    // Refresh file tree and trigger indexing in the background
    // This allows file restoration to proceed immediately after project is set
    void refreshFileTree().then(() => {
      // Trigger indexing if folders exist (after file tree is loaded)
      if (hasFolders.value) {
        const indexingStore = useIndexingStore();
        void indexingStore.triggerIndexing(projectId, 'startup');
      }
    });
  }

  async function renameActiveProject(name: string): Promise<void> {
    if (!activeProject.value) return;
    const updated = await updateCompanionProject(activeProject.value.id, { name });
    activeProject.value = updated;
    projects.value = await listCompanionProjects();
  }

  async function deleteProjectById(projectId: ProjectId): Promise<void> {
    // Cancel active indexing if it's for this project
    if (indexOrchestrator.isIndexingForProject(projectId)) {
      indexOrchestrator.cancelForProject(projectId);
      // Wait for indexing to finish (with timeout)
      await indexOrchestrator.waitForIndexingToFinish(5000);
    }

    // Switch active project BEFORE deleting data if this is the active project
    if (activeProject.value?.id === projectId) {
      await initialize();
    }

    // Delete chat sessions for this project
    const chatStore = useChatStore();
    await chatStore.cleanupProjectSessions(projectId);

    // Delete companion project (includes all data on disk)
    await deleteCompanionProject(projectId);

    // Update projects list
    projects.value = await listCompanionProjects();

    // Clear last opened project if it was the deleted one
    const last = await getLastOpenedProjectId();
    if (last === projectId) {
      await setLastOpenedProjectId(null);
    }
  }

  function refreshFolderPermissions(): void {
    // With backend-only, all folders are always "connected"
    if (!activeProject.value) {
      folderRuntimeState.value = {};
      return;
    }

    const next: Record<ProjectFolderId, FolderRuntimeState> = {};
    const now = Date.now();

    for (const folder of activeProject.value.folders) {
      next[folder.id] = {
        folderId: folder.id,
        permission: 'granted',
        connected: true,
        lastCheckedAt: now,
      };
    }

    folderRuntimeState.value = next;
  }

  async function reconnectFolder(_folderId: ProjectFolderId): Promise<void> {
    // With backend-only, folders are always connected - just refresh
    refreshFolderPermissions();
    await refreshFileTree();

    if (activeProject.value) {
      const indexingStore = useIndexingStore();
      await indexingStore.triggerIndexing(activeProject.value.id, 'folder-add');
    }
  }

  async function addFolder(systemPath: string): Promise<void> {
    if (!systemPath) {
      throw new Error('System path is required');
    }

    if (!activeProject.value) {
      throw new Error('No active project. Create or open a project first.');
    }

    try {
      // Extract folder name from path
      const pathParts = systemPath.split(/[/\\]/).filter(Boolean);
      const folderName = pathParts[pathParts.length - 1] || systemPath;

      const folder: ProjectFolderRecord = {
        id: generateId(),
        name: folderName,
        systemPath,
        addedAt: Date.now(),
      };

      const updatedFolders = [...activeProject.value.folders, folder];
      const updated = await updateCompanionProject(activeProject.value.id, {
        folders: updatedFolders.map((f) => ({
          id: f.id,
          name: f.name,
          path: f.systemPath,
        })),
      });

      activeProject.value = updated;
      projects.value = await listCompanionProjects();

      // Update folder runtime state
      folderRuntimeState.value = {
        ...folderRuntimeState.value,
        [folder.id]: {
          folderId: folder.id,
          permission: 'granted',
          connected: true,
          lastCheckedAt: Date.now(),
        },
      };

      await refreshFileTree();

      // Trigger indexing for the new folder
      if (activeProject.value) {
        const indexingStore = useIndexingStore();
        await indexingStore.triggerIndexing(activeProject.value.id, 'folder-add');
      }
    } catch (error) {
      console.error('Failed to add folder:', error);
      throw error;
    }
  }

  async function removeFolder(folderId: ProjectFolderId) {
    if (!activeProject.value) return;

    // Remove folder's index data before removing from project
    if (activeProject.value.id) {
      try {
        await indexOrchestrator.removeFolderFromIndex(activeProject.value.id, [folderId]);

        // Reload index stats after removal
        const indexingStore = useIndexingStore();
        await indexingStore.loadStats();
      } catch (error) {
        console.error('Failed to remove folder from index:', error);
        // Continue with folder removal even if index cleanup fails
      }
    }

    const nextFolders = activeProject.value.folders.filter((f) => f.id !== folderId);
    const updated = await updateCompanionProject(activeProject.value.id, {
      folders: nextFolders.map((f) => ({
        id: f.id,
        name: f.name,
        path: f.systemPath,
      })),
    });

    activeProject.value = updated;
    projects.value = await listCompanionProjects();

    const { [folderId]: _removed, ...rest } = folderRuntimeState.value;
    folderRuntimeState.value = rest;

    await refreshFileTree();
  }

  async function refreshFileTree() {
    isLoading.value = true;
    try {
      const combinedTree: FileNode[] = [];
      if (!activeProject.value) {
        fileTree.value = [];
        return;
      }

      const companionStore = useLocalCompanionStore();

      for (const folder of activeProject.value.folders) {
        try {
          const response = await companionStore.request<{
            success: boolean;
            tree?: FileNode;
            error?: string;
          }>('list_tree', {
            rootPath: folder.systemPath,
            showHidden: showHiddenFiles.value,
            maxDepth: 10, // Reasonable limit to avoid huge trees
          });

          if (response.success && response.tree) {
            // Map the tree paths to use folder.id as root, converting absolute paths to relative
            const mappedTree = mapTreePaths(response.tree, folder.id, folder.systemPath);
            combinedTree.push(mappedTree);
          } else {
            // Fallback: empty tree
            combinedTree.push({
              name: folder.name,
              path: folder.id,
              type: 'directory',
              children: [],
            });
          }
        } catch (error) {
          console.error(`Failed to load tree for folder ${folder.name}:`, error);
          combinedTree.push({
            name: folder.name,
            path: folder.id,
            type: 'directory',
            children: [],
          });
        }
      }
      fileTree.value = combinedTree;
    } finally {
      isLoading.value = false;
    }
  }

  function mapTreePaths(node: FileNode, rootId: string, rootSystemPath: string): FileNode {
    // Normalize paths to POSIX format (handle Windows paths)
    const normalizePath = (path: string): string => path.replace(/\\/g, '/');
    const normalizedSystemPath = normalizePath(rootSystemPath);
    const normalizedNodePath = normalizePath(node.path);

    // For the root node, use folderId as path and folder name
    if (
      normalizedNodePath === normalizedSystemPath ||
      normalizedNodePath === normalizedSystemPath + '/'
    ) {
      const mappedChildren =
        node.children?.map((child) => mapTreePaths(child, rootId, rootSystemPath)) ?? [];
      return {
        name: node.name, // Keep original name from companion (folder name)
        path: rootId,
        type: 'directory',
        children: mappedChildren,
      };
    }

    // For children, compute relative path by stripping the system root
    let relativePath: string;
    if (normalizedNodePath.startsWith(normalizedSystemPath + '/')) {
      // Absolute path: strip the system root prefix
      relativePath = normalizedNodePath.slice(normalizedSystemPath.length + 1);
    } else if (normalizedNodePath.startsWith(normalizedSystemPath)) {
      // Edge case: path equals system path exactly
      relativePath = '';
    } else {
      // Already relative or unexpected format - use as-is but log warning
      console.warn(
        `Unexpected path format in tree mapping: ${normalizedNodePath} (system root: ${normalizedSystemPath})`,
      );
      relativePath = normalizedNodePath.startsWith('/')
        ? normalizedNodePath.slice(1)
        : normalizedNodePath;
    }

    // Build workspace path: folderId/relativePath
    const workspacePath = relativePath ? `${rootId}/${relativePath}` : rootId;
    const newPath = workspacePath.replace(/\/+/g, '/'); // Normalize duplicate slashes

    if (node.type === 'file') {
      return {
        ...node,
        path: newPath,
      };
    }

    // Directory node
    const mappedChildren =
      node.children?.map((child) => mapTreePaths(child, rootId, rootSystemPath)) ?? [];

    return {
      ...node,
      path: newPath,
      children: mappedChildren,
    };
  }

  async function readFile(filePath: string): Promise<string> {
    const parts = filePath.split('/');
    const folderIdentifier = parts[0];

    if (!folderIdentifier) {
      throw new Error(`Invalid file path: ${filePath}`);
    }

    if (!activeProject.value) {
      throw new Error('No active project');
    }

    // Resolve folder identifier (UUID or folder name) to folder ID
    const rootFolderId = resolveFolderId(folderIdentifier, activeProject.value.folders);
    if (!rootFolderId) {
      throw new Error(`Root folder not found for path: ${filePath}`);
    }

    const folder = activeProject.value.folders.find((f) => f.id === rootFolderId);
    if (!folder) {
      throw new Error(`Root folder not found for path: ${filePath}`);
    }

    // Build relative path from folder root
    const relativeParts = parts.slice(1);
    let relativePath = relativeParts.join('/');

    // Defensive: strip system path if it's already included (prevents double-prefixing)
    const normalizedSystemPath = folder.systemPath.replace(/\\/g, '/');
    const normalizedRelativePath = relativePath.replace(/\\/g, '/');

    if (normalizedRelativePath.startsWith(normalizedSystemPath + '/')) {
      // Path already contains system path - strip it
      relativePath = normalizedRelativePath.slice(normalizedSystemPath.length + 1);
    } else if (normalizedRelativePath === normalizedSystemPath) {
      // Edge case: path equals system path exactly
      relativePath = '';
    }

    const fullPath = relativePath
      ? `${normalizedSystemPath}/${relativePath}`.replace(/\/+/g, '/')
      : normalizedSystemPath;

    const companionStore = useLocalCompanionStore();
    const response = await companionStore.request<{
      success: boolean;
      result?: {
        content: string;
        path: string;
        size: number;
      };
      error?: string;
    }>('execute_tool', {
      tool: 'read_file',
      args: {
        path: fullPath,
      },
      projectRoot: folder.systemPath,
    });

    if (!response.success || !response.result) {
      throw new Error(response.error ?? 'Failed to read file');
    }

    return response.result.content;
  }

  async function writeFile(filePath: string, content: string): Promise<void> {
    const parts = filePath.split('/');
    const folderIdentifier = parts[0];

    if (!folderIdentifier) {
      throw new Error(`Invalid file path: ${filePath}`);
    }

    if (!activeProject.value) {
      throw new Error('No active project');
    }

    // Resolve folder identifier (UUID or folder name) to folder ID
    const rootFolderId = resolveFolderId(folderIdentifier, activeProject.value.folders);
    if (!rootFolderId) {
      throw new Error(`Root folder not found for path: ${filePath}`);
    }

    const folder = activeProject.value.folders.find((f) => f.id === rootFolderId);
    if (!folder) {
      throw new Error(`Root folder not found for path: ${filePath}`);
    }

    // Build relative path from folder root
    const relativeParts = parts.slice(1);
    let relativePath = relativeParts.join('/');

    // Defensive: strip system path if it's already included (prevents double-prefixing)
    const normalizedSystemPath = folder.systemPath.replace(/\\/g, '/');
    const normalizedRelativePath = relativePath.replace(/\\/g, '/');

    if (normalizedRelativePath.startsWith(normalizedSystemPath + '/')) {
      // Path already contains system path - strip it
      relativePath = normalizedRelativePath.slice(normalizedSystemPath.length + 1);
    } else if (normalizedRelativePath === normalizedSystemPath) {
      // Edge case: path equals system path exactly
      relativePath = '';
    }

    const fullPath = relativePath
      ? `${normalizedSystemPath}/${relativePath}`.replace(/\/+/g, '/')
      : normalizedSystemPath;

    const companionStore = useLocalCompanionStore();
    const response = await companionStore.request<{
      success: boolean;
      result?: {
        path: string;
        bytesWritten: number;
        changeType: string;
      };
      error?: string;
    }>('execute_tool', {
      tool: 'write_file',
      args: {
        path: fullPath,
        content,
      },
      projectRoot: folder.systemPath,
    });

    if (!response.success) {
      throw new Error(response.error ?? 'Failed to write file');
    }
  }

  async function toggleHiddenFiles(): Promise<void> {
    showHiddenFiles.value = !showHiddenFiles.value;
    saveShowHiddenFiles(showHiddenFiles.value);
    await refreshFileTree();
  }

  /**
   * Read a file for the editor (full content, no chunking).
   * Uses the dedicated editor I/O RPC instead of the tool.
   */
  async function readFileForEditor(filePath: string): Promise<string> {
    const parts = filePath.split('/');
    const folderIdentifier = parts[0];

    if (!folderIdentifier) {
      throw new Error(`Invalid file path: ${filePath}`);
    }

    if (!activeProject.value) {
      throw new Error('No active project');
    }

    // Resolve folder identifier (UUID or folder name) to folder ID
    const rootFolderId = resolveFolderId(folderIdentifier, activeProject.value.folders);
    if (!rootFolderId) {
      throw new Error(`Root folder not found for path: ${filePath}`);
    }

    const folder = activeProject.value.folders.find((f) => f.id === rootFolderId);
    if (!folder) {
      throw new Error(`Root folder not found for path: ${filePath}`);
    }

    // Build relative path from folder root
    const relativeParts = parts.slice(1);
    let relativePath = relativeParts.join('/');

    // Defensive: strip system path if it's already included (prevents double-prefixing)
    const normalizedSystemPath = folder.systemPath.replace(/\\/g, '/');
    const normalizedRelativePath = relativePath.replace(/\\/g, '/');

    if (normalizedRelativePath.startsWith(normalizedSystemPath + '/')) {
      // Path already contains system path - strip it
      relativePath = normalizedRelativePath.slice(normalizedSystemPath.length + 1);
    } else if (normalizedRelativePath === normalizedSystemPath) {
      // Edge case: path equals system path exactly
      relativePath = '';
    }

    const fullPath = relativePath
      ? `${normalizedSystemPath}/${relativePath}`.replace(/\/+/g, '/')
      : normalizedSystemPath;

    const companionStore = useLocalCompanionStore();
    const response = await companionStore.request<{
      success: boolean;
      result?: {
        content: string;
        path: string;
        sizeBytes: number;
      };
      error?: string;
    }>('read_file_editor', {
      path: fullPath,
      projectRoot: folder.systemPath,
    });

    if (!response.success || !response.result) {
      throw new Error(response.error ?? 'Failed to read file');
    }

    return response.result.content;
  }

  /**
   * Write a file for the editor (full content, no truncation).
   * Uses the dedicated editor I/O RPC instead of the tool.
   */
  async function writeFileForEditor(filePath: string, content: string): Promise<void> {
    const parts = filePath.split('/');
    const folderIdentifier = parts[0];

    if (!folderIdentifier) {
      throw new Error(`Invalid file path: ${filePath}`);
    }

    if (!activeProject.value) {
      throw new Error('No active project');
    }

    // Resolve folder identifier (UUID or folder name) to folder ID
    const rootFolderId = resolveFolderId(folderIdentifier, activeProject.value.folders);
    if (!rootFolderId) {
      throw new Error(`Root folder not found for path: ${filePath}`);
    }

    const folder = activeProject.value.folders.find((f) => f.id === rootFolderId);
    if (!folder) {
      throw new Error(`Root folder not found for path: ${filePath}`);
    }

    // Build relative path from folder root
    const relativeParts = parts.slice(1);
    let relativePath = relativeParts.join('/');

    // Defensive: strip system path if it's already included (prevents double-prefixing)
    const normalizedSystemPath = folder.systemPath.replace(/\\/g, '/');
    const normalizedRelativePath = relativePath.replace(/\\/g, '/');

    if (normalizedRelativePath.startsWith(normalizedSystemPath + '/')) {
      // Path already contains system path - strip it
      relativePath = normalizedRelativePath.slice(normalizedSystemPath.length + 1);
    } else if (normalizedRelativePath === normalizedSystemPath) {
      // Edge case: path equals system path exactly
      relativePath = '';
    }

    const fullPath = relativePath
      ? `${normalizedSystemPath}/${relativePath}`.replace(/\/+/g, '/')
      : normalizedSystemPath;

    const companionStore = useLocalCompanionStore();
    const response = await companionStore.request<{
      success: boolean;
      result?: {
        path: string;
        bytesWritten: number;
        changeType: string;
      };
      error?: string;
    }>('write_file_editor', {
      path: fullPath,
      content,
      projectRoot: folder.systemPath,
    });

    if (!response.success) {
      throw new Error(response.error ?? 'Failed to write file');
    }
  }

  /**
   * Read an absolute file path for the editor (full content, no chunking).
   * Used for files outside project folders.
   */
  async function readAbsoluteFileForEditor(absolutePath: string): Promise<string> {
    const companionStore = useLocalCompanionStore();
    const response = await companionStore.request<{
      success: boolean;
      result?: {
        content: string;
        path: string;
        sizeBytes: number;
      };
      error?: string;
    }>('read_file_editor', {
      path: absolutePath,
    });

    if (!response.success || !response.result) {
      throw new Error(response.error ?? 'Failed to read file');
    }

    return response.result.content;
  }

  /**
   * Read a specific line range from a file using the tool's offset/limit feature.
   * This avoids chunking issues when reading snippets for context.
   * Returns the content of the specified line range (0-based line numbers).
   */
  async function readFileRange(
    filePath: string,
    startLine: number,
    endLine: number,
  ): Promise<string> {
    const parts = filePath.split('/');
    const folderIdentifier = parts[0];

    if (!folderIdentifier) {
      throw new Error(`Invalid file path: ${filePath}`);
    }

    if (!activeProject.value) {
      throw new Error('No active project');
    }

    // Resolve folder identifier (UUID or folder name) to folder ID
    const rootFolderId = resolveFolderId(folderIdentifier, activeProject.value.folders);
    if (!rootFolderId) {
      throw new Error(`Root folder not found for path: ${filePath}`);
    }

    const folder = activeProject.value.folders.find((f) => f.id === rootFolderId);
    if (!folder) {
      throw new Error(`Root folder not found for path: ${filePath}`);
    }

    // Build relative path from folder root
    const relativeParts = parts.slice(1);
    let relativePath = relativeParts.join('/');

    // Defensive: strip system path if it's already included (prevents double-prefixing)
    const normalizedSystemPath = folder.systemPath.replace(/\\/g, '/');
    const normalizedRelativePath = relativePath.replace(/\\/g, '/');

    if (normalizedRelativePath.startsWith(normalizedSystemPath + '/')) {
      // Path already contains system path - strip it
      relativePath = normalizedRelativePath.slice(normalizedSystemPath.length + 1);
    } else if (normalizedRelativePath === normalizedSystemPath) {
      // Edge case: path equals system path exactly
      relativePath = '';
    }

    const fullPath = relativePath
      ? `${normalizedSystemPath}/${relativePath}`.replace(/\/+/g, '/')
      : normalizedSystemPath;

    const companionStore = useLocalCompanionStore();
    const response = await companionStore.request<{
      success: boolean;
      result?: {
        content: string;
        path: string;
        totalLines: number;
        truncated: boolean;
        strategy: string;
      };
      error?: string;
    }>('execute_tool', {
      tool: 'read_file',
      args: {
        path: fullPath,
        offset: startLine,
        limit: endLine - startLine + 1,
      },
      projectRoot: folder.systemPath,
    });

    if (!response.success || !response.result) {
      throw new Error(response.error ?? 'Failed to read file range');
    }

    return response.result.content;
  }

  /**
   * Get the embedding model ID for the active project, with default fallback
   */
  function getEmbeddingModelId(): EmbeddingModelId {
    if (!activeProject.value) {
      return 'sentence-transformers/all-MiniLM-L6-v2'; // Default
    }
    return (
      activeProject.value.settings?.embeddingModelId ?? 'sentence-transformers/all-MiniLM-L6-v2'
    );
  }

  /**
   * Set the embedding model ID for the active project
   * This will trigger a reindex if the model changed
   */
  async function setEmbeddingModelId(modelId: EmbeddingModelId): Promise<void> {
    if (!activeProject.value) {
      throw new Error('No active project');
    }

    const oldModelId =
      activeProject.value.settings?.embeddingModelId ?? 'sentence-transformers/all-MiniLM-L6-v2';
    const modelChanged = oldModelId !== modelId;

    const updated = await updateCompanionProject(activeProject.value.id, {
      settings: {
        ...activeProject.value.settings,
        embeddingModelId: modelId,
      },
    });

    activeProject.value = updated;
    projects.value = await listCompanionProjects();

    // If model changed and we have an index, trigger reindex
    if (modelChanged && activeProject.value.id) {
      const indexingStore = useIndexingStore();
      await indexingStore.reindex(activeProject.value.id);
    }
  }

  /**
   * Resolve a workspace path to folder, relative path, and absolute path.
   * Workspace paths are in format: folderId/relativePath
   * For root folders, path === folderId
   */
  function resolveWorkspacePath(workspacePath: string): {
    folder: ProjectFolderRecord;
    relativePath: string;
    absolutePath: string;
  } | null {
    if (!activeProject.value) {
      return null;
    }

    const parts = workspacePath.split('/');
    const folderIdentifier = parts[0];

    if (!folderIdentifier) {
      return null;
    }

    // Resolve folder identifier (UUID or folder name) to folder ID
    const rootFolderId = resolveFolderId(folderIdentifier, activeProject.value.folders);
    if (!rootFolderId) {
      return null;
    }

    const folder = activeProject.value.folders.find((f) => f.id === rootFolderId);
    if (!folder) {
      return null;
    }

    // Build relative path from folder root
    const relativeParts = parts.slice(1);
    let relativePath = relativeParts.join('/');

    // For root folder, relative path is empty (or '.')
    if (workspacePath === folder.id) {
      relativePath = '.';
    }

    // Build absolute path
    const normalizedSystemPath = folder.systemPath.replace(/\\/g, '/');
    const absolutePath =
      relativePath === '.' || relativePath === ''
        ? normalizedSystemPath
        : `${normalizedSystemPath}/${relativePath}`.replace(/\/+/g, '/');

    return {
      folder,
      relativePath: relativePath === '.' ? '.' : relativePath,
      absolutePath,
    };
  }

  /**
   * Resolve an absolute system path to editor's folder-based path format: {folderId}/{relativePath}
   * Returns null if the path is not under any project folder.
   */
  function resolveAbsolutePath(absolutePath: string): string | null {
    if (!activeProject.value) {
      return null;
    }

    // Normalize the absolute path (handle both / and \ separators)
    const normalizedAbsolutePath = absolutePath.replace(/\\/g, '/');

    // Check each project folder to see if the absolute path is under it
    for (const folder of activeProject.value.folders) {
      const normalizedFolderPath = folder.systemPath.replace(/\\/g, '/');

      // Check if the absolute path starts with the folder's system path
      if (
        normalizedAbsolutePath.startsWith(normalizedFolderPath + '/') ||
        normalizedAbsolutePath === normalizedFolderPath
      ) {
        // Calculate relative path
        const relativePath =
          normalizedAbsolutePath === normalizedFolderPath
            ? ''
            : normalizedAbsolutePath.slice(normalizedFolderPath.length + 1);

        // Return in editor format: {folderId}/{relativePath}
        return relativePath ? `${folder.id}/${relativePath}` : folder.id;
      }
    }

    // Path is not under any project folder
    return null;
  }

  /**
   * Copy absolute path to clipboard
   */
  function copyAbsolutePath(workspacePath: string): string {
    const resolved = resolveWorkspacePath(workspacePath);
    if (!resolved) {
      throw new Error('Failed to resolve workspace path');
    }
    return resolved.absolutePath;
  }

  /**
   * Copy relative path to clipboard (including root folder name)
   */
  function copyRelativePath(workspacePath: string): string {
    const resolved = resolveWorkspacePath(workspacePath);
    if (!resolved) {
      throw new Error('Failed to resolve workspace path');
    }

    if (resolved.relativePath === '.' || resolved.relativePath === '') {
      return resolved.folder.name;
    }

    return `${resolved.folder.name}/${resolved.relativePath}`;
  }

  /**
   * Delete a file or directory at the given workspace path
   */
  async function deletePath(workspacePath: string, opts: { recursive: boolean }): Promise<void> {
    const resolved = resolveWorkspacePath(workspacePath);
    if (!resolved) {
      throw new Error('Failed to resolve workspace path');
    }

    const companionStore = useLocalCompanionStore();
    const response = await companionStore.request<{
      success: boolean;
      result?: {
        path: string;
        deleted: boolean;
        needsReindex?: boolean;
      };
      error?: string;
    }>('execute_tool', {
      tool: 'delete_path',
      args: {
        path: resolved.absolutePath,
        recursive: opts.recursive,
      },
      projectRoot: resolved.folder.systemPath,
    });

    if (!response.success) {
      throw new Error(response.error ?? 'Failed to delete path');
    }

    // If needsReindex flag is set, trigger a full reindex
    if (response.result?.needsReindex && activeProject.value) {
      const indexingStore = useIndexingStore();
      await indexingStore.reindex(activeProject.value.id);
    }
  }

  /**
   * Get file content from git HEAD (or specified ref)
   */
  async function getGitHeadContent(
    workspacePath: string,
    ref: string = 'HEAD',
  ): Promise<{ baseContent: string; baseRef: string; existsInRef: boolean }> {
    const resolved = resolveWorkspacePath(workspacePath);
    if (!resolved) {
      throw new Error('Failed to resolve workspace path');
    }

    // Only works for files
    if (resolved.relativePath === '.' || resolved.relativePath.endsWith('/')) {
      throw new Error('Git diff is only available for files, not directories');
    }

    const companionStore = useLocalCompanionStore();
    const response = await companionStore.request<{
      success: boolean;
      result?: {
        content: string;
        ref: string;
        existsInRef: boolean;
      };
      error?: string;
    }>('execute_tool', {
      tool: 'git_read_file_at_ref',
      args: {
        path: resolved.absolutePath,
        ref,
      },
      projectRoot: resolved.folder.systemPath,
    });

    if (!response.success) {
      throw new Error(response.error ?? 'Failed to read file from git');
    }

    if (!response.result) {
      throw new Error('No result returned from git_read_file_at_ref');
    }

    return {
      baseContent: response.result.content,
      baseRef: response.result.ref,
      existsInRef: response.result.existsInRef,
    };
  }

  function reset() {
    fileTree.value = [];
    isLoading.value = false;
    projects.value = [];
    activeProject.value = null;
    folderRuntimeState.value = {};
  }

  return {
    fileTree,
    isLoading,
    projects,
    activeProject,
    activeProjectId,
    folderRuntimeState,
    showHiddenFiles,
    hasActiveProject,
    hasFolders,
    hasConnectedFolders,
    initialize,
    createProject,
    setActiveProject,
    renameActiveProject,
    deleteProjectById,
    addFolder,
    removeFolder,
    reconnectFolder,
    refreshFolderPermissions,
    refreshFileTree,
    toggleHiddenFiles,
    readFile,
    writeFile,
    readFileForEditor,
    writeFileForEditor,
    readAbsoluteFileForEditor,
    readFileRange,
    getEmbeddingModelId,
    setEmbeddingModelId,
    resolveWorkspacePath,
    copyAbsolutePath,
    copyRelativePath,
    resolveAbsolutePath,
    deletePath,
    getGitHeadContent,
    reset,
  };
});
