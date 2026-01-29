import type { ProjectId, ProjectFolderId } from '../types';
import { loadIndex } from './persistence';
import type { SearchResult } from './types';
import { useLocalCompanionStore } from '../../stores/localCompanion';
import { useProjectStore } from '../../stores/project';

export class Retrieval {
  /**
   * Check if a filePath matches the folder scope
   * filePath format: "folderName/rel/path" (new) or "folderId/rel/path" (legacy)
   */
  private matchesFolderScope(filePath: string, folderIds?: ProjectFolderId[]): boolean {
    if (!folderIds || folderIds.length === 0) {
      return true; // No filter, match all
    }
    const pathParts = filePath.split('/');
    if (!pathParts.length) {
      return false; // Invalid path format
    }

    const firstPart = pathParts[0];
    if (!firstPart) {
      return false; // Invalid path format
    }

    // Check if it's a UUID (legacy format: 8-4-4-4-12 hex digits)
    const uuidPattern = /^[\w-]{8}-[\w-]{4}-[\w-]{4}-[\w-]{4}-[\w-]{12}$/;
    if (uuidPattern.test(firstPart)) {
      // Legacy format: first part is folder ID
      return folderIds.includes(firstPart);
    }

    // New format: first part is folder name, resolve to ID
    const projectStore = useProjectStore();
    const activeProject = projectStore.activeProject;
    if (!activeProject) {
      return false;
    }

    // Find folder by name (sanitized name matches)
    const folder = activeProject.folders.find((f) => {
      // Sanitize folder name the same way as server does
      const sanitizedName = f.name
        .replace(/\//g, '_')
        .replace(/\\/g, '_')
        .replace(/:/g, '_')
        .replace(/\*/g, '_')
        .replace(/\?/g, '_')
        .replace(/"/g, '_')
        .replace(/</g, '_')
        .replace(/>/g, '_')
        .replace(/\|/g, '_')
        .replace(/\./g, '')
        .trim();

      // Remove multiple consecutive underscores
      const normalized = sanitizedName.replace(/_+/g, '_');
      return normalized === firstPart || (normalized || 'folder') === firstPart;
    });

    if (!folder) {
      return false;
    }

    return folderIds.includes(folder.id);
  }
  async searchSymbols(
    projectId: ProjectId,
    symbolName: string,
    limit = 10,
    folderIds?: ProjectFolderId[],
  ): Promise<SearchResult[]> {
    const indexData = await loadIndex(projectId);
    if (!indexData) {
      return [];
    }

    const lowerName = symbolName.toLowerCase();
    const matchingSymbols = indexData.symbols.filter(
      (s) =>
        s.name.toLowerCase().includes(lowerName) && this.matchesFolderScope(s.filePath, folderIds),
    );

    const results: SearchResult[] = [];
    const seenChunks = new Set<string>();

    for (const symbol of matchingSymbols.slice(0, limit)) {
      // Find chunks containing this symbol
      const chunks = indexData.chunks.filter(
        (c) =>
          c.symbolIds?.includes(symbol.symbolId) && this.matchesFolderScope(c.filePath, folderIds),
      );

      for (const chunk of chunks) {
        if (!seenChunks.has(chunk.chunkId)) {
          seenChunks.add(chunk.chunkId);
          results.push({
            chunkId: chunk.chunkId,
            filePath: chunk.filePath,
            startLine: chunk.startLine,
            endLine: chunk.endLine,
            preview: chunk.preview,
            relevanceScore: 1.0,
            matchType: 'symbol',
            matchedSymbols: [symbol.symbolId],
          });
        }
      }
    }

    return results;
  }

  async searchText(
    projectId: ProjectId,
    query: string,
    limit = 20,
    folderIds?: ProjectFolderId[],
  ): Promise<SearchResult[]> {
    const indexData = await loadIndex(projectId);
    if (!indexData) {
      return [];
    }

    const lowerQuery = query.toLowerCase();
    const results: SearchResult[] = [];

    for (const chunk of indexData.chunks) {
      // Filter by folder scope
      if (!this.matchesFolderScope(chunk.filePath, folderIds)) {
        continue;
      }

      const lowerPreview = chunk.preview.toLowerCase();
      if (lowerPreview.includes(lowerQuery)) {
        // Calculate simple relevance score based on match position
        const index = lowerPreview.indexOf(lowerQuery);
        const relevanceScore = 1.0 - index / chunk.preview.length;

        results.push({
          chunkId: chunk.chunkId,
          filePath: chunk.filePath,
          startLine: chunk.startLine,
          endLine: chunk.endLine,
          preview: chunk.preview,
          relevanceScore,
          matchType: 'text',
          matchedSymbols: chunk.symbolIds ?? [],
        });
      }
    }

    // Sort by relevance and limit
    return results.sort((a, b) => b.relevanceScore - a.relevanceScore).slice(0, limit);
  }

  async searchSemantic(
    projectId: ProjectId,
    query: string,
    limit = 10,
    folderIds?: ProjectFolderId[],
  ): Promise<SearchResult[]> {
    const companionStore = useLocalCompanionStore();
    const projectStore = useProjectStore();

    // Require companion connection for semantic search
    if (!companionStore.isConnected) {
      throw new Error('Local companion connection required for semantic search. Please ensure the companion server is running.');
    }

    const response = await companionStore.request<{
      success: boolean;
      results?: SearchResult[];
      error?: string;
    }>('retrieve_chunks', {
      projectId,
      query,
      limit,
      folderIds,
      embeddingModelId: projectStore.getEmbeddingModelId(),
      hfToken: companionStore.huggingFaceToken || undefined,
    });

    if (response.success && response.results) {
      return response.results;
    }

    // If companion returns an error, throw it
    throw new Error(response.error ?? 'Semantic search failed');
  }

  async search(
    projectId: ProjectId,
    query: string,
    type: 'text' | 'symbol' | 'semantic' = 'semantic',
    limit = 10,
    folderIds?: ProjectFolderId[],
  ): Promise<SearchResult[]> {
    switch (type) {
      case 'symbol':
        return this.searchSymbols(projectId, query, limit, folderIds);
      case 'text':
        return this.searchText(projectId, query, limit, folderIds);
      case 'semantic':
        return this.searchSemantic(projectId, query, limit, folderIds);
      default:
        return [];
    }
  }

  async getSymbolContext(
    projectId: ProjectId,
    symbolName: string,
    folderIds?: ProjectFolderId[],
  ): Promise<SearchResult[]> {
    const indexData = await loadIndex(projectId);
    if (!indexData) {
      return [];
    }

    const symbol = indexData.symbols.find(
      (s) =>
        s.name.toLowerCase() === symbolName.toLowerCase() &&
        this.matchesFolderScope(s.filePath, folderIds),
    );

    if (!symbol) {
      return [];
    }

    // Get chunks containing this symbol (filtered by folder scope)
    const chunks = indexData.chunks.filter(
      (c) =>
        c.symbolIds?.includes(symbol.symbolId) && this.matchesFolderScope(c.filePath, folderIds),
    );

    // Get related symbols via edges (only from same folder scope)
    const relatedEdges = indexData.edges.filter(
      (e) => e.fromSymbolId === symbol.symbolId || e.toName === symbol.name,
    );

    const relatedSymbolIds = new Set<string>();
    for (const edge of relatedEdges) {
      if (edge.toSymbolId) {
        const relatedSymbol = indexData.symbols.find((s) => s.symbolId === edge.toSymbolId);
        if (relatedSymbol && this.matchesFolderScope(relatedSymbol.filePath, folderIds)) {
          relatedSymbolIds.add(edge.toSymbolId);
        }
      }
    }

    // Get chunks for related symbols (filtered by folder scope)
    const relatedChunks = indexData.chunks.filter(
      (c) =>
        c.symbolIds?.some((sid) => relatedSymbolIds.has(sid)) &&
        this.matchesFolderScope(c.filePath, folderIds),
    );

    const results: SearchResult[] = [];

    // Add symbol's own chunks
    for (const chunk of chunks) {
      results.push({
        chunkId: chunk.chunkId,
        filePath: chunk.filePath,
        startLine: chunk.startLine,
        endLine: chunk.endLine,
        preview: chunk.preview,
        relevanceScore: 1.0,
        matchType: 'symbol',
        matchedSymbols: [symbol.symbolId],
      });
    }

    // Add related chunks
    for (const chunk of relatedChunks.slice(0, 5)) {
      results.push({
        chunkId: chunk.chunkId,
        filePath: chunk.filePath,
        startLine: chunk.startLine,
        endLine: chunk.endLine,
        preview: chunk.preview,
        relevanceScore: 0.7,
        matchType: 'symbol',
        matchedSymbols: chunk.symbolIds ?? [],
      });
    }

    return results;
  }
}

// Singleton instance
export const retrieval = new Retrieval();
