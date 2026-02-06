<template>
  <div class="generation-queue-panel q-pa-sm">
    <div class="row items-center">
      <div class="text-subtitle2 text-dark">Generation Queue</div>
      <q-space />
      <q-btn
        v-if="completedJobs.length > 0"
        flat
        size="sm"
        color="primary"
        label="Clear Completed"
        @click="clearCompleted"
      />
    </div>

    <div class="queue-content row q-gutter-sm q-mt-sm">
      <!-- Active Job -->
      <div v-if="activeJob" class="active-job col-4">
        <q-card flat class="bg-grey-2">
          <q-card-section class="q-pa-sm">
            <div class="row items-center">
              <q-spinner color="primary" size="sm" class="q-mr-sm" />
              <span class="text-caption text-dark">{{ getJobLabel(activeJob) }}</span>
              <q-space />
              <q-btn
                flat
                round
                size="xs"
                icon="close"
                color="grey-7"
                @click="cancelJob(activeJob.id)"
              />
            </div>
            <q-linear-progress
              :value="activeProgress?.overall_progress || 0"
              color="primary"
              size="4px"
              class="q-mt-sm"
            />
            <div class="text-caption text-grey-8 q-mt-xs">
              {{ activeProgress?.message || 'Starting...' }}
            </div>
          </q-card-section>
        </q-card>
      </div>

      <!-- Pending Jobs -->
      <div v-for="job in pendingJobs.slice(0, 5)" :key="job.id" class="pending-job">
        <q-chip
          :removable="job.status === 'queued'"
          color="grey-3"
          text-color="dark"
          size="sm"
          @remove="cancelJob(job.id)"
        >
          <q-icon :name="getJobIcon(job.type)" class="q-mr-xs" />
          {{ getJobLabel(job) }}
        </q-chip>
      </div>

      <!-- More indicator -->
      <div v-if="pendingJobs.length > 5" class="text-grey-8">
        +{{ pendingJobs.length - 5 }} more
      </div>

      <!-- No jobs message -->
      <div v-if="!activeJob && pendingJobs.length === 0" class="text-grey-8 text-caption">
        No active generation jobs
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue';
import { useVideoJobsStore } from '../stores';
import type { Job, JobType } from '../types';

const jobsStore = useVideoJobsStore();

const activeJob = computed(() => jobsStore.activeJob);
const activeProgress = computed(() => jobsStore.activeJobProgress);
const pendingJobs = computed(() => jobsStore.pendingJobs);
const completedJobs = computed(() => jobsStore.completedJobs);

function getJobIcon(type: JobType): string {
  switch (type) {
    case 'script_generate':
      return 'auto_stories';
    case 'tts_generate':
      return 'record_voice_over';
    case 'image_generate':
      return 'image';
    case 'video_generate':
      return 'videocam';
    case 'music_generate':
      return 'music_note';
    case 'final_merge':
      return 'movie';
    default:
      return 'pending';
  }
}

function getJobLabel(job: Job): string {
  switch (job.type) {
    case 'script_generate':
      return 'Story';
    case 'tts_generate':
      return `Audio (${job.clip_ids.length})`;
    case 'image_generate':
      return `Image (${job.clip_ids.length})`;
    case 'video_generate':
      return `Video (${job.clip_ids.length})`;
    case 'music_generate':
      return 'Music';
    case 'final_merge':
      return 'Export';
    default:
      return 'Job';
  }
}

async function cancelJob(jobId: string): Promise<void> {
  try {
    await jobsStore.cancelJob(jobId);
  } catch (e) {
    console.error('Failed to cancel job:', e);
  }
}

function clearCompleted(): void {
  jobsStore.clearCompleted();
}
</script>

<style scoped lang="scss">
.generation-queue-panel {
  height: 100%;
}

.queue-content {
  align-items: center;
  flex-wrap: wrap;
}

.active-job {
  max-width: 300px;
}
</style>
