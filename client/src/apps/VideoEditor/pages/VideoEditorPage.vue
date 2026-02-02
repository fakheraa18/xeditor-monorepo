<template>
  <q-page class="video-editor-page">
    <!-- No project open - show wizard -->
    <div v-if="!projectStore.isOpen" class="flex flex-center full-height">
      <ProjectWizard @created="onProjectReady" @opened="onProjectReady" @cancel="goHome" />
    </div>

    <!-- Project open - show main content based on active tab -->
    <div v-else class="main-content q-pa-md">
      <StoryDesigner v-if="activeTab === 'story'" />
      <AssetManager v-else-if="activeTab === 'assets'" />
      <TimelineEditor v-else-if="activeTab === 'timeline'" />
      <ExportPanel v-else-if="activeTab === 'export'" />
    </div>
  </q-page>
</template>

<script setup lang="ts">
import { toRef } from 'vue';
import { useRouter } from 'vue-router';
import { useVideoProjectStore } from '../stores';
import ProjectWizard from '../components/ProjectWizard.vue';
import StoryDesigner from '../components/StoryDesigner.vue';
import AssetManager from '../components/AssetManager.vue';
import TimelineEditor from '../components/TimelineEditor.vue';
import ExportPanel from '../components/ExportPanel.vue';

// Props from layout
const props = withDefaults(
  defineProps<{
    activeTab?: 'story' | 'assets' | 'timeline' | 'export';
  }>(),
  {
    activeTab: 'story',
  },
);

const emit = defineEmits<{
  'update:active-tab': [value: 'story' | 'assets' | 'timeline' | 'export'];
}>();

const router = useRouter();
const projectStore = useVideoProjectStore();

// Reactive reference to activeTab prop
const activeTab = toRef(props, 'activeTab');

// Methods
function onProjectReady(): void {
  // Project is now open, emit to show story tab
  emit('update:active-tab', 'story');
}

function goHome(): void {
  void router.push('/');
}
</script>

<style scoped lang="scss">
.video-editor-page {
  height: 100%;
}

.full-height {
  min-height: calc(100vh - 100px);
}

.main-content {
  height: 100%;
  overflow: auto;
  background: var(--q-grey-3);
}
</style>
