import type { ProjectId, ProjectFolderId, ProjectFolderRecord } from '../types';
import { loadIndex, deleteIndex } from './persistence';
import type { IndexData, Symbol, GraphEdge, CodeChunk, IndexingProgress } from './types';
import { hashContent } from './utils';
import { embeddingManager } from './embeddings/EmbeddingManager';
import { useProjectStore } from '../../stores/project';
import { useLocalCompanionStore } from '../../../../stores/localCompanion';

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
 * Check if a file path belongs to a folder (handles both UUID and folder name formats)
 */
function _filePathBelongsToFolder(
  filePath: string,
  folderId: ProjectFolderId,
  folderName: string,
): boolean {
  const pathParts = filePath.split('/');
  if (!pathParts.length) {
    return false;
  }

  const firstPart = pathParts[0];
  if (!firstPart) {
    return false;
  }

  // Check if it's a UUID (legacy format: 8-4-4-4-12 hex digits)
  const uuidPattern = /^[\w-]{8}-[\w-]{4}-[\w-]{4}-[\w-]{4}-[\w-]{12}$/;
  if (uuidPattern.test(firstPart)) {
    // Legacy format: compare with folder ID
    return firstPart === folderId;
  }

  // New format: compare with sanitized folder name
  const sanitizedName = sanitizeFolderName(folderName);
  return firstPart === sanitizedName;
}

type ProgressCallback = (progress: IndexingProgress) => void;

export class IndexOrchestrator {
  private currentProjectId: ProjectId | null = null;
  private indexingInProgress = false;
  private indexingPaused = false;
  private indexingCancelled = false;
  private progressCallbacks: Set<ProgressCallback> = new Set();

  constructor() {
    // Companion handles all parsing
  }

  /**
   * Parse file using companion - requires companion connection
   */
  private async parseFileWithCompanion(
    filePath: string,
    content: string,
    language: string,
  ): Promise<{ symbols: Symbol[]; edges: GraphEdge[]; chunks: CodeChunk[] }> {
    const companionStore = useLocalCompanionStore();
    if (!companionStore.isConnected) {
      throw new Error(
        'Local companion connection required for parsing. Please ensure the companion server is running.',
      );
    }

    const response = await companionStore.request<{
      symbols: Symbol[];
      edges: GraphEdge[];
      chunks: Array<CodeChunk & { content?: string }>;
      error?: string;
    }>('parse_request', {
      filePath,
      content,
      language,
    });

    if (response.error) {
      throw new Error(`Companion Parse Error: ${response.error}`);
    }

    // We need to re-hash the content in the frontend to ensure consistency
    // as the Python side might not use exactly the same hashing algorithm
    const chunks = response.chunks.map((c) => {
      const chunkContent = c.content || '';
      const { content: _content, ...chunkWithoutContent } = c;
      return {
        ...chunkWithoutContent,
        contentHash: hashContent(chunkContent),
        preview: chunkContent.slice(0, 500),
      };
    });

    return {
      symbols: response.symbols,
      edges: response.edges,
      chunks: chunks as CodeChunk[],
    };
  }

  onProgress(callback: ProgressCallback): () => void {
    this.progressCallbacks.add(callback);
    return () => {
      this.progressCallbacks.delete(callback);
    };
  }

  private notifyProgress(progress: IndexingProgress): void {
    for (const callback of this.progressCallbacks) {
      callback(progress);
    }
  }

  async ensureIndexLoaded(projectId: ProjectId): Promise<IndexData | null> {
    this.currentProjectId = projectId;
    return await loadIndex(projectId);
  }

  pause(): void {
    this.indexingPaused = true;
    this.notifyProgress({
      phase: 'paused',
      filesProcessed: 0,
      totalFiles: 0,
      pausedReason: 'user',
    });
  }

  resume(): void {
    this.indexingPaused = false;
  }

  cancel(): void {
    this.indexingCancelled = true;
    this.indexingPaused = false;
  }

  cancelForProject(projectId: ProjectId): void {
    if (this.currentProjectId === projectId) {
      this.cancel();
    }
  }

  async waitForIndexingToFinish(maxWaitMs: number = 5000): Promise<void> {
    if (!this.indexingInProgress) {
      return;
    }

    const startTime = Date.now();
    while (this.indexingInProgress && Date.now() - startTime < maxWaitMs) {
      await new Promise((resolve) => setTimeout(resolve, 100));
    }
  }

