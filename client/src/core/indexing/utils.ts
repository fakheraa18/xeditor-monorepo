// Utility functions for indexing

/**
 * Simple hash function for content (djb2 algorithm)
 */
export function hashContent(content: string): string {
  let hash = 5381;
  for (let i = 0; i < content.length; i++) {
    hash = ((hash << 5) + hash) + content.charCodeAt(i);
  }
  return hash.toString(36);
}

/**
 * Calculate cosine similarity between two vectors
 */
export function cosineSimilarity(a: Float32Array, b: Float32Array): number {
  if (a.length !== b.length) {
    throw new Error('Vectors must have the same length');
  }
  
  let dotProduct = 0;
  let normA = 0;
  let normB = 0;
  
  for (let i = 0; i < a.length; i++) {
    dotProduct += a[i]! * b[i]!;
    normA += a[i]! * a[i]!;
    normB += b[i]! * b[i]!;
  }
  
  const denominator = Math.sqrt(normA) * Math.sqrt(normB);
  if (denominator === 0) {
    return 0;
  }
  
  return dotProduct / denominator;
}

/**
 * Normalize a vector to unit length
 */
export function normalizeVector(vector: Float32Array): Float32Array {
  const norm = Math.sqrt(Array.from(vector).reduce((sum, val) => sum + val * val, 0));
  if (norm === 0) {
    return vector;
  }
  return new Float32Array(vector.map((val) => val / norm));
}

/**
 * Detect language from file extension
 */
export function detectLanguage(filePath: string): string {
  const ext = filePath.split('.').pop()?.toLowerCase() ?? '';
  
  const languageMap: Record<string, string> = {
    ts: 'typescript',
    tsx: 'tsx',
    js: 'javascript',
    jsx: 'jsx',
    py: 'python',
    rs: 'rust',
    go: 'go',
    java: 'java',
    cpp: 'cpp',
    c: 'c',
    cxx: 'cpp',
    h: 'c',
    hpp: 'cpp',
    vue: 'vue',
    html: 'html',
    css: 'css',
    scss: 'scss',
    json: 'json',
    yaml: 'yaml',
    yml: 'yaml',
    md: 'markdown',
    sql: 'sql',
    sh: 'bash',
    xml: 'xml',
  };
  
  return languageMap[ext] ?? 'plaintext';
}

/**
 * Check if a file should be indexed (skip node_modules, .git, etc.)
 * This is a safety net - the ignore evaluator is the primary filter
 */
export function shouldIndexFile(filePath: string, showHiddenFiles: boolean): boolean {
  const normalizedPath = filePath.replace(/\\/g, '/');
  const parts = normalizedPath.split('/');
  
  // Skip common vendor/build directories (check both as directory and as path segment)
  const excludedDirs = [
    'node_modules',
    '.git',
    '.svn',
    '.hg',
    'dist',
    'build',
    'out',
    '.next',
    '.nuxt',
    '.svelte-kit',
    '.quasar',
    '.vite',
    '.cache',
    '.turbo',
    'target',
    '__pycache__',
    '.venv',
    'venv',
    'env',
    'ENV',
    'site-packages',
    '.gradle',
    'vendor',
    'coverage',
    '.nyc_output',
    '.jest',
  ];
  
  for (const part of parts) {
    if (excludedDirs.includes(part)) {
      return false;
    }
  }
  
  // Skip hidden files/folders unless explicitly enabled
  if (!showHiddenFiles) {
    if (parts.some((part) => part.startsWith('.'))) {
      return false;
    }
  }
  
  // Skip binary-like extensions (must match backend _BINARY_EXTS)
  const binaryExts = ['png', 'jpg', 'jpeg', 'gif', 'svg', 'ico', 'woff', 'woff2', 'ttf', 'eot', 'pdf', 'zip', 'tar', 'gz', 'webp', 'eps'];
  const ext = filePath.split('.').pop()?.toLowerCase();
  if (ext && binaryExts.includes(ext)) {
    return false;
  }
  
  return true;
}

/**
 * Cooperative scheduling: yield to browser to keep UI responsive
 */
export function idle(): Promise<void> {
  return new Promise((resolve) => {
    if ('requestIdleCallback' in window) {
      requestIdleCallback(() => resolve(), { timeout: 50 });
    } else {
      setTimeout(() => resolve(), 0);
    }
  });
}

/**
 * Estimate memory usage for vectors
 */
export function estimateVectorMemory(chunkCount: number, vectorDim: number = 384): number {
  // Float32 = 4 bytes per float
  return chunkCount * vectorDim * 4;
}

/**
 * Get current heap memory usage if available
 */
export function getMemoryUsage(): { used: number; limit: number; available: boolean } {
  if ('memory' in performance && typeof (performance as { memory?: { usedJSHeapSize?: number; jsHeapSizeLimit?: number } }).memory !== 'undefined') {
    const mem = (performance as { memory: { usedJSHeapSize: number; jsHeapSizeLimit: number } }).memory;
    return {
      used: mem.usedJSHeapSize,
      limit: mem.jsHeapSizeLimit,
      available: true,
    };
  }
  return { used: 0, limit: 0, available: false };
}
