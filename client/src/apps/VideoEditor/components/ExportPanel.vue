<template>
  <div class="export-panel">
    <div class="text-h5 q-mb-md">Export Project</div>

    <!-- Export Status -->
    <q-card flat bordered class="q-mb-md">
      <q-card-section>
        <div class="text-subtitle1 q-mb-sm">Project Status</div>
        <div class="row q-gutter-md">
          <div class="col">
            <q-linear-progress
              :value="completionProgress"
              color="primary"
              size="24px"
              class="q-mb-sm"
            >
              <div class="absolute-full flex flex-center">
                <q-badge
                  color="white"
                  text-color="primary"
                  :label="`${Math.round(completionProgress * 100)}% Complete`"
                />
              </div>
            </q-linear-progress>
          </div>
        </div>

        <div class="row q-gutter-md q-mt-md">
          <div class="col text-center">
            <div class="text-h4">{{ totalClips }}</div>
            <div class="text-caption">Total Clips</div>
          </div>
          <div class="col text-center">
            <div class="text-h4 text-positive">{{ completedClips }}</div>
            <div class="text-caption">Completed</div>
          </div>
          <div class="col text-center">
            <div class="text-h4 text-warning">{{ pendingClips }}</div>
            <div class="text-caption">Pending</div>
          </div>
          <div class="col text-center">
            <div class="text-h4 text-negative">{{ staleClips }}</div>
            <div class="text-caption">Need Regen</div>
          </div>
        </div>
      </q-card-section>
    </q-card>

    <!-- Export Settings -->
    <q-card flat bordered class="q-mb-md">
      <q-card-section>
        <div class="text-subtitle1 q-mb-sm">Export Settings</div>

        <div class="row q-gutter-md">
          <q-select
            v-model="exportFormat"
            :options="formatOptions"
            label="Format"
            outlined
            emit-value
            map-options
            class="col"
          />
          <q-select
            v-model="exportQuality"
            :options="qualityOptions"
            label="Quality"
            outlined
            emit-value
            map-options
            class="col"
          />
        </div>

        <div class="row q-gutter-md q-mt-sm">
          <q-input v-model="outputFilename" label="Output Filename" outlined class="col">
            <template #append>.{{ exportFormat }}</template>
          </q-input>
        </div>
      </q-card-section>
    </q-card>

    <!-- Export Actions -->
    <q-card flat bordered>
      <q-card-section>
        <div class="row q-gutter-md">
          <q-btn
            :disable="staleClips > 0"
            color="primary"
            icon="movie"
            label="Export Video"
            size="lg"
            class="col"
            @click="exportVideo"
          />
          <q-btn
            v-if="staleClips > 0"
            color="warning"
            icon="refresh"
            label="Regenerate Stale Clips"
            size="lg"
            class="col"
            @click="regenerateStale"
          />
        </div>

        <q-banner v-if="staleClips > 0" class="bg-warning-1 q-mt-md">
          <template #avatar>
            <q-icon name="warning" color="warning" />
          </template>
          {{ staleClips }} clips need regeneration before export. Changes were made to scripts or
          keyframes since last generation.
        </q-banner>
      </q-card-section>
    </q-card>

    <!-- Export Progress -->
    <q-card v-if="isExporting" flat bordered class="q-mt-md">
      <q-card-section>
        <div class="text-subtitle1 q-mb-sm">Exporting...</div>
        <q-linear-progress :value="exportProgress" color="primary" size="24px" />
        <div class="text-caption text-grey q-mt-sm">{{ exportStage }}</div>
      </q-card-section>
    </q-card>
  </div>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue';
import { useVideoProjectStore, useVideoJobsStore } from '../stores';
import { isClipAudioStale, isClipVideoStale } from '../types';

const projectStore = useVideoProjectStore();
const jobsStore = useVideoJobsStore();

const timeline = computed(() => projectStore.timeline);

// Export settings
const exportFormat = ref('mp4');
const exportQuality = ref('high');
const outputFilename = ref('my_video');

const formatOptions = [
  { label: 'MP4 (H.264)', value: 'mp4' },
  { label: 'WebM (VP9)', value: 'webm' },
  { label: 'MOV (ProRes)', value: 'mov' },
];

const qualityOptions = [
  { label: 'Preview (Fast)', value: 'preview' },
  { label: 'Standard', value: 'standard' },
  { label: 'High Quality', value: 'high' },
  { label: 'Maximum', value: 'maximum' },
];

// Statistics
const totalClips = computed(() => timeline.value.clips.length);
const completedClips = computed(
  () => timeline.value.clips.filter((c) => c.status === 'done').length,
);
const pendingClips = computed(
  () =>
    timeline.value.clips.filter((c) => ['draft', 'queued', 'generating'].includes(c.status)).length,
);
const staleClips = computed(
  () =>
    timeline.value.clips.filter(
      (c) => c.status === 'done' && (isClipAudioStale(c) || isClipVideoStale(c)),
    ).length,
);

const completionProgress = computed(() => {
  if (totalClips.value === 0) return 0;
  return completedClips.value / totalClips.value;
});

// Export state
const isExporting = ref(false);
const exportProgress = ref(0);
const exportStage = ref('');

async function exportVideo(): Promise<void> {
  try {
    isExporting.value = true;
    exportStage.value = 'Starting export...';
    await jobsStore.exportProject();
  } catch (e) {
    console.error('Export failed:', e);
  } finally {
    isExporting.value = false;
  }
}

async function regenerateStale(): Promise<void> {
  const staleClipIds = timeline.value.clips
    .filter((c) => c.status === 'done' && (isClipAudioStale(c) || isClipVideoStale(c)))
    .map((c) => c.id);

  if (staleClipIds.length > 0) {
    await jobsStore.regenerateClips(staleClipIds, 'regen_all_stale');
  }
}
</script>

<style scoped lang="scss">
.export-panel {
  max-width: 800px;
  margin: 0 auto;
}
</style>