  isIndexingForProject(projectId: ProjectId): boolean {
    return this.indexingInProgress && this.currentProjectId === projectId;
  }

  async buildIndex(
    projectId: ProjectId,
    folders: ProjectFolderRecord[],
    showHiddenFiles: boolean,
  ): Promise<void> {
    if (this.indexingInProgress) {
      throw new Error('Indexing already in progress');
    }

    this.indexingInProgress = true;
    this.indexingPaused = false;
    this.indexingCancelled = false;
    this.currentProjectId = projectId;

    const companionStore = useLocalCompanionStore();
    const projectStore = useProjectStore();

    // Use companion indexing if available
    if (companionStore.isConnected && folders.every((f) => f.systemPath)) {
      try {
        // Set up progress listener for WebSocket messages
        // Note: Progress updates come as separate 'index_progress' messages
        // The store will need to handle these and forward to IndexOrchestrator

        // Start indexing via companion (this is async and sends progress via WebSocket)
        const buildPromise = companionStore.request<{
          success: boolean;
          error?: string;
        }>(
          'index_build',
          {
            projectId,
            folders: folders.map((f) => ({
              id: f.id,
              name: f.name,
              path: f.systemPath,
            })),
            showHidden: showHiddenFiles,
            embeddingModelId: projectStore.getEmbeddingModelId(),
            hfToken: companionStore.huggingFaceToken || undefined,
          },
          (progress: unknown) => {
            // Forward progress updates to IndexOrchestrator
            if (progress && typeof progress === 'object' && 'phase' in progress) {
              this.notifyProgress(progress as IndexingProgress);
            }
          },
        );

        // Wait for build to complete
        const response = await buildPromise;

        if (!response.success) {
          throw new Error(response.error ?? 'Indexing failed');
        }

        // Progress updates are handled via WebSocket 'index_progress' messages
        // The localCompanion store should forward these to IndexOrchestrator
        // For now, we'll mark as complete when the build finishes
        this.notifyProgress({
          phase: 'complete',
          filesProcessed: 0,
          totalFiles: 0,
        });

        this.indexingInProgress = false;
        return;
      } catch (error) {
        console.error('Companion indexing failed:', error);
        this.indexingInProgress = false;
        this.notifyProgress({
          phase: 'error',
          filesProcessed: 0,
          totalFiles: 0,
          error: error instanceof Error ? error.message : 'Unknown error',
        });
        throw error;
      }
    }

    // Companion indexing is required - no browser fallback
    this.indexingInProgress = false;
    throw new Error(
      'Local companion connection required for indexing. Please ensure the companion server is running and folders have systemPath set.',
    );
  }

  // enumerateFiles is no longer used - companion handles file enumeration
  // Method signature kept for type compatibility but implementation removed
  private enumerateFiles(): Promise<void> {
    throw new Error('enumerateFiles is no longer used - companion handles file enumeration');
  }

  /**
   * Check if index needs to be rebuilt due to embedding model mismatch
   */
  async checkModelMismatch(projectId: ProjectId): Promise<boolean> {
    const indexData = await loadIndex(projectId);
    if (!indexData) {
      return false; // No index, no mismatch
    }

    const projectStore = useProjectStore();
    const currentModelId = projectStore.getEmbeddingModelId();

    const manifest = indexData.metadata.manifest;
    // Index version mismatch: force rebuild (e.g. vector persistence format fixes)
    if ((manifest.version ?? 0) < 2) {
      return true;
    }

    // Check model ID mismatch first
    if (manifest.embeddingModelId && manifest.embeddingModelId !== currentModelId) {
      return true; // Model ID mismatch - definitely need to rebuild
    }

    // If model IDs match, trust the manifest dimension (it was set when index was created)
    // Don't check against currentDim because it might have a default value before
    // the actual dimension is known, causing false positives on reload
    // Only check dimension if model ID is missing (legacy index)
    if (!manifest.embeddingModelId) {
      const currentDim = embeddingManager.getDimension(projectId);
      if (manifest.embeddingDim && manifest.embeddingDim !== currentDim) {
        return true; // Dimension mismatch for legacy index
      }
    }

    return false;
  }

  updateFile(_projectId: ProjectId, _filePath: string, _content: string): void {
    // File updates are handled by companion's file watching system
    // This method is kept for compatibility but companion handles incremental updates automatically
    const companionStore = useLocalCompanionStore();
    if (!companionStore.isConnected) {
      throw new Error(
        'Local companion connection required for file updates. Please ensure the companion server is running.',
      );
    }
    // Companion handles file watching and incremental indexing automatically
    // No action needed here - companion will detect file changes and update the index
  }

