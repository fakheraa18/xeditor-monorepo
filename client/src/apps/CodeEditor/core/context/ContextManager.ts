import type { ContextItem } from '../types';
import { useEditorStore } from '../../stores/editor';
import { useProjectStore } from '../../stores/project';
import { retrieval } from '../indexing/Retrieval';

export class ContextManager {
  getCurrentFileContext(): Promise<ContextItem[]> {
    const editorStore = useEditorStore();

    if (!editorStore.activeTab) {
      return Promise.resolve([]);
    }

    const tab = editorStore.activeTab;
    const content = tab.content;

    return Promise.resolve([
      {
        id: `file-${tab.filePath}`,
        type: 'file',
        content,
        relevanceScore: 1.0,
        metadata: {
          filePath: tab.filePath,
        },
      },
    ]);
  }

  getSelectedCodeContext(): Promise<ContextItem[]> {
    const editorStore = useEditorStore();

    if (!editorStore.activeTab || !editorStore.selectedText) {
      return Promise.resolve([]);
    }

    const tab = editorStore.activeTab;
    const selectedText = editorStore.selectedText;

    const metadata: ContextItem['metadata'] = {
      filePath: tab.filePath,
    };

    if (editorStore.cursorPosition?.line !== undefined) {
      metadata.lineStart = editorStore.cursorPosition.line;
      metadata.lineEnd = editorStore.cursorPosition.line;
    }

    return Promise.resolve([
      {
        id: `selection-${tab.filePath}-${Date.now()}`,
        type: 'snippet',
        content: selectedText,
        relevanceScore: 1.0,
        metadata,
      },
    ]);
  }

  async getSymbolContext(symbolName: string): Promise<ContextItem[]> {
    const projectStore = useProjectStore();
    const projectId = projectStore.activeProjectId;

    if (!projectId) {
      return [];
    }

    try {
      const results = await retrieval.getSymbolContext(projectId, symbolName);

      // Load actual content on-demand using range-based read (avoids chunking issues)
      const contextItems: ContextItem[] = [];
      for (const result of results) {
        try {
          const content = await projectStore.readFileRange(
            result.filePath,
            result.startLine,
            result.endLine,
          );

          contextItems.push({
            id: result.chunkId,
            type: 'symbol' as const,
            content,
            relevanceScore: result.relevanceScore,
            metadata: {
              filePath: result.filePath,
              lineStart: result.startLine,
              lineEnd: result.endLine,
              ...(result.matchedSymbols?.[0] ? { symbolName: result.matchedSymbols[0] } : {}),
            },
          });
        } catch (_error) {
          // Fallback to preview
          contextItems.push({
            id: result.chunkId,
            type: 'symbol' as const,
            content: result.preview,
            relevanceScore: result.relevanceScore,
            metadata: {
              filePath: result.filePath,
              lineStart: result.startLine,
              lineEnd: result.endLine,
              ...(result.matchedSymbols?.[0] ? { symbolName: result.matchedSymbols[0] } : {}),
            },
          });
        }
      }

      return contextItems;
    } catch (error) {
      console.error('Failed to get symbol context:', error);
      return [];
    }
  }

  async searchCode(
    query: string,
    type: 'text' | 'symbol' | 'semantic' = 'semantic',
  ): Promise<ContextItem[]> {
    const projectStore = useProjectStore();
    const projectId = projectStore.activeProjectId;

    if (!projectId) {
      return [];
    }

    try {
      const results = await retrieval.search(projectId, query, type, 20);
      const projectStore = useProjectStore();

      // Load actual content on-demand for top results using range-based read (avoids chunking issues)
      const contextItems: ContextItem[] = [];
      for (const result of results) {
        try {
          // Read actual file content for the chunk range
          const content = await projectStore.readFileRange(
            result.filePath,
            result.startLine,
            result.endLine,
          );

          contextItems.push({
            id: result.chunkId,
            type: result.matchType === 'symbol' ? 'symbol' : 'snippet',
            content,
            relevanceScore: result.relevanceScore,
            metadata: {
              filePath: result.filePath,
              lineStart: result.startLine,
              lineEnd: result.endLine,
              ...(result.matchedSymbols?.[0] ? { symbolName: result.matchedSymbols[0] } : {}),
            },
          });
        } catch (_error) {
          // Fallback to preview if file read fails
          contextItems.push({
            id: result.chunkId,
            type: result.matchType === 'symbol' ? 'symbol' : 'snippet',
            content: result.preview,
            relevanceScore: result.relevanceScore,
            metadata: {
              filePath: result.filePath,
              lineStart: result.startLine,
              lineEnd: result.endLine,
              ...(result.matchedSymbols?.[0] ? { symbolName: result.matchedSymbols[0] } : {}),
            },
          });
        }
      }

      return contextItems;
    } catch (error) {
      console.error('Failed to search code:', error);
      return [];
    }
  }

  rankContext(items: ContextItem[], _query: string): Promise<ContextItem[]> {
    // Simple ranking: sort by relevance score
    // TODO: Implement more sophisticated ranking
    return Promise.resolve([...items].sort((a, b) => b.relevanceScore - a.relevanceScore));
  }

  limitContext(items: ContextItem[], maxTokens: number = 4000): Promise<ContextItem[]> {
    // Simple token estimation: ~4 chars per token
    const charLimit = maxTokens * 4;
    let totalChars = 0;
    const limited: ContextItem[] = [];

    for (const item of items) {
      const itemChars = item.content.length;
      if (totalChars + itemChars <= charLimit) {
        limited.push(item);
        totalChars += itemChars;
      } else {
        break;
      }
    }

    return Promise.resolve(limited);
  }
}
