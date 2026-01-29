// Embedding Provider Interface
// All embedding operations must go through a provider to ensure consistency

export interface EmbeddingProvider {
  /**
   * Unique identifier for this provider/model
   */
  readonly id: string;

  /**
   * Dimension of embeddings produced by this provider
   */
  getDimension(): number;

  /**
   * Embed a single text string
   */
  embed(text: string): Promise<Float32Array>;

  /**
   * Embed multiple text strings (batch operation)
   */
  embedBatch(texts: string[]): Promise<Float32Array[]>;
}