  removeFile(_projectId: ProjectId, _filePath: string): void {
    // File deletions are handled by companion's file watching system
    // This method is kept for compatibility but companion handles deletions automatically
    const companionStore = useLocalCompanionStore();
    if (!companionStore.isConnected) {
      throw new Error(
        'Local companion connection required for file updates. Please ensure the companion server is running.',
      );
    }
    // Companion handles file watching and detects deletions automatically
    // No action needed here - companion will detect file deletions and update the index
  }

  async pruneIgnored(
    _projectId: ProjectId,
    _folders: ProjectFolderRecord[],
    _showHiddenFiles: boolean,
  ): Promise<void> {
    // Ignore evaluation is handled by companion during indexing
    // This method is kept for compatibility but is a no-op
    // Companion indexing handles ignore patterns server-side automatically
  }

  /**
   * Incrementally index only the specified folders (append to existing index)
   * Removes any existing data for these folders first, then adds new data
   *
   * Note: Incremental indexing now requires companion.
   */
  async indexFolders(
    projectId: ProjectId,
    foldersToIndex: ProjectFolderRecord[],
    showHiddenFiles: boolean,
  ): Promise<void> {
    if (this.indexingInProgress) {
      throw new Error('Indexing already in progress');
    }

    this.indexingInProgress = true;
    this.indexingPaused = false;
    this.indexingCancelled = false;
    this.currentProjectId = projectId;

    const companionStore = useLocalCompanionStore();
    const projectStore = useProjectStore();

    // Use companion indexing if available
    if (companionStore.isConnected && foldersToIndex.every((f) => f.systemPath)) {
      try {
        // Start incremental folder indexing via companion
        const indexPromise = companionStore.request<{
          success: boolean;
          error?: string;
        }>(
          'index_folders',
          {
            projectId,
            folders: foldersToIndex.map((f) => ({
              id: f.id,
              name: f.name,
              path: f.systemPath,
            })),
            showHidden: showHiddenFiles,
            embeddingModelId: projectStore.getEmbeddingModelId(),
            hfToken: companionStore.huggingFaceToken || undefined,
          },
          (progress: unknown) => {
            // Forward progress updates to IndexOrchestrator
            if (progress && typeof progress === 'object' && 'phase' in progress) {
              this.notifyProgress(progress as IndexingProgress);
            }
          },
        );

        // Wait for indexing to complete
        const response = await indexPromise;

        if (!response.success) {
          throw new Error(response.error ?? 'Indexing failed');
        }

        // Progress updates are handled via WebSocket 'index_progress' messages
        // The localCompanion store should forward these to IndexOrchestrator
        // For now, we'll mark as complete when the indexing finishes
        this.notifyProgress({
          phase: 'complete',
          filesProcessed: 0,
          totalFiles: 0,
        });

        this.indexingInProgress = false;
        return;
      } catch (error) {
        console.error('Companion folder indexing failed:', error);
        this.indexingInProgress = false;
        this.notifyProgress({
          phase: 'error',
          filesProcessed: 0,
          totalFiles: 0,
          error: error instanceof Error ? error.message : 'Unknown error',
        });
        throw error;
      }
    }

    // Companion indexing is required - no browser fallback
    this.indexingInProgress = false;
    throw new Error(
      'Local companion connection required for indexing. Please ensure the companion server is running and folders have systemPath set.',
    );
  }

  /**
   * Remove a specific folder's data from the index (without reindexing other folders)
   * Companion handles folder management automatically - this method delegates to companion
   */
  removeFolderFromIndex(_projectId: ProjectId, _folderId: ProjectFolderId): void {
    const companionStore = useLocalCompanionStore();
    if (!companionStore.isConnected) {
      throw new Error(
        'Local companion connection required for folder management. Please ensure the companion server is running.',
      );
    }
    // Companion handles folder removal automatically during indexing
    // If needed, we could add a companion RPC call here, but companion's indexing
    // system handles folder changes automatically
  }

  async reindexAll(
    projectId: ProjectId,
    folders: ProjectFolderRecord[],
    showHiddenFiles: boolean,
  ): Promise<void> {
    await deleteIndex(projectId);
    await this.buildIndex(projectId, folders, showHiddenFiles);
  }

  isIndexing(): boolean {
    return this.indexingInProgress;
  }
}

// Singleton instance
export const indexOrchestrator = new IndexOrchestrator();
