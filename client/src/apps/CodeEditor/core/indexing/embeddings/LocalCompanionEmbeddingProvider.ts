import type { EmbeddingProvider } from './EmbeddingProvider';
import type { EmbeddingModelId } from '../../types';
import { useLocalCompanionStore } from '../../../../../stores/localCompanion';

/**
 * Embedding provider that routes requests to the local Python companion server
 */
export class LocalCompanionEmbeddingProvider implements EmbeddingProvider {
  readonly id: EmbeddingModelId;
  private dim: number | null = null;

  constructor(modelId: EmbeddingModelId) {
    this.id = modelId;
  }

  getDimension(): number {
    if (this.dim !== null) return this.dim;

    // Default dimensions for known models
    switch (this.id) {
      case 'microsoft/codebert-base':
        return 768;
      default:
        return 384;
    }
  }

  async embed(text: string): Promise<Float32Array> {
    const companionStore = useLocalCompanionStore();
    const response = await companionStore.request<{
      embedding: number[];
      dim: number;
      error?: string;
    }>('embedding_request', {
      modelId: this.id,
      text,
      hfToken: companionStore.huggingFaceToken || undefined,
    });

    if (response.error) {
      throw new Error(`COMPANION_EMBEDDING_FAILED: ${response.error}`);
    }

    this.dim = response.dim;
    return new Float32Array(response.embedding);
  }

  async embedBatch(texts: string[]): Promise<Float32Array[]> {
    const companionStore = useLocalCompanionStore();
    const response = await companionStore.request<{
      embeddings: number[][];
      dim: number;
      error?: string;
    }>('embedding_batch_request', {
      modelId: this.id,
      texts,
      hfToken: companionStore.huggingFaceToken || undefined,
    });

    if (response.error) {
      // Instead of throwing, we'll let the EmbeddingManager handle the fallback
      // by throwing a special error that indicates companion failure
      throw new Error(`COMPANION_EMBEDDING_FAILED: ${response.error}`);
    }

    this.dim = response.dim;
    return response.embeddings.map((e) => new Float32Array(e));
  }
}
