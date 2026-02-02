<template>
  <div class="markdown-preview-container">
    <div class="markdown-preview-content" v-html="renderedContent" />
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue';
import { useMarkdown } from '../../../components/ai/AIPanel/composables/useMarkdown';

interface Props {
  content: string;
  filePath?: string;
}

const props = defineProps<Props>();

const { renderMarkdown } = useMarkdown();

const renderedContent = computed(() => {
  return renderMarkdown(props.content || '', false);
});
</script>

<style scoped>
.markdown-preview-container {
  height: 100%;
  overflow-y: auto;
  overflow-x: hidden;
  background: #ffffff;
  padding: 24px;
}

.markdown-preview-content {
  max-width: 900px;
  margin: 0 auto;
  line-height: 1.6;
  color: #1a1a1a;
}

/* Markdown content styling */
:deep(.markdown-preview-content) {
  font-family:
    -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif;
}

:deep(.markdown-preview-content h1) {
  font-size: 2em;
  font-weight: 600;
  margin-top: 0.67em;
  margin-bottom: 0.67em;
  border-bottom: 1px solid #e0e0e0;
  padding-bottom: 0.3em;
}

:deep(.markdown-preview-content h2) {
  font-size: 1.5em;
  font-weight: 600;
  margin-top: 0.83em;
  margin-bottom: 0.83em;
  border-bottom: 1px solid #e0e0e0;
  padding-bottom: 0.3em;
}

:deep(.markdown-preview-content h3) {
  font-size: 1.17em;
  font-weight: 600;
  margin-top: 1em;
  margin-bottom: 1em;
}

:deep(.markdown-preview-content h4) {
  font-size: 1em;
  font-weight: 600;
  margin-top: 1.33em;
  margin-bottom: 1.33em;
}

:deep(.markdown-preview-content h5) {
  font-size: 0.83em;
  font-weight: 600;
  margin-top: 1.67em;
  margin-bottom: 1.67em;
}

:deep(.markdown-preview-content h6) {
  font-size: 0.67em;
  font-weight: 600;
  margin-top: 2.33em;
  margin-bottom: 2.33em;
}

:deep(.markdown-preview-content p) {
  margin-top: 1em;
  margin-bottom: 1em;
}

:deep(.markdown-preview-content ul),
:deep(.markdown-preview-content ol) {
  margin-top: 1em;
  margin-bottom: 1em;
  padding-left: 2em;
}

:deep(.markdown-preview-content li) {
  margin-top: 0.5em;
  margin-bottom: 0.5em;
}

:deep(.markdown-preview-content blockquote) {
  margin: 1em 0;
  padding-left: 1em;
  border-left: 4px solid #1976d2;
  color: #616161;
  font-style: italic;
}

:deep(.markdown-preview-content code) {
  background: #f5f5f5;
  padding: 2px 6px;
  border-radius: 3px;
  font-family: 'JetBrains Mono', 'Fira Code', 'Cascadia Code', Consolas, 'Courier New', monospace;
  font-size: 0.9em;
}

:deep(.markdown-preview-content pre) {
  background: #f5f5f5;
  padding: 16px;
  border-radius: 6px;
  overflow-x: auto;
  margin: 1em 0;
}

:deep(.markdown-preview-content pre code) {
  background: transparent;
  padding: 0;
}

:deep(.markdown-preview-content a) {
  color: #1976d2;
  text-decoration: none;
}

:deep(.markdown-preview-content a:hover) {
  text-decoration: underline;
}

:deep(.markdown-preview-content table) {
  border-collapse: collapse;
  margin: 1em 0;
  width: 100%;
}

:deep(.markdown-preview-content th),
:deep(.markdown-preview-content td) {
  border: 1px solid #e0e0e0;
  padding: 8px 12px;
  text-align: left;
}

:deep(.markdown-preview-content th) {
  background: #f5f5f5;
  font-weight: 600;
}

:deep(.markdown-preview-content hr) {
  border: none;
  border-top: 1px solid #e0e0e0;
  margin: 2em 0;
}

:deep(.markdown-preview-content img) {
  max-width: 100%;
  height: auto;
  border-radius: 4px;
  margin: 1em 0;
}

/* Code block wrapper styling */
:deep(.code-block-wrapper) {
  margin: 1em 0;
  border-radius: 6px;
  overflow: hidden;
  border: 1px solid #e0e0e0;
}

:deep(.code-block-header) {
  background: #f5f5f5;
  padding: 8px 12px;
  display: flex;
  justify-content: space-between;
  align-items: center;
  border-bottom: 1px solid #e0e0e0;
}

:deep(.code-language) {
  font-size: 12px;
  font-weight: 500;
  color: #616161;
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
}

:deep(.code-copy-btn) {
  background: transparent;
  border: none;
  cursor: pointer;
  padding: 4px;
  display: flex;
  align-items: center;
  justify-content: center;
  color: #616161;
  border-radius: 3px;
  transition:
    background-color 0.15s ease,
    color 0.15s ease;
}

:deep(.code-copy-btn:hover) {
  background: rgba(0, 0, 0, 0.05);
  color: #1976d2;
}

:deep(.code-block-wrapper pre) {
  margin: 0;
  border-radius: 0;
}

/* Syntax highlighting styles */
:deep(.hljs) {
  background: #f5f5f5;
  color: #1a1a1a;
}
</style>
