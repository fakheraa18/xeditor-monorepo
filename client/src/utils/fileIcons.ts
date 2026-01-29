/**
 * File icon mapping utility for VS Code-like file icons
 * Uses Material Design icons available in Quasar
 */

export interface FileIconInfo {
  icon: string;
  color: string;
}

// Map of file extensions to icons and colors
const extensionIconMap: Record<string, FileIconInfo> = {
  // TypeScript/JavaScript
  ts: { icon: 'code', color: '#3178c6' },
  tsx: { icon: 'code', color: '#3178c6' },
  js: { icon: 'javascript', color: '#f7df1e' },
  jsx: { icon: 'javascript', color: '#f7df1e' },
  mjs: { icon: 'javascript', color: '#f7df1e' },
  cjs: { icon: 'javascript', color: '#f7df1e' },

  // Vue
  vue: { icon: 'widgets', color: '#42b883' },

  // Web
  html: { icon: 'html', color: '#e34c26' },
  htm: { icon: 'html', color: '#e34c26' },
  css: { icon: 'css', color: '#1572b6' },
  scss: { icon: 'css', color: '#cc6699' },
  sass: { icon: 'css', color: '#cc6699' },
  less: { icon: 'css', color: '#1d365d' },

  // Data formats
  json: { icon: 'data_object', color: '#f5a623' },
  yaml: { icon: 'data_object', color: '#cb171e' },
  yml: { icon: 'data_object', color: '#cb171e' },
  xml: { icon: 'code', color: '#f16529' },
  toml: { icon: 'settings', color: '#9c4121' },

  // Markdown/Documentation
  md: { icon: 'article', color: '#083fa1' },
  mdx: { icon: 'article', color: '#fcb32c' },
  txt: { icon: 'notes', color: '#6e6e6e' },
  rst: { icon: 'article', color: '#141414' },

  // Python
  py: { icon: 'code', color: '#3776ab' },
  pyw: { icon: 'code', color: '#3776ab' },
  pyx: { icon: 'code', color: '#3776ab' },
  pyi: { icon: 'code', color: '#3776ab' },

  // Rust
  rs: { icon: 'memory', color: '#dea584' },

  // Go
  go: { icon: 'code', color: '#00add8' },

  // Java/Kotlin
  java: { icon: 'coffee', color: '#b07219' },
  kt: { icon: 'code', color: '#a97bff' },
  kts: { icon: 'code', color: '#a97bff' },

  // C/C++
  c: { icon: 'code', color: '#555555' },
  h: { icon: 'code', color: '#555555' },
  cpp: { icon: 'code', color: '#f34b7d' },
  hpp: { icon: 'code', color: '#f34b7d' },
  cc: { icon: 'code', color: '#f34b7d' },

  // Shell/Scripts
  sh: { icon: 'terminal', color: '#89e051' },
  bash: { icon: 'terminal', color: '#89e051' },
  zsh: { icon: 'terminal', color: '#89e051' },
  fish: { icon: 'terminal', color: '#89e051' },
  ps1: { icon: 'terminal', color: '#012456' },
  bat: { icon: 'terminal', color: '#c1f12e' },
  cmd: { icon: 'terminal', color: '#c1f12e' },

  // Config files
  env: { icon: 'settings', color: '#ecd53f' },
  ini: { icon: 'settings', color: '#6e6e6e' },
  conf: { icon: 'settings', color: '#6e6e6e' },
  config: { icon: 'settings', color: '#6e6e6e' },

  // Images
  png: { icon: 'image', color: '#a074c4' },
  jpg: { icon: 'image', color: '#a074c4' },
  jpeg: { icon: 'image', color: '#a074c4' },
  gif: { icon: 'image', color: '#a074c4' },
  svg: { icon: 'image', color: '#ffb13b' },
  ico: { icon: 'image', color: '#a074c4' },
  webp: { icon: 'image', color: '#a074c4' },

  // Fonts
  woff: { icon: 'font_download', color: '#ec6363' },
  woff2: { icon: 'font_download', color: '#ec6363' },
  ttf: { icon: 'font_download', color: '#ec6363' },
  otf: { icon: 'font_download', color: '#ec6363' },
  eot: { icon: 'font_download', color: '#ec6363' },

  // Documents
  pdf: { icon: 'picture_as_pdf', color: '#e6342c' },
  doc: { icon: 'description', color: '#2b579a' },
  docx: { icon: 'description', color: '#2b579a' },
  xls: { icon: 'table_chart', color: '#217346' },
  xlsx: { icon: 'table_chart', color: '#217346' },

  // Archives
  zip: { icon: 'folder_zip', color: '#6e6e6e' },
  tar: { icon: 'folder_zip', color: '#6e6e6e' },
  gz: { icon: 'folder_zip', color: '#6e6e6e' },
  rar: { icon: 'folder_zip', color: '#6e6e6e' },
  '7z': { icon: 'folder_zip', color: '#6e6e6e' },

  // Lock files
  lock: { icon: 'lock', color: '#8b8b8b' },

  // Git
  gitignore: { icon: 'rule', color: '#f14e32' },
  gitattributes: { icon: 'rule', color: '#f14e32' },

  // Docker
  dockerfile: { icon: 'sailing', color: '#2496ed' },
  dockerignore: { icon: 'rule', color: '#2496ed' },

  // SQL
  sql: { icon: 'storage', color: '#e38c00' },

  // Log files
  log: { icon: 'receipt_long', color: '#6e6e6e' },
};

