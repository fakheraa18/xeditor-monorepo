import MarkdownIt from 'markdown-it';
import highlightjs from 'markdown-it-highlightjs';

// Language mapping for highlight.js (maps unsupported languages to supported ones)
const languageAliases: Record<string, string> = {
  vue: 'html', // Vue files contain HTML-like syntax, use HTML highlighting
  jsx: 'javascript', // JSX is JavaScript with XML
  tsx: 'typescript', // TSX is TypeScript with XML
  dockerfile: 'bash', // Dockerfile syntax is similar to bash
  prisma: 'javascript', // Prisma schema files, use JavaScript-like highlighting
  pr: 'plaintext', // Unknown 'pr' language, fallback to plaintext
};

// Common highlight.js supported languages (non-exhaustive, but covers most cases)
// If a language isn't in aliases and isn't in this set, we'll fallback to plaintext
const knownSupportedLanguages = new Set([
  'javascript',
  'typescript',
  'python',
  'java',
  'c',
  'cpp',
  'csharp',
  'go',
  'rust',
  'ruby',
  'php',
  'swift',
  'kotlin',
  'scala',
  'html',
  'css',
  'scss',
  'sass',
  'less',
  'json',
  'xml',
  'yaml',
  'markdown',
  'sql',
  'bash',
  'shell',
  'sh',
  'powershell',
  'plaintext',
  'text',
  'diff',
  'dockerfile',
  'ini',
  'toml',
  'makefile',
  'nginx',
  'apache',
]);

/**
 * Normalizes language names for highlight.js compatibility
 * Falls back to 'plaintext' for unknown languages to avoid errors
 */
function normalizeLanguage(lang: string): string {
  if (!lang) return 'plaintext';
  
  const normalized = lang.toLowerCase().trim();
  
  // Reject invalid language identifiers (special chars only, too short, etc.)
  if (
    normalized.length === 0 ||
    normalized.length === 1 ||
    !/^[a-zA-Z]/.test(normalized) ||
    /^[^a-zA-Z0-9]+$/.test(normalized) // Only special chars, no letters/numbers
  ) {
    return 'plaintext';
  }
  
  // Check if we have an alias for this language
  if (languageAliases[normalized]) {
    return languageAliases[normalized] ?? 'plaintext';
  }
  
  // Check if it's a known supported language
  if (knownSupportedLanguages.has(normalized)) {
    return normalized;
  }
  
  // Fallback to plaintext for unknown languages to avoid highlight.js errors
  return 'plaintext';
}

/**
 * Preprocesses markdown content to replace unsupported language identifiers
 */
function preprocessMarkdown(content: string): string {
  // Replace language identifiers in code fences: ```vue -> ```html
  // Match: ``` followed by language identifier (must start with letter, then word chars/hyphens/dots)
  // This preserves any additional info after the language identifier
  // Only match valid language identifiers (at least one letter, no special chars like |)
  return content.replace(/```([a-zA-Z][a-zA-Z0-9_.-]*)(\s.*?)?(\n|$)/g, (match, lang, rest, newline) => {
    // Validate that we have a valid language identifier
    if (!lang || lang.trim().length === 0 || !/^[a-zA-Z]/.test(lang)) {
      return match; // Return original if invalid
    }
    const normalized = normalizeLanguage(lang);
    const restPart = rest ?? '';
    return `\`\`\`${normalized}${restPart}${newline}`;
  });
}

// Initialize markdown-it with highlightjs plugin
const md = new MarkdownIt({
  html: false, // Disable HTML tags for security
  breaks: true, // Convert \n to <br>
  linkify: true, // Auto-convert URLs to links
  typographer: true, // Enable smart quotes and dashes
});

// Add syntax highlighting
md.use(highlightjs, {
  inline: true, // Enable inline code highlighting
});

/**
 * Closes any unclosed code blocks in streaming content
 * This ensures markdown-it can properly parse incomplete code blocks
 */
function closeOpenCodeBlocks(content: string): string {
  // Count occurrences of code block markers
  // We need to handle both ``` and ```language
  const codeBlockPattern = /```/g;
  const matches = content.match(codeBlockPattern);

  if (matches && matches.length % 2 !== 0) {
    // Odd number of ```, append closing marker
    return content + '\n```';
  }

  return content;
}

/**
 * Closes any unclosed inline code in streaming content
 */
function closeOpenInlineCode(content: string): string {
  // Count single backticks that are not part of triple backticks
  // First, temporarily replace triple backticks
  const placeholder = '\u0000CODEBLOCK\u0000';
  const withoutCodeBlocks = content.replace(/```[\s\S]*?```|```[\s\S]*/g, placeholder);

  // Count remaining single backticks
  const backtickCount = (withoutCodeBlocks.match(/`/g) || []).length;

  if (backtickCount % 2 !== 0) {
    // Odd number of backticks, append closing
    return content + '`';
  }

  return content;
}

/**
 * Prepares streaming content for safe rendering
 * Closes any unclosed markdown structures
 */
