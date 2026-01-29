/**
 * Configuration for file types that support preview mode
 * This registry defines which file extensions can be previewed and how
 */

export interface PreviewConfig {
  extensions: string[];
  component: string; // Vue component name
  label: string; // Display label, e.g. "Markdown Preview"
}

export const previewableTypes: PreviewConfig[] = [
  {
    extensions: ['md', 'markdown'],
    component: 'MarkdownPreview',
    label: 'Markdown Preview',
  },
  // Future: html, svg, etc.
];

/**
 * Check if a file extension supports preview mode
 */
export function isPreviewable(extension: string): boolean {
  if (!extension) return false;
  const normalized = extension.toLowerCase();
  return previewableTypes.some((config) =>
    config.extensions.includes(normalized),
  );
}

/**
 * Get the preview configuration for a file extension
 */
export function getPreviewConfig(
  extension: string,
): PreviewConfig | undefined {
  if (!extension) return undefined;
  const normalized = extension.toLowerCase();
  return previewableTypes.find((config) =>
    config.extensions.includes(normalized),
  );
}

/**
 * Extract file extension from a file path
 */
export function getFileExtension(filePath: string): string {
  const parts = filePath.split('.');
  if (parts.length < 2) return '';
  return parts.pop()?.toLowerCase() || '';
}