// Special file names that override extension matching
const specialFileMap: Record<string, FileIconInfo> = {
  'package.json': { icon: 'inventory_2', color: '#cb3837' },
  'package-lock.json': { icon: 'lock', color: '#cb3837' },
  'tsconfig.json': { icon: 'settings', color: '#3178c6' },
  'vite.config.ts': { icon: 'flash_on', color: '#646cff' },
  'vite.config.js': { icon: 'flash_on', color: '#646cff' },
  '.gitignore': { icon: 'rule', color: '#f14e32' },
  '.env': { icon: 'vpn_key', color: '#ecd53f' },
  '.env.local': { icon: 'vpn_key', color: '#ecd53f' },
  '.env.development': { icon: 'vpn_key', color: '#ecd53f' },
  '.env.production': { icon: 'vpn_key', color: '#ecd53f' },
  'README.md': { icon: 'menu_book', color: '#083fa1' },
  LICENSE: { icon: 'gavel', color: '#d4af37' },
  Dockerfile: { icon: 'sailing', color: '#2496ed' },
  'docker-compose.yml': { icon: 'sailing', color: '#2496ed' },
  'docker-compose.yaml': { icon: 'sailing', color: '#2496ed' },
  '.prettierrc': { icon: 'auto_fix_high', color: '#56b3b4' },
  '.prettierrc.json': { icon: 'auto_fix_high', color: '#56b3b4' },
  '.eslintrc': { icon: 'rule', color: '#4b32c3' },
  '.eslintrc.js': { icon: 'rule', color: '#4b32c3' },
  '.eslintrc.json': { icon: 'rule', color: '#4b32c3' },
  'eslint.config.js': { icon: 'rule', color: '#4b32c3' },
  'eslint.config.mjs': { icon: 'rule', color: '#4b32c3' },
  'quasar.config.ts': { icon: 'settings', color: '#1976d2' },
  'quasar.config.js': { icon: 'settings', color: '#1976d2' },
  'yarn.lock': { icon: 'lock', color: '#2c8ebb' },
  'pnpm-lock.yaml': { icon: 'lock', color: '#f9ad00' },
  'requirements.txt': { icon: 'list', color: '#3776ab' },
  'pyproject.toml': { icon: 'settings', color: '#3776ab' },
  'Cargo.toml': { icon: 'settings', color: '#dea584' },
  'Cargo.lock': { icon: 'lock', color: '#dea584' },
  'go.mod': { icon: 'settings', color: '#00add8' },
  'go.sum': { icon: 'lock', color: '#00add8' },
  Makefile: { icon: 'build', color: '#6d8086' },
};

const defaultIcon: FileIconInfo = { icon: 'description', color: '#9e9e9e' };
const folderIcon: FileIconInfo = { icon: 'folder', color: '#dcb67a' };
const folderOpenIcon: FileIconInfo = { icon: 'folder_open', color: '#dcb67a' };
const rootFolderIcon: FileIconInfo = { icon: 'work', color: '#1976d2' };

/**
 * Get icon info for a file based on its name
 */
export function getFileIcon(fileName: string): FileIconInfo {
  // Check for special file names first
  const lowerFileName = fileName.toLowerCase();
  if (specialFileMap[fileName]) {
    return specialFileMap[fileName];
  }
  if (specialFileMap[lowerFileName]) {
    return specialFileMap[lowerFileName];
  }

  // Extract extension
  const lastDotIndex = fileName.lastIndexOf('.');
  if (lastDotIndex === -1 || lastDotIndex === 0) {
    return defaultIcon;
  }

  const ext = fileName.slice(lastDotIndex + 1).toLowerCase();
  return extensionIconMap[ext] || defaultIcon;
}

/**
 * Get icon info for a folder
 */
export function getFolderIcon(isOpen = false, isRoot = false): FileIconInfo {
  if (isRoot) {
    return rootFolderIcon;
  }
  return isOpen ? folderOpenIcon : folderIcon;
}

/**
 * Get the language identifier for Monaco editor based on file extension
 */
export function getLanguageFromFileName(fileName: string): string {
  const ext = fileName.split('.').pop()?.toLowerCase() || '';

  const languageMap: Record<string, string> = {
    ts: 'typescript',
    tsx: 'typescript',
    js: 'javascript',
    jsx: 'javascript',
    mjs: 'javascript',
    cjs: 'javascript',
    vue: 'vue',
    html: 'html',
    htm: 'html',
    css: 'css',
    scss: 'scss',
    sass: 'scss',
    less: 'less',
    json: 'json',
    yaml: 'yaml',
    yml: 'yaml',
    xml: 'xml',
    md: 'markdown',
    mdx: 'markdown',
    py: 'python',
    rs: 'rust',
    go: 'go',
    java: 'java',
    kt: 'kotlin',
    c: 'c',
    h: 'c',
    cpp: 'cpp',
    hpp: 'cpp',
    sh: 'shell',
    bash: 'shell',
    sql: 'sql',
    txt: 'plaintext',
  };

  return languageMap[ext] || 'plaintext';
}
