// Indexing Data Model Types

export type ChunkId = string;
export type SymbolId = string;
export type FilePath = string;

export type SymbolKind =
  | 'function'
  | 'class'
  | 'interface'
  | 'type'
  | 'variable'
  | 'constant'
  | 'method'
  | 'property'
  | 'enum'
  | 'namespace'
  | 'import'
  | 'export';

export type EdgeType = 'calls' | 'imports' | 'references' | 'extends' | 'implements' | 'uses';

export interface FileManifest {
  filePath: FilePath;
  language: string;
  size: number;
  lastModified: number;
  contentHash: string;
}

export interface SymbolRange {
  startLine: number;
  startColumn: number;
  endLine: number;
  endColumn: number;
}

export interface Symbol {
  symbolId: SymbolId;
  name: string;
  kind: SymbolKind;
  filePath: FilePath;
  range: SymbolRange;
  signature?: string;
  language: string;
  documentation?: string;
}

export interface GraphEdge {
  fromSymbolId: SymbolId;
  toSymbolId?: SymbolId;
  toName: string;
  edgeType: EdgeType;
  confidence: number;
}

export interface CodeChunk {
  chunkId: ChunkId;
  filePath: FilePath;
  startLine: number;
  endLine: number;
  preview: string; // First 300-600 chars for quick preview (not full content)
  contentHash: string; // Hash of full content for change detection
  symbolIds?: SymbolId[]; // Symbols defined in this chunk
}

export interface IndexManifest {
  projectId: string;
  version: number;
  createdAt: number;
  updatedAt: number;
  fileCount: number;
  symbolCount: number;
  chunkCount: number;
  embeddingModelId?: string; // Model used to generate embeddings
  embeddingDim?: number; // Dimension of embedding vectors
}

export interface IndexMetadata {
  manifest: IndexManifest;
  fileManifests: FileManifest[];
  indexedFolderIds?: string[]; // Root folder IDs that have been indexed (even if 0 files)
}

export interface IndexData {
  metadata: IndexMetadata;
  symbols: Symbol[];
  edges: GraphEdge[];
  chunks: CodeChunk[];
}

export interface IndexingProgress {
  phase: 'loading' | 'scanning' | 'parsing' | 'embedding' | 'complete' | 'error' | 'paused';
  currentFile?: FilePath;
  filesProcessed: number;
  totalFiles: number;
  error?: string;
  pausedReason?: 'memory' | 'user';
}

export interface SearchResult {
  chunkId: ChunkId;
  filePath: FilePath;
  startLine: number;
  endLine: number;
  preview: string;
  relevanceScore: number;
  matchType: 'symbol' | 'text' | 'semantic';
  matchedSymbols?: SymbolId[];
}