function prepareStreamingContent(content: string): string {
  let result = content;

  // Close unclosed code blocks first (higher priority)
  result = closeOpenCodeBlocks(result);

  // Then close unclosed inline code
  result = closeOpenInlineCode(result);

  return result;
}

/**
 * Language display name mapping
 */
const languageDisplayNames: Record<string, string> = {
  js: 'JavaScript',
  javascript: 'JavaScript',
  ts: 'TypeScript',
  typescript: 'TypeScript',
  py: 'Python',
  python: 'Python',
  rb: 'Ruby',
  ruby: 'Ruby',
  sh: 'Shell',
  bash: 'Bash',
  zsh: 'Zsh',
  json: 'JSON',
  yaml: 'YAML',
  yml: 'YAML',
  md: 'Markdown',
  markdown: 'Markdown',
  html: 'HTML',
  css: 'CSS',
  scss: 'SCSS',
  vue: 'Vue',
  jsx: 'JSX',
  tsx: 'TSX',
  sql: 'SQL',
  go: 'Go',
  rust: 'Rust',
  cpp: 'C++',
  c: 'C',
  java: 'Java',
  kotlin: 'Kotlin',
  swift: 'Swift',
  php: 'PHP',
  dockerfile: 'Dockerfile',
  xml: 'XML',
  plaintext: 'Text',
  text: 'Text',
};

/**
 * Gets the display name for a language
 */
function getLanguageDisplayName(lang: string): string {
  if (!lang) return 'Code';
  return languageDisplayNames[lang.toLowerCase()] || lang.toUpperCase();
}

/**
 * Wraps code blocks with header containing language label and copy button
 */
function wrapCodeBlocks(html: string, isStreaming: boolean): string {
  // Match <pre><code class="...">...</code></pre> blocks
  // The highlight.js plugin adds class like "hljs language-xxx" or just "hljs"
  return html.replace(
    /<pre><code(?:\s+class="([^"]*)")?>([\s\S]*?)<\/code><\/pre>/g,
    (_match, classAttr: string | undefined, codeContent: string) => {
      // Extract language from class attribute
      let language = '';
      if (classAttr) {
        // Look for language-xxx or just the language name in classes
        const langMatch = classAttr.match(/language-(\w+)/);
        if (langMatch && langMatch[1]) {
          language = langMatch[1];
        } else {
          // Try to find a language class that's not "hljs"
          const classes = classAttr.split(/\s+/);
          for (const cls of classes) {
            if (cls !== 'hljs' && languageDisplayNames[cls.toLowerCase()]) {
              language = cls;
              break;
            }
          }
        }
      }

      const displayName = getLanguageDisplayName(language);
      const streamingClass = isStreaming ? ' is-streaming' : '';

      return `<div class="code-block-wrapper${streamingClass}">
  <div class="code-block-header">
    <span class="code-language">${displayName}</span>
    <button class="code-copy-btn" title="Copy code">
      <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
        <rect x="9" y="9" width="13" height="13" rx="2" ry="2"></rect>
        <path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"></path>
      </svg>
    </button>
  </div>
  <pre><code${classAttr ? ` class="${classAttr}"` : ''}>${codeContent}</code></pre>
</div>`;
    },
  );
}

export function useMarkdown() {
  /**
   * Renders markdown content to HTML
   * @param content - The markdown content to render
   * @param isStreaming - Whether the content is still being streamed (handles incomplete blocks)
   * @returns HTML string
   */
  /**
   * Post-processes HTML to fix invalid language classes that might have slipped through
   */
  function postProcessHtml(html: string): string {
    // Fix invalid language classes like "language-|" or "language-|something"
    // Replace with plaintext to avoid highlight.js errors
    return html.replace(/language-([^"\s<>]+)/g, (match, lang) => {
      const normalized = normalizeLanguage(lang);
      return `language-${normalized}`;
    });
  }

  function renderMarkdown(content: string, isStreaming = false): string {
    if (!content) return '';

    let processedContent = content;

    // Preprocess to normalize language identifiers for highlight.js
    processedContent = preprocessMarkdown(processedContent);

    // If streaming, close any unclosed structures
    if (isStreaming) {
      processedContent = prepareStreamingContent(processedContent);
    }

    try {
      let html = md.render(processedContent);

      // Post-process to fix any invalid language classes that slipped through
      html = postProcessHtml(html);

      // Wrap code blocks with header
      html = wrapCodeBlocks(html, isStreaming);

      return html;
    } catch (error) {
      console.error('Markdown rendering error:', error);
      // Fallback: escape HTML and convert newlines
      return processedContent
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/\n/g, '<br>');
    }
  }

  /**
   * Renders inline markdown (no block elements like paragraphs)
   * Useful for single-line content
   */
  function renderInline(content: string): string {
    if (!content) return '';

    try {
      return md.renderInline(content);
    } catch (error) {
      console.error('Markdown inline rendering error:', error);
      return content;
    }
  }

  return {
    renderMarkdown,
    renderInline,
    md, // Expose md instance for advanced customization if needed
  };
}
