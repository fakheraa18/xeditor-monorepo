<template>
  <q-page class="video-editor-page">
    <!-- No project open - show wizard -->
    <div v-if="!projectStore.isOpen" class="flex flex-center full-height">
      <ProjectWizard @created="onProjectReady" @opened="onProjectReady" @cancel="goHome" />
    </div>

    <!-- Project open - Premiere-style workspace -->
    <div v-else class="workspace-container">
      <!-- Center: Video Player (upper portion) -->
      <div class="player-area">
        <VideoPlayer />
      </div>

      <!-- Bottom: Multi-track Timeline (full width below player) -->
      <div class="timeline-area">
        <TimelineEditor />
      </div>
    </div>

    <!-- Script Generator Dialog -->
    <q-dialog v-model="showScriptGeneratorLocal" position="right" full-height>
      <q-card style="width: 500px; max-width: 90vw">
        <q-card-section class="row items-center q-pb-none">
          <div class="text-h6">Script Generator</div>
          <q-space />
          <q-btn icon="close" flat round dense @click="showScriptGeneratorLocal = false" />
        </q-card-section>
        <q-card-section>
          <StoryDesigner />
        </q-card-section>
      </q-card>
    </q-dialog>
  </q-page>
</template>

<script setup lang="ts">
import { computed } from 'vue';
import { useRouter } from 'vue-router';
import { useVideoProjectStore } from '../stores';
import ProjectWizard from '../components/ProjectWizard.vue';
import VideoPlayer from '../components/VideoPlayer.vue';
import TimelineEditor from '../components/TimelineEditor.vue';
import StoryDesigner from '../components/StoryDesigner.vue';

const props = withDefaults(
  defineProps<{
    rightPanel?: string;
    showScriptGenerator?: boolean;
  }>(),
  {
    rightPanel: 'properties',
    showScriptGenerator: false,
  },
);

const emit = defineEmits<{
  'update:right-panel': [value: string];
  'update:show-script-generator': [value: boolean];
}>();

const router = useRouter();
const projectStore = useVideoProjectStore();

const showScriptGeneratorLocal = computed({
  get: () => props.showScriptGenerator,
  set: (val: boolean) => emit('update:show-script-generator', val),
});

function onProjectReady(): void {
  // Project opened, workspace shows automatically
}

function goHome(): void {
  void router.push('/');
}
</script>

<style scoped lang="scss">
.video-editor-page {
  height: 100%;
  display: flex;
  flex-direction: column;
}

.full-height {
  min-height: calc(100vh - 120px);
}

.workspace-container {
  display: flex;
  flex-direction: column;
  height: calc(100vh - 120px); // header 40px + footer 80px
  background: #f5f5f5;
}

.player-area {
  flex: 1;
  min-height: 200px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: #e0e0e0;
  border-bottom: 1px solid rgba(0, 0, 0, 0.1);
  overflow: hidden;
}

.timeline-area {
  height: 280px;
  min-height: 200px;
  background: #ffffff;
  overflow: hidden;
}
</style>
