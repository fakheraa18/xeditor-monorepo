<template>
  <div class="code-block-wrapper" :class="{ 'is-streaming': isStreaming }">
    <!-- Header with language and copy button -->
    <div class="code-block-header">
      <span class="code-language">{{ displayLanguage }}</span>
      <div class="code-actions">
        <q-btn
          flat
          dense
          round
          size="xs"
          :icon="copied ? 'check' : 'content_copy'"
          :color="copied ? 'positive' : 'grey-6'"
          class="copy-btn"
          @click="copyCode"
        >
          <q-tooltip :delay="300">{{ copied ? 'Copied!' : 'Copy code' }}</q-tooltip>
        </q-btn>
      </div>
    </div>
    <!-- Code content -->
    <div class="code-block-content">
      <pre><code :class="languageClass" v-html="highlightedCode"></code></pre>
    </div>
    <!-- Streaming indicator -->
    <div v-if="isStreaming" class="streaming-indicator">
      <q-spinner-dots size="16px" color="grey-5" />
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue';
import hljs from 'highlight.js';

const props = defineProps<{
  code: string;
  language?: string;
  isStreaming?: boolean;
}>();

const copied = ref(false);

const displayLanguage = computed(() => {
  if (!props.language) return 'code';
  // Map common language aliases to display names
  const languageMap: Record<string, string> = {
    js: 'JavaScript',
    ts: 'TypeScript',
    py: 'Python',
    rb: 'Ruby',
    sh: 'Shell',
    bash: 'Bash',
    zsh: 'Zsh',
    json: 'JSON',
    yaml: 'YAML',
    yml: 'YAML',
    md: 'Markdown',
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
  };
  return languageMap[props.language.toLowerCase()] || props.language;
});

const languageClass = computed(() => {
  if (!props.language) return '';
  return `language-${props.language} hljs`;
});

const highlightedCode = computed(() => {
  if (!props.code) return '';
  try {
    if (props.language && hljs.getLanguage(props.language)) {
      return hljs.highlight(props.code, { language: props.language }).value;
    }
    // Auto-detect language
    return hljs.highlightAuto(props.code).value;
  } catch {
    // Fallback: escape HTML
    return props.code
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;');
  }
});

async function copyCode() {
  try {
    await navigator.clipboard.writeText(props.code);
    copied.value = true;
    setTimeout(() => {
      copied.value = false;
    }, 2000);
  } catch (err) {
    console.error('Failed to copy code:', err);
  }
}
</script>

<style scoped>
.code-block-wrapper {
  margin: 12px 0;
  border-radius: 8px;
  overflow: hidden;
  background: #1e1e1e;
  border: 1px solid #333;
}

.code-block-wrapper.is-streaming {
  border-color: #7b1fa2;
}

.code-block-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 6px 12px;
  background: #2d2d2d;
  border-bottom: 1px solid #333;
}

.code-language {
  font-size: 11px;
  font-weight: 500;
  color: #888;
  text-transform: uppercase;
  letter-spacing: 0.5px;
}

.code-actions {
  display: flex;
  gap: 4px;
}

.copy-btn {
  opacity: 0.7;
  transition: opacity 0.2s ease;
}

.copy-btn:hover {
  opacity: 1;
}

.code-block-content {
  overflow-x: auto;
}

.code-block-content pre {
  margin: 0;
  padding: 12px 16px;
  background: transparent;
}

.code-block-content code {
  font-family: 'JetBrains Mono', 'Fira Code', Consolas, monospace;
  font-size: 12px;
  line-height: 1.5;
  color: #d4d4d4;
  display: block;
  white-space: pre;
}

/* Syntax highlighting colors */
.code-block-content :deep(.hljs-keyword) {
  color: #569cd6;
}

.code-block-content :deep(.hljs-string) {
  color: #ce9178;
}

.code-block-content :deep(.hljs-comment) {
  color: #6a9955;
}

.code-block-content :deep(.hljs-function) {
  color: #dcdcaa;
}

.code-block-content :deep(.hljs-number) {
  color: #b5cea8;
}

.code-block-content :deep(.hljs-class) {
  color: #4ec9b0;
}

.code-block-content :deep(.hljs-variable) {
  color: #9cdcfe;
}

.code-block-content :deep(.hljs-attr) {
  color: #9cdcfe;
}

.code-block-content :deep(.hljs-built_in) {
  color: #4ec9b0;
}

.code-block-content :deep(.hljs-title) {
  color: #dcdcaa;
}

.code-block-content :deep(.hljs-params) {
  color: #9cdcfe;
}

.streaming-indicator {
  display: flex;
  justify-content: flex-end;
  padding: 4px 12px 8px;
  background: #1e1e1e;
}
</style>
