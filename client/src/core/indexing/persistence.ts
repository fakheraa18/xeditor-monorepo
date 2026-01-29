import type { ProjectId } from '../types';
import { useLocalCompanionStore } from '../../stores/localCompanion';
import type {
  IndexData,
  IndexMetadata,
  Symbol,
  GraphEdge,
  CodeChunk,
} from './types';

// File constants are no longer used - companion handles all persistence

// Note: Index persistence is now handled by companion
// Save functions throw errors to indicate companion handles persistence

export function saveIndexMetadata(
  _projectId: ProjectId,
  _metadata: IndexMetadata,
): void {
  throw new Error('Index persistence is handled by companion. Direct saving is not supported.');
}

export async function loadIndexMetadata(
  projectId: ProjectId,
): Promise<IndexMetadata | null> {
  // Load from companion - requires connection
  const companionStore = useLocalCompanionStore();
  if (!companionStore.isConnected) {
    throw new Error('Local companion connection required to load index metadata. Please ensure the companion server is running.');
  }

  const response = await companionStore.request<{
    success: boolean;
    data?: IndexData;
    error?: string;
  }>('load_index_data', { id: projectId });

  if (response.success && response.data) {
    // response.data is IndexData, extract metadata
    return response.data.metadata;
  }

  return null;
}

export function saveSymbols(_projectId: ProjectId, _symbols: Symbol[]): void {
  throw new Error('Index persistence is handled by companion. Direct saving is not supported.');
}

export async function loadSymbols(projectId: ProjectId): Promise<Symbol[]> {
  // Load from companion index
  const indexData = await loadIndex(projectId);
  return indexData?.symbols ?? [];
}

export function saveEdges(_projectId: ProjectId, _edges: GraphEdge[]): void {
  throw new Error('Index persistence is handled by companion. Direct saving is not supported.');
}

export async function loadEdges(projectId: ProjectId): Promise<GraphEdge[]> {
  // Load from companion index
  const indexData = await loadIndex(projectId);
  return indexData?.edges ?? [];
}

export function saveChunks(_projectId: ProjectId, _chunks: CodeChunk[]): void {
  throw new Error('Index persistence is handled by companion. Direct saving is not supported.');
}

export async function loadChunks(projectId: ProjectId): Promise<CodeChunk[]> {
  // Load from companion index
  const indexData = await loadIndex(projectId);
  return indexData?.chunks ?? [];
}

// Vector storage is now handled by companion

export function saveVectors(
  _projectId: ProjectId,
  _vectors: Map<string, Float32Array>,
): void {
  throw new Error('Vector persistence is handled by companion. Direct saving is not supported.');
}

export function loadVectors(
  _projectId: ProjectId,
): Map<string, Float32Array> {
  throw new Error('Vector loading is handled by companion during retrieval. Direct loading is not supported.');
}

export function saveIndex(_projectId: ProjectId, _indexData: IndexData): void {
  throw new Error('Index persistence is handled by companion. Direct saving is not supported.');
}

export async function loadIndex(projectId: ProjectId): Promise<IndexData | null> {
  // Load from companion - requires connection
  const companionStore = useLocalCompanionStore();
  if (!companionStore.isConnected) {
    throw new Error('Local companion connection required to load index. Please ensure the companion server is running.');
  }

  // Load full index data from companion
  const response = await companionStore.request<{
    success: boolean;
    data?: IndexData;
    error?: string;
  }>('load_index_data', { id: projectId });

  if (response.success && response.data) {
    return response.data;
  }

  return null;
}

export async function deleteIndex(projectId: ProjectId): Promise<void> {
  // Delete via companion - requires connection
  const companionStore = useLocalCompanionStore();
  if (!companionStore.isConnected) {
    throw new Error('Local companion connection required to delete index. Please ensure the companion server is running.');
  }

  await companionStore.request('index_delete', { projectId });
}

