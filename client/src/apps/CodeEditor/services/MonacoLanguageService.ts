import * as monaco from 'monaco-editor';
import { retrieval } from '../core/indexing/Retrieval';
import { loadIndex } from '../core/indexing/persistence';
import { useProjectStore } from '../stores/project';
import type { IndexData } from '../core/indexing/types';

export class MonacoLanguageService {
  private static instance: MonacoLanguageService;
  private disposables: monaco.IDisposable[] = [];
  private isInitialized = false;
  private indexCache: Map<string, { data: IndexData; timestamp: number }> = new Map();
  private pendingRequests: Map<string, Promise<IndexData | null>> = new Map();
  private readonly CACHE_TTL = 30000; // 30 seconds cache for index data

  private constructor() {}

  public static getInstance(): MonacoLanguageService {
    if (!MonacoLanguageService.instance) {
      MonacoLanguageService.instance = new MonacoLanguageService();
    }
    return MonacoLanguageService.instance;
  }

  public initialize() {
    if (this.isInitialized) return;

    this.configureDiagnostics();
    this.registerProviders();

    this.isInitialized = true;
    console.log('MonacoLanguageService initialized');
  }

  public dispose() {
    this.disposables.forEach((d) => d.dispose());
    this.disposables = [];
    this.isInitialized = false;
    this.indexCache.clear();
    this.pendingRequests.clear();
  }

  private configureDiagnostics() {
    // Configure TypeScript/JavaScript diagnostics
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    const ts = monaco.languages.typescript as any;
    const defaults = [ts.typescriptDefaults, ts.javascriptDefaults];

    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    defaults.forEach((d: any) => {
      d.setCompilerOptions({
        target: ts.ScriptTarget.ESNext,
        allowNonTsExtensions: true,
        moduleResolution: ts.ModuleResolutionKind.NodeJs,
        module: ts.ModuleKind.CommonJS,
        noEmit: true,
        esModuleInterop: true,
        jsx: ts.JsxEmit.React,
        reactNamespace: 'React',
        allowJs: true,
        typeRoots: ['node_modules/@types'],
        // Reduce strictness to avoid red lines for missing types
        noImplicitAny: false,
        noSemanticValidation: false,
        noSyntaxValidation: false,
      });
    });
  }

  private registerProviders() {
    const languages = [
      'typescript',
      'javascript',
      'python',
      'java',
      'cpp',
      'c',
      'csharp',
      'go',
      'rust',
      'php',
      'vue',
    ];

    languages.forEach((languageId) => {
      // Definition Provider
      this.disposables.push(
        monaco.languages.registerDefinitionProvider(languageId, {
          provideDefinition: async (model, position, _token) => {
            return this.provideDefinition(model, position);
          },
        }),
      );

      // Hover Provider
      this.disposables.push(
        monaco.languages.registerHoverProvider(languageId, {
          provideHover: async (model, position, _token) => {
            return this.provideHover(model, position);
          },
        }),
      );

      // Completion Provider
      this.disposables.push(
        monaco.languages.registerCompletionItemProvider(languageId, {
          triggerCharacters: ['.', '"', "'", '/'],
          provideCompletionItems: async (model, position, _context, _token) => {
            return this.provideCompletionItems(model, position);
          },
        }),
      );
    });
  }

  private async getIndex(projectId: string): Promise<IndexData | null> {
    const now = Date.now();
    const cached = this.indexCache.get(projectId);

    // Return cached data if still valid
    if (cached && now - cached.timestamp < this.CACHE_TTL) {
      return cached.data;
    }

    // If there's already a pending request for this project, wait for it
    const pendingRequest = this.pendingRequests.get(projectId);
    if (pendingRequest) {
      return pendingRequest;
    }

    // Create a new request and track it
    const requestPromise = (async () => {
      try {
        const data = await loadIndex(projectId);
        if (data) {
          this.indexCache.set(projectId, { data, timestamp: Date.now() });
        }
        return data;
      } catch (e) {
        console.error('Failed to load index for Monaco service', e);
        return null;
      } finally {
        // Remove from pending requests once complete
        this.pendingRequests.delete(projectId);
      }
    })();

    this.pendingRequests.set(projectId, requestPromise);
    return requestPromise;
  }

