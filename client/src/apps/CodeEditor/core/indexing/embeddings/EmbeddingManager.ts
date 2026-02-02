import type { ProjectId, EmbeddingModelId } from '../../types';
import { useProjectStore } from '../../../stores/project';
import { useLocalCompanionStore } from '../../../../../stores/localCompanion';
import type { EmbeddingProvider } from './EmbeddingProvider';
import { LocalCompanionEmbeddingProvider } from './LocalCompanionEmbeddingProvider';

/**
 * Central embedding manager - single entrypoint for all embedding operations
 * Ensures all embeddings use the project's configured model
 */
export class EmbeddingManager {
  private static instance: EmbeddingManager | null = null;
  private providers: Map<string, EmbeddingProvider> = new Map();

  private constructor() {
    // Private constructor for singleton
  }

  static getInstance(): EmbeddingManager {
    if (!EmbeddingManager.instance) {
      EmbeddingManager.instance = new EmbeddingManager();
    }
    return EmbeddingManager.instance;
  }

  /**
   * Get or create provider for a specific model ID
   * Requires companion connection - throws error if not connected
   */
  private getProvider(modelId: EmbeddingModelId): EmbeddingProvider {
    const companionStore = useLocalCompanionStore();
    if (!companionStore.isConnected) {
      throw new Error(
        'Local companion connection required for embeddings. Please ensure the companion server is running.',
      );
    }

    const key = `${modelId}:companion`;
    let provider = this.providers.get(key);

    if (!provider) {
      provider = new LocalCompanionEmbeddingProvider(modelId);
      this.providers.set(key, provider);
    }
    return provider;
  }

  /**
   * Get the provider for the active project's embedding model
   */
  private getProjectProvider(_projectId: ProjectId): EmbeddingProvider {
    const projectStore = useProjectStore();
    const modelId = projectStore.getEmbeddingModelId();
    return this.getProvider(modelId);
  }

  /**
   * Embed a single query text for semantic search
   * Requires companion connection
   */
  async embedQuery(projectId: ProjectId, query: string): Promise<Float32Array> {
    const provider = this.getProjectProvider(projectId);
    return await provider.embed(query);
  }

  /**
   * Embed multiple texts (for indexing chunks)
   * Requires companion connection
   */
  async embedTexts(projectId: ProjectId, texts: string[]): Promise<Float32Array[]> {
    const provider = this.getProjectProvider(projectId);
    return await provider.embedBatch(texts);
  }

  /**
   * Get embedding dimension for the active project's model
   * Requires companion connection
   */
  getDimension(projectId: ProjectId): number {
    const provider = this.getProjectProvider(projectId);
    return provider.getDimension();
  }

  /**
   * Get the model ID used for a project
   */
  getModelId(_projectId: ProjectId): EmbeddingModelId {
    const projectStore = useProjectStore();
    return projectStore.getEmbeddingModelId();
  }

  /**
   * Cleanup: dispose all providers
   */
  dispose(): void {
    // LocalCompanionEmbeddingProvider doesn't need disposal
    this.providers.clear();
  }
}

// Singleton instance export
export const embeddingManager = EmbeddingManager.getInstance();
