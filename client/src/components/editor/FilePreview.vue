<template>
  <component
    :is="previewComponent"
    v-if="previewComponent"
    :content="content"
    :file-path="filePath"
  />
  <div v-else class="preview-error">
    <q-icon name="error_outline" size="48px" color="grey-5" />
    <div class="error-message">Preview not available for this file type</div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue';
import { getPreviewConfig, getFileExtension } from '../../config/previewable';
import MarkdownPreview from './previews/MarkdownPreview.vue';

interface Props {
  content: string;
  filePath: string;
}

const props = defineProps<Props>();

// Map component names to actual Vue components
const componentMap: Record<string, typeof MarkdownPreview> = {
  MarkdownPreview,
};

const previewComponent = computed(() => {
  const extension = getFileExtension(props.filePath);
  const config = getPreviewConfig(extension);
  if (!config) return null;
  return componentMap[config.component] || null;
});
</script>

<style scoped>
.preview-error {
  height: 100%;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  background: #fafafa;
  color: #616161;
}

.error-message {
  margin-top: 16px;
  font-size: 14px;
}
</style>