  private async provideDefinition(
    model: monaco.editor.ITextModel,
    position: monaco.Position,
  ): Promise<monaco.languages.Definition | undefined> {
    const projectStore = useProjectStore();
    const projectId = projectStore.activeProjectId;
    if (!projectId) return;

    const wordInfo = model.getWordAtPosition(position);
    const lineContent = model.getLineContent(position.lineNumber);

    // Check for import path (string literal)
    const importMatch = lineContent.match(/['"]([^'"]+)['"]/);
    if (importMatch) {
      const importPath = importMatch[1];
      const index = importMatch.index || 0;
      const end = index + importMatch[0].length;

      // If cursor is within the string
      if (position.column > index && position.column <= end + 1) {
        const resolvedFile = await this.resolveImportPath(projectId, importPath!);
        if (resolvedFile) {
          return {
            uri: monaco.Uri.file('/' + resolvedFile),
            range: new monaco.Range(1, 1, 1, 1),
          };
        }
      }
    }

    if (!wordInfo) return;

    // Look up symbol
    const symbol = await retrieval.findExactSymbol(projectId, wordInfo.word);

    if (symbol) {
      return {
        uri: monaco.Uri.file('/' + symbol.filePath),
        range: new monaco.Range(
          symbol.range.startLine,
          symbol.range.startColumn,
          symbol.range.endLine,
          symbol.range.endColumn,
        ),
      };
    }
  }

  private async provideHover(
    model: monaco.editor.ITextModel,
    position: monaco.Position,
  ): Promise<monaco.languages.Hover | undefined> {
    const projectStore = useProjectStore();
    const projectId = projectStore.activeProjectId;
    if (!projectId) return;

    const wordInfo = model.getWordAtPosition(position);
    if (!wordInfo) return;

    const symbol = await retrieval.findExactSymbol(projectId, wordInfo.word);

    if (symbol) {
      const contents: monaco.IMarkdownString[] = [];

      // Signature
      if (symbol.signature) {
        contents.push({ value: '```' + symbol.language + '\n' + symbol.signature + '\n```' });
      } else {
        contents.push({ value: '**' + symbol.name + '** (' + symbol.kind + ')' });
      }

      // Documentation
      if (symbol.documentation) {
        contents.push({ value: symbol.documentation });
      }

      // Location info
      contents.push({ value: `*Defined in ${symbol.filePath}*` });

      return {
        range: new monaco.Range(
          position.lineNumber,
          wordInfo.startColumn,
          position.lineNumber,
          wordInfo.endColumn,
        ),
        contents,
      };
    }
  }

  private async provideCompletionItems(
    model: monaco.editor.ITextModel,
    position: monaco.Position,
  ): Promise<monaco.languages.CompletionList | undefined> {
    const projectStore = useProjectStore();
    const projectId = projectStore.activeProjectId;
    if (!projectId) return;

    const wordInfo = model.getWordUntilPosition(position);
    const prefix = wordInfo.word;

    const indexData = await this.getIndex(projectId);

    if (indexData) {
      const matchingSymbols = indexData.symbols.filter((s) =>
        s.name.toLowerCase().startsWith(prefix.toLowerCase()),
      );

      return {
        suggestions: matchingSymbols.map((s) => {
          const item: monaco.languages.CompletionItem = {
            label: s.name,
            kind: this.mapSymbolKind(s.kind),
            detail: s.signature || s.kind,
            insertText: s.name,
            range: {
              startLineNumber: position.lineNumber,
              endLineNumber: position.lineNumber,
              startColumn: wordInfo.startColumn,
              endColumn: wordInfo.endColumn,
            },
          };

          if (s.documentation) {
            item.documentation = { value: s.documentation };
          }

          return item;
        }),
      };
    }

    return { suggestions: [] };
  }

  private mapSymbolKind(kind: string): monaco.languages.CompletionItemKind {
    switch (kind) {
      case 'function':
        return monaco.languages.CompletionItemKind.Function;
      case 'class':
        return monaco.languages.CompletionItemKind.Class;
      case 'interface':
        return monaco.languages.CompletionItemKind.Interface;
      case 'variable':
        return monaco.languages.CompletionItemKind.Variable;
      case 'constant':
        return monaco.languages.CompletionItemKind.Constant;
      case 'method':
        return monaco.languages.CompletionItemKind.Method;
      case 'property':
        return monaco.languages.CompletionItemKind.Property;
      case 'enum':
        return monaco.languages.CompletionItemKind.Enum;
      case 'module':
        return monaco.languages.CompletionItemKind.Module;
      default:
        return monaco.languages.CompletionItemKind.Text;
    }
  }

  private async resolveImportPath(
    projectId: string,
    importPath: string,
  ): Promise<string | undefined> {
    const indexData = await this.getIndex(projectId);
    if (!indexData) return undefined;

    // Normalize import path (remove ./, ../ etc if possible, or just match end)
    const cleanImport = importPath.replace(/^[./]+/, '');

    // Find a file that ends with this path
    // We also need to check extensions
    const extensions = [
      '.ts',
      '.js',
      '.vue',
      '.py',
      '.java',
      '.cpp',
      '.h',
      '.c',
      '.cs',
      '.go',
      '.rs',
      '.php',
    ];

    const matchedFile = indexData.metadata.fileManifests.find((f) => {
      // Check exact match
      if (f.filePath.endsWith(cleanImport)) return true;

      // Check with extensions
      return extensions.some((ext) => f.filePath.endsWith(cleanImport + ext));
    });

    return matchedFile?.filePath;
  }
}

export const monacoLanguageService = MonacoLanguageService.getInstance();
