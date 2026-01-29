import { useProjectStore } from '../../../../stores/project';
import { useEditorStore } from '../../../../stores/editor';
import { useMarkdown } from './useMarkdown';
import { useQuasar } from 'quasar';

export function useMessageFormatting() {
  const projectStore = useProjectStore();
  const editorStore = useEditorStore();
  const { renderMarkdown } = useMarkdown();
  const $q = useQuasar();

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

  function getFolderName(folderId: string): string {
    const folder = projectStore.activeProject?.folders.find((f) => f.id === folderId);
    return folder?.name || folderId.slice(0, 8);
  }

  function getFolderIdFromName(folderName: string): string | null {
    // Handle both exact name match and sanitized name match (for paths)
    const sanitizedInput = sanitizeFolderName(folderName);
    const folder = projectStore.activeProject?.folders.find((f) => {
      const sanitizedFolderName = sanitizeFolderName(f.name);
      return f.name === folderName || sanitizedFolderName === sanitizedInput;
    });
    return folder?.id || null;
  }

  /**
   * Valid file extensions whitelist
   */
  const VALID_FILE_EXTENSIONS = new Set([
    'ts',
    'tsx',
    'js',
    'jsx',
    'vue',
    'py',
    'json',
    'md',
    'css',
    'html',
    'htm',
    'scss',
    'sass',
    'less',
    'yaml',
    'yml',
    'xml',
    'sh',
    'bash',
    'zsh',
    'go',
    'rs',
    'cpp',
    'c',
    'h',
    'hpp',
    'java',
    'kt',
    'swift',
    'php',
    'rb',
    'sql',
    'dockerfile',
    'txt',
    'log',
    'ini',
    'conf',
    'config',
    'env',
    'lock',
    'toml',
    'json5',
    'mjs',
    'cjs',
    'dts',
    'map',
    'graphql',
    'gql',
    'proto',
    'r',
    'm',
    'mm',
    'pl',
    'pm',
    'lua',
    'dart',
    'elm',
    'ex',
    'exs',
    'erl',
    'hrl',
    'clj',
    'cljs',
    'cljc',
    'edn',
    'hs',
    'lhs',
    'fs',
    'fsx',
    'ml',
    'mli',
    'scala',
    'sbt',
    'groovy',
    'gradle',
    'kt',
    'kts',
    'nim',
    'zig',
    'v',
    'sv',
    'svh',
    'vhd',
    'vhdl',
    'tcl',
    'makefile',
    'mk',
    'cmake',
  ]);

  /**
   * Common Vue/JS event modifiers that should not be matched as file paths
   */
  const EVENT_MODIFIERS = new Set([
    'prevent',
    'stop',
    'once',
    'capture',
    'self',
    'passive',
    'native',
    'enter',
    'tab',
    'delete',
    'esc',
    'space',
    'up',
    'down',
    'left',
    'right',
  ]);

  /**
   * Validates if a matched path looks like a valid file path
   */
  function isValidFilePath(filePath: string): boolean {
    // Extract file name and extension
    const fileName = filePath.split('/').pop() ?? filePath;
    const lastDotIndex = fileName.lastIndexOf('.');

    // Must have an extension
    if (lastDotIndex === -1 || lastDotIndex === 0 || lastDotIndex === fileName.length - 1) {
      return false;
    }

    const extension = fileName.slice(lastDotIndex + 1).toLowerCase();

    // Extension must be in whitelist
    if (!VALID_FILE_EXTENSIONS.has(extension)) {
      return false;
    }

    // Check if any part of the path matches event modifiers
    const parts = filePath.toLowerCase().split('/');
    for (const part of parts) {
      // Remove extension for checking
      const dotIndex = part.indexOf('.');
      const partWithoutExt = dotIndex !== -1 ? part.slice(0, dotIndex) : part;
      if (partWithoutExt && EVENT_MODIFIERS.has(partWithoutExt)) {
        return false;
      }
    }

    // Path should not be too short (avoid matching things like @a.b)
    if (filePath.length < 4) {
      return false;
    }

    // File name should be reasonable (at least 2 chars before extension)
    const nameWithoutExt = fileName.slice(0, lastDotIndex);
    if (nameWithoutExt.length < 1) {
      return false;
    }

    return true;
  }

  /**
   * Processes file mentions (@folder/path/file.ext) and converts them to clickable chips
   * This is applied as post-processing after markdown rendering
   * Excludes code blocks to prevent chips inside code examples
   */
  function processFileMentions(html: string): string {
    // Extract code blocks and temporarily replace them with placeholders
    const codeBlockPlaceholders: string[] = [];
    let placeholderIndex = 0;

    // Match code blocks in order of specificity:
    // 1. code-block-wrapper divs (most specific, contains pre/code)
    // 2. pre tags (code blocks)
    // 3. code tags (inline code)
    // Use non-greedy matching and handle nested structures
    const codeBlockPattern =
      /(<div[^>]*class="[^"]*code-block-wrapper[^"]*"[^>]*>[\s\S]*?<\/div>)|(<pre[^>]*>[\s\S]*?<\/pre>)|(<code[^>]*>[\s\S]*?<\/code>)/gi;

    let processedHtml = html.replace(codeBlockPattern, (match) => {
      const placeholder = `__CODE_BLOCK_PLACEHOLDER_${placeholderIndex}__`;
      codeBlockPlaceholders[placeholderIndex] = match;
      placeholderIndex++;
      return placeholder;
    });

    // Stricter regex pattern: @folderName/path/to/file.ext or @path/to/file.ext
    // Requires valid file extension and proper path structure
    // Pattern breakdown:
    // - @ - literal @ symbol
    // - (?:[\w\s-]+\/) - optional folder name/ID (one or more word chars, spaces, hyphens followed by /)
    // - [\w\s./-]+ - path segments (word chars, spaces, dots, slashes, hyphens) - allows spaces in paths
    // - \. - literal dot before extension
    // - (ts|tsx|js|jsx|vue|...) - valid file extension from whitelist
    // - (?![\w.]) - negative lookahead to ensure we don't match beyond the extension
    const extensionPattern = Array.from(VALID_FILE_EXTENSIONS).join('|');
    const fileMentionPattern = new RegExp(
      `@((?:[\\w\\s-]+\\/)?[\\w\\s./-]+\\.(?:${extensionPattern}))(?![\\.\\w])`,
      'gi',
    );

    processedHtml = processedHtml.replace(fileMentionPattern, (match: string, filePath: string) => {
      // Trim whitespace from the matched path
      const trimmedPath = filePath.trim();

      // Validate the matched path
      if (!isValidFilePath(trimmedPath)) {
        return match; // Return original if invalid
      }

      const fileName = trimmedPath.split('/').pop() ?? trimmedPath;
      const parts = trimmedPath.split('/');

      let folderId: string | null = null;
      let displayName = fileName;
      let resolvedPath = trimmedPath; // Path with folderId for data-path attribute

      if (parts.length > 1 && parts[0]) {
        const firstPart = parts[0];

        // Check if first part is a UUID (folderId format: 8-4-4-4-12 hex digits)
        if (firstPart.match(/^[\w-]{8}-[\w-]{4}-[\w-]{4}-[\w-]{4}-[\w-]{12}$/)) {
          // It's a folderId (UUID), resolve to folder name for display
          folderId = firstPart;
          const folderName = getFolderName(folderId);
          displayName = `${folderName}/${fileName}`;
          resolvedPath = filePath; // Already has folderId
        } else {
          // It's likely a folder name, resolve to folderId for data-path
          folderId = getFolderIdFromName(firstPart);
          if (folderId) {
            // Resolve folder name to folderId for the data-path (so we can open files)
            const relativePath = parts.slice(1).join('/');
            resolvedPath = `${folderId}/${relativePath}`;
            displayName = `${firstPart}/${fileName}`; // Show folder name in display
          } else {
            // Couldn't resolve, might be legacy format or invalid
            displayName = fileName;
          }
        }
      }

      const escapedPath = resolvedPath.replace(/"/g, '&quot;');
      const escapedDisplay = displayName.replace(/"/g, '&quot;');

      return `<span class="file-mention-chip" data-path="${escapedPath}" title="${trimmedPath}">${escapedDisplay}</span>`;
    });

    // Restore code blocks
    for (let i = 0; i < codeBlockPlaceholders.length; i++) {
      processedHtml = processedHtml.replace(
        `__CODE_BLOCK_PLACEHOLDER_${i}__`,
        codeBlockPlaceholders[i] ?? '',
      );
    }

    return processedHtml;
  }

  /**
   * Formats message content with full markdown support
   * @param content - The raw message content
   * @param isStreaming - Whether the content is still being streamed (handles incomplete blocks)
   * @returns HTML string ready for v-html rendering
   */
  function formatMessage(content: string, isStreaming = false): string {
    if (!content) return '';

    // First, render markdown (with streaming support for incomplete blocks)
    let html = renderMarkdown(content, isStreaming);

    // Then, process file mentions as post-processing
    html = processFileMentions(html);

    return html;
  }

  function handleMessageClick(event: MouseEvent) {
    const target = event.target as HTMLElement;

    // Handle file mention chip clicks
    if (target.classList.contains('file-mention-chip')) {
      const filePath = target.dataset.path;
      if (filePath) {
        openMentionedFile(filePath);
      }
      return;
    }

    // Handle code block copy button clicks
    if (target.classList.contains('code-copy-btn') || target.closest('.code-copy-btn')) {
      const button = target.classList.contains('code-copy-btn')
        ? target
        : target.closest('.code-copy-btn');
      const codeBlock = button?.closest('.code-block-wrapper')?.querySelector('code');
      if (codeBlock) {
        void navigator.clipboard.writeText(codeBlock.textContent || '');
        // Visual feedback could be added here
      }
      return;
    }
  }

  function openMentionedFile(filePath: string) {
    try {
      // Validate filePath is not empty
      if (!filePath || filePath.trim() === '') {
        $q.notify({
          type: 'negative',
          message: 'Invalid file path',
          position: 'top',
          timeout: 3000,
        });
        return;
      }

      // filePath from data-path is always in format: folderId/relativePath
      // (formatMessage resolves folder names to folderIds)
      // For backward compatibility, also handle relativePath-only format
      const parts = filePath.split('/');
      let workspacePath: string;

      // Check if first part is a UUID (folderId format: 8-4-4-4-12 hex digits)
      if (
        parts.length > 1 &&
        parts[0] &&
        parts[0].match(/^[\w-]{8}-[\w-]{4}-[\w-]{4}-[\w-]{4}-[\w-]{12}$/)
      ) {
        // Path includes folderId: folderId/relativePath
        workspacePath = filePath;
      } else {
        // Legacy format or folder name: try to resolve or use first folder
        const project = projectStore.activeProject;
        if (!project || !project.folders || project.folders.length === 0) {
          $q.notify({
            type: 'warning',
            message: 'No project folders available',
            position: 'top',
            timeout: 3000,
          });
          return;
        }

        // Try to resolve folder name to folderId
        if (parts.length > 1 && parts[0]) {
          const folderId = getFolderIdFromName(parts[0]);
          if (folderId) {
            const relativePath = parts.slice(1).join('/');
            workspacePath = `${folderId}/${relativePath}`;
          } else {
            // Fallback to first folder
            const firstFolder = project.folders[0];
            if (!firstFolder) {
              $q.notify({
                type: 'warning',
                message: 'No project folders available',
                position: 'top',
                timeout: 3000,
              });
              return;
            }
            workspacePath = `${firstFolder.id}/${filePath}`;
          }
        } else {
          // Just relativePath, use first folder
          const firstFolder = project.folders[0];
          if (!firstFolder) {
            $q.notify({
              type: 'warning',
              message: 'No project folders available',
              position: 'top',
              timeout: 3000,
            });
            return;
          }
          workspacePath = `${firstFolder.id}/${filePath}`;
        }
      }

      // Validate folderId exists
      const folderId = workspacePath.split('/')[0];
      const folder = projectStore.activeProject?.folders.find((f) => f.id === folderId);
      if (!folder) {
        $q.notify({
          type: 'negative',
          message: `Folder not found: ${folderId}`,
          position: 'top',
          timeout: 3000,
        });
        return;
      }

      // Attempt to open file (this will handle file not found errors internally)
      void editorStore.openFile(workspacePath).catch((error) => {
        console.error('Error opening file:', error);
        $q.notify({
          type: 'negative',
          message: `Failed to open file: ${filePath}`,
          position: 'top',
          timeout: 3000,
        });
      });
    } catch (error) {
      console.error('Error in openMentionedFile:', error);
      $q.notify({
        type: 'negative',
        message: `Error opening file: ${filePath}`,
        position: 'top',
        timeout: 3000,
      });
    }
  }

  return {
    formatMessage,
    handleMessageClick,
    openMentionedFile,
    getFolderName,
    getFolderIdFromName,
  };
}
