import { defineStore } from 'pinia';
import { ref, computed } from 'vue';
import { indexOrchestrator } from '../core/indexing/IndexOrchestrator';
import { useProjectStore } from './project';
import { useLocalCompanionStore } from './localCompanion';
import { loadIndexMetadata } from '../core/indexing/persistence';
import { getMemoryUsage } from '../core/indexing/utils';
import type { IndexingProgress } from '../core/indexing/types';
import type { ProjectId } from '../core/types';

export type TriggerReason = 'manual' | 'folder-add' | 'file-change' | 'startup';

export interface IndexStats {
  fileCount: number;
  symbolCount: number;
  chunkCount: number;
  vectorCount: number;
  lastUpdated: number;
  version: number;
}

export const useIndexingStore = defineStore('indexing', () => {
  const progress = ref<IndexingProgress | null>(null);
  const isIndexing = ref(false);
  const lastTriggerReason = ref<TriggerReason | null>(null);
  const indexStats = ref<IndexStats | null>(null);
  // Queue for folder-add requests that arrive while indexing is in progress
  const pendingFolderAddByProjectId = ref<Set<ProjectId>>(new Set());

  function initialize() {
    // Subscribe to progress updates
    indexOrchestrator.onProgress((prog) => {
      progress.value = prog;
      isIndexing.value = prog.phase !== 'complete' && prog.phase !== 'error';

      // Update stats when indexing completes
      if (prog.phase === 'complete') {
        void loadStats();

        // Drain queued folder-add requests for the active project
        const projectStore = useProjectStore();
        const activeProjectId = projectStore.activeProjectId;
        if (activeProjectId && pendingFolderAddByProjectId.value.has(activeProjectId)) {
          pendingFolderAddByProjectId.value.delete(activeProjectId);
          // Schedule in microtask to ensure indexing state is fully cleared
          void Promise.resolve().then(() => {
            void triggerIndexing(activeProjectId, 'folder-add');
          });
        }
      } else if (prog.phase === 'error') {
        // Drop queued folder-add requests on error/cancel
        pendingFolderAddByProjectId.value.clear();
      }
    });

    // Load initial stats - show loading state while checking
    progress.value = {
      phase: 'loading',
      filesProcessed: 0,
      totalFiles: 0,
    };
    void loadStats().then(() => {
      // After loading stats, check if we have an index and update progress accordingly
      const projectStore = useProjectStore();
      const projectId = projectStore.activeProjectId;
      if (projectId && indexStats.value) {
        progress.value = {
          phase: 'complete',
          filesProcessed: indexStats.value.fileCount,
          totalFiles: indexStats.value.fileCount,
        };
      } else if (projectId) {
        // No index found - clear progress so status bar shows re-index button
        progress.value = null;
      }
    });
  }

  async function loadStats() {
    const projectStore = useProjectStore();
    const projectId = projectStore.activeProjectId;

    if (!projectId) {
      indexStats.value = null;
      return;
    }

    try {
      const metadata = await loadIndexMetadata(projectId);
      if (metadata) {
        indexStats.value = {
          fileCount: metadata.manifest.fileCount,
          symbolCount: metadata.manifest.symbolCount,
          chunkCount: metadata.manifest.chunkCount,
          vectorCount: metadata.manifest.chunkCount, // Vectors match chunks
          lastUpdated: metadata.manifest.updatedAt,
          version: metadata.manifest.version,
        };
      } else {
        indexStats.value = null;
      }
    } catch (error) {
      console.error('Failed to load index stats:', error);
      indexStats.value = null;
    }
  }

  const memoryUsage = computed(() => {
    const mem = getMemoryUsage();
    return {
      ...mem,
      percentage: mem.available ? (mem.used / mem.limit) * 100 : 0,
    };
  });

  // Centralized indexing status computed properties
  const isProcessing = computed(() => {
    if (!progress.value) return false;
    return ['loading', 'scanning', 'parsing', 'embedding'].includes(progress.value.phase);
  });

  const statusText = computed(() => {
    if (!progress.value) return null;

    const { phase, filesProcessed, totalFiles } = progress.value;

    switch (phase) {
      case 'loading':
        return 'Loading index...';
      case 'scanning':
        return 'Scanning...';
      case 'parsing':
      case 'embedding':
        if (totalFiles > 0) {
          const percent = Math.round((filesProcessed / totalFiles) * 100);
          return `${phase === 'parsing' ? 'Parsing' : 'Indexing'} ${percent}%`;
        }
        return phase === 'parsing' ? 'Parsing...' : 'Indexing...';
      case 'paused':
        return 'Paused';
      case 'complete':
        return 'Indexed';
      case 'error':
        return 'Error';
      default:
        return null;
    }
  });

  const statusIcon = computed(() => {
    if (!progress.value) return 'search';

    switch (progress.value.phase) {
      case 'loading':
      case 'scanning':
      case 'parsing':
      case 'embedding':
        return 'sync';
      case 'paused':
        return 'pause';
      case 'complete':
        return 'check_circle';
      case 'error':
        return 'error';
      default:
        return 'search';
    }
  });

  const statusTooltip = computed(() => {
    if (!progress.value) return 'Index Status';

    const { phase, filesProcessed, totalFiles, error } = progress.value;

    if (error) return `Error: ${error}`;

    switch (phase) {
      case 'loading':
        return 'Loading index from storage...';
      case 'scanning':
        return 'Scanning project files...';
      case 'parsing':
        return `Parsing files: ${filesProcessed}/${totalFiles}`;
      case 'embedding':
        return `Generating embeddings: ${filesProcessed}/${totalFiles}`;
      case 'paused':
        return 'Indexing paused - Click to view';
      case 'complete':
        return `Index complete: ${totalFiles} files`;
      default:
        return 'Index Status';
    }
  });

  const statusClass = computed(() => {
    if (!progress.value) return '';

    switch (progress.value.phase) {
      case 'loading':
      case 'scanning':
      case 'parsing':
      case 'embedding':
        return 'status-primary';
      case 'paused':
        return 'status-warning';
      case 'complete':
        return 'status-positive';
      case 'error':
        return 'status-negative';
      default:
        return '';
    }
  });

  /**
   * Wait for companion connection with timeout
   * Returns true if connected, false if timeout or error
   */
  async function waitForCompanionConnection(timeoutMs: number = 5000): Promise<boolean> {
    const companionStore = useLocalCompanionStore();

    // If already connected, return immediately
    if (companionStore.isConnected) {
      return true;
    }

    // Try to connect if not already connecting
    if (!companionStore.isConnecting) {
      await companionStore.connect();
    }

    // Wait for connection with timeout
    const startTime = Date.now();
    while (!companionStore.isConnected && Date.now() - startTime < timeoutMs) {
      await new Promise((resolve) => setTimeout(resolve, 100));
    }

    return companionStore.isConnected;
  }

  async function triggerIndexing(projectId: string, reason: TriggerReason = 'startup') {
    const projectStore = useProjectStore();
    const project = projectStore.activeProject;

    if (!project || project.id !== projectId) {
      return;
    }

    // Wait for companion connection before checking index status
    // This prevents false "no index" results when companion isn't connected yet
    const isConnected = await waitForCompanionConnection(5000);
    if (!isConnected) {
      console.warn(
        `Indexing skipped for project ${projectId}: Companion not connected after timeout. ` +
        `Index status check requires companion connection.`
      );
      return;
    }

    lastTriggerReason.value = reason;

    // For folder-add, only index newly connected folders that haven't been indexed yet
    if (reason === 'folder-add') {
      // If indexing is already in progress, enqueue this request instead of throwing
      if (indexOrchestrator.isIndexing() || isIndexing.value) {
        pendingFolderAddByProjectId.value.add(projectId);
        return;
      }

      const existingIndex = await indexOrchestrator.ensureIndexLoaded(projectId);

      if (!existingIndex) {
        // No index exists, build full index
        await indexOrchestrator.buildIndex(
          projectId,
          project.folders,
          projectStore.showHiddenFiles,
        );
      } else {
        // Find folders that are connected but not yet indexed
        const indexedFolderIds = new Set(existingIndex.metadata.indexedFolderIds ?? []);
        const foldersToIndex = project.folders.filter((folder) => {
          const runtime = projectStore.folderRuntimeState[folder.id];
          const isConnected = runtime?.connected === true;
          const isIndexed = indexedFolderIds.has(folder.id);
          return isConnected && !isIndexed;
        });

        if (foldersToIndex.length > 0) {
          // Incrementally index only the new folders
          await indexOrchestrator.indexFolders(
            projectId,
            foldersToIndex,
            projectStore.showHiddenFiles,
          );
        }
        // If foldersToIndex is empty, all connected folders are already indexed
      }

      await loadStats();
      return;
    }

    // Show loading state while checking for existing index
    progress.value = {
      phase: 'loading',
      filesProcessed: 0,
      totalFiles: 0,
    };

    // Check if index exists
    const existingIndex = await indexOrchestrator.ensureIndexLoaded(projectId);

    // Check for embedding model mismatch
    const modelMismatch = await indexOrchestrator.checkModelMismatch(projectId);

    if (!existingIndex || modelMismatch) {
      // Build new index (or rebuild if model mismatch)
      if (modelMismatch) {
        // Model changed, need full reindex
        await indexOrchestrator.reindexAll(
          projectId,
          project.folders,
          projectStore.showHiddenFiles,
        );
      } else {
        // Build new index
        await indexOrchestrator.buildIndex(
          projectId,
          project.folders,
          projectStore.showHiddenFiles,
        );
      }
      await loadStats();
    } else {
      // Index exists and no mismatch - load stats and set progress to complete so status bar shows "Indexed"
      await loadStats();
      // Set progress to complete state so status bar displays "Indexed" in green
      if (existingIndex) {
        progress.value = {
          phase: 'complete',
          filesProcessed: existingIndex.metadata.manifest.fileCount,
          totalFiles: existingIndex.metadata.manifest.fileCount,
        };
      } else if (indexStats.value) {
        // Fallback: use stats if index data not available
        progress.value = {
          phase: 'complete',
          filesProcessed: indexStats.value.fileCount,
          totalFiles: indexStats.value.fileCount,
        };
      }
    }
  }

  async function reindex(projectId: string) {
    const projectStore = useProjectStore();
    const project = projectStore.activeProject;
    if (!project || project.id !== projectId) {
      return;
    }

    lastTriggerReason.value = 'manual';

    await indexOrchestrator.reindexAll(projectId, project.folders, projectStore.showHiddenFiles);
    await loadStats();
  }

  function pauseIndexing() {
    indexOrchestrator.pause();
  }

  function resumeIndexing() {
    indexOrchestrator.resume();
  }

  function cancelIndexing() {
    indexOrchestrator.cancel();
  }

  async function incrementalIndex(projectId: string, filePath: string, changeType: string) {
    const projectStore = useProjectStore();
    const project = projectStore.activeProject;

    if (!project || project.id !== projectId) {
      return;
    }

    // Wait for companion connection
    const isConnected = await waitForCompanionConnection(5000);
    if (!isConnected) {
      console.warn('Companion not connected, skipping incremental indexing');
      return;
    }

    // Map workspace path to system path and folder info
    const pathParts = filePath.split('/');
    if (pathParts.length === 0) {
      return;
    }

    const folderIdentifier = pathParts[0];
    const folder = project.folders.find((f) => f.id === folderIdentifier);
    if (!folder || !folder.systemPath) {
      return;
    }

    // Build system path
    const relativeParts = pathParts.slice(1);
    const relativePath = relativeParts.join('/');
    const systemPath = relativePath
      ? `${folder.systemPath}/${relativePath}`.replace(/\/+/g, '/')
      : folder.systemPath;

    const companionStore = useLocalCompanionStore();

    try {
      if (changeType === 'deleted') {
        // File was deleted
        await companionStore.request('index_update_files', {
          projectId,
          changedFiles: [],
          deletedFiles: [filePath],
          embeddingModelId: projectStore.getEmbeddingModelId(),
          hfToken: companionStore.huggingFaceToken || undefined,
        });
      } else {
        // File was created or modified - server will read content from systemPath
        await companionStore.request('index_update_files', {
          projectId,
          changedFiles: [
            {
              filePath,
              systemPath,
              folderId: folder.id,
            },
          ],
          deletedFiles: [],
          embeddingModelId: projectStore.getEmbeddingModelId(),
          hfToken: companionStore.huggingFaceToken || undefined,
        });
      }

      // Reload stats after update
      await loadStats();
    } catch (error) {
      console.error('Failed to perform incremental indexing:', error);
    }
  }

  return {
    progress,
    isIndexing,
    lastTriggerReason,
    indexStats,
    memoryUsage,
    isProcessing,
    statusText,
    statusIcon,
    statusTooltip,
    statusClass,
    initialize,
    triggerIndexing,
    reindex,
    pauseIndexing,
    resumeIndexing,
    cancelIndexing,
    loadStats,
    incrementalIndex,
  };
});
