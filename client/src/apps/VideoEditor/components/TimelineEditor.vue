<template>
  <div class="timeline-editor">
    <div class="row items-center q-mb-md">
      <div class="text-h5">Timeline</div>
      <q-space />
      <q-btn-toggle
        v-model="viewMode"
        :options="[
          { label: 'Script', value: 'script' },
          { label: 'Video', value: 'video' },
        ]"
        color="primary"
        toggle-color="primary"
      />
      <q-btn flat icon="zoom_out" class="q-ml-md" @click="zoomOut" />
      <q-btn flat icon="zoom_in" @click="zoomIn" />
    </div>

    <!-- Timeline Header -->
    <div class="timeline-header bg-grey-3 q-pa-sm">
      <div class="row items-center">
        <div class="track-label">Tracks</div>
        <div class="timeline-ruler">
          <div
            v-for="marker in timeMarkers"
            :key="marker.time"
            class="time-marker"
            :style="{ left: `${marker.position}%` }"
          >
            {{ formatTime(marker.time) }}
          </div>
        </div>
      </div>
    </div>

    <!-- Timeline Tracks -->
    <div class="timeline-tracks">
      <div v-for="track in timeline.tracks" :key="track.id" class="timeline-track">
        <div class="track-header bg-grey-2">
          <q-icon :name="track.type === 'video' ? 'videocam' : 'audiotrack'" class="q-mr-sm" />
          {{ track.name }}
          <q-space />
          <q-btn
            flat
            round
            size="sm"
            :icon="track.muted ? 'volume_off' : 'volume_up'"
            @click="toggleMute(track)"
          />
          <q-btn
            flat
            round
            size="sm"
            :icon="track.locked ? 'lock' : 'lock_open'"
            @click="toggleLock(track)"
          />
        </div>
        <div class="track-content" @click="handleTrackClick($event, track)">
          <div
            v-for="clip in getTrackClips(track.id)"
            :key="clip.id"
            class="timeline-clip"
            :class="[`status-${clip.status}`, { selected: selectedClipId === clip.id }]"
            :style="getClipStyle(clip)"
            @click.stop="selectClip(clip.id)"
          >
            <div class="clip-content">
              <q-icon v-if="clip.status === 'generating'" name="sync" class="rotating" />
              <q-icon v-else-if="clip.status === 'done'" name="check" color="positive" />
              <q-icon v-else-if="clip.status === 'error'" name="error" color="negative" />
              <span class="clip-label">{{ getClipLabel(clip) }}</span>
            </div>
            <div v-if="isClipStale(clip)" class="stale-indicator">
              <q-icon name="warning" color="warning" size="xs" />
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- Timeline Controls -->
    <div class="timeline-controls bg-grey-2 q-pa-sm">
      <div class="row items-center">
        <q-btn flat round icon="skip_previous" />
        <q-btn flat round icon="play_arrow" />
        <q-btn flat round icon="skip_next" />
        <q-separator vertical class="q-mx-sm" />
        <span class="text-body2"
          >{{ formatTime(currentTime) }} / {{ formatTime(timeline.total_duration) }}</span
        >
        <q-space />
        <q-btn flat icon="add" label="Add Clips from Scenes" @click="addClipFromScene" />
        <q-btn-dropdown flat icon="auto_awesome" label="Generate" color="primary">
          <q-list>
            <q-item clickable v-close-popup @click="generateAll">
              <q-item-section avatar>
                <q-icon name="record_voice_over" />
              </q-item-section>
              <q-item-section>
                <q-item-label>Generate Audio (TTS)</q-item-label>
                <q-item-label caption>Create speech from narration</q-item-label>
              </q-item-section>
            </q-item>
            <q-item clickable v-close-popup @click="generateImages">
              <q-item-section avatar>
                <q-icon name="image" />
              </q-item-section>
              <q-item-section>
                <q-item-label>Generate Images</q-item-label>
                <q-item-label caption>Create visuals from prompts</q-item-label>
              </q-item-section>
            </q-item>
            <q-item clickable v-close-popup @click="generateVideos">
              <q-item-section avatar>
                <q-icon name="movie" />
              </q-item-section>
              <q-item-section>
                <q-item-label>Generate Videos</q-item-label>
                <q-item-label caption>Create video clips from images</q-item-label>
              </q-item-section>
            </q-item>
            <q-separator />
            <q-item clickable v-close-popup @click="exportVideo">
              <q-item-section avatar>
                <q-icon name="file_download" />
              </q-item-section>
              <q-item-section>
                <q-item-label>Export Final Video</q-item-label>
                <q-item-label caption>Merge all clips to MP4</q-item-label>
              </q-item-section>
            </q-item>
          </q-list>
        </q-btn-dropdown>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue';
import { useVideoProjectStore, useVideoJobsStore } from '../stores';
import type { TimelineClip, TimelineTrack } from '../types';
import { isClipAudioStale, isClipVideoStale } from '../types';

const projectStore = useVideoProjectStore();
const jobsStore = useVideoJobsStore();

const timeline = computed(() => projectStore.timeline);
const story = computed(() => projectStore.story);

const viewMode = ref<'script' | 'video'>('script');
const zoom = ref(1);
const currentTime = ref(0);
const selectedClipId = ref<string | null>(null);

const timeMarkers = computed(() => {
  const duration = timeline.value.total_duration || 60;
  const markers = [];
  const step = duration > 300 ? 60 : duration > 60 ? 10 : 5;

  for (let t = 0; t <= duration; t += step) {
    markers.push({
      time: t,
      position: (t / duration) * 100,
    });
  }

  return markers;
});

function getTrackClips(trackId: string): TimelineClip[] {
  return timeline.value.clips.filter((c) => c.track_id === trackId);
}

function getClipStyle(clip: TimelineClip): Record<string, string> {
  const duration = timeline.value.total_duration || 60;
  const left = (clip.start_time / duration) * 100;
  const width = (clip.duration / duration) * 100;

  return {
    left: `${left}%`,
    width: `${Math.max(width, 2)}%`,
  };
}

function getClipLabel(clip: TimelineClip): string {
  if (clip.scene_id) {
    const scene = story.value.scenes.find((s) => s.id === clip.scene_id);
    return scene?.title || `Scene`;
  }
  return `Clip`;
}

function isClipStale(clip: TimelineClip): boolean {
  return isClipAudioStale(clip) || isClipVideoStale(clip);
}

function selectClip(clipId: string): void {
  selectedClipId.value = clipId;
}

function handleTrackClick(event: MouseEvent, track: TimelineTrack): void {
  if (track.locked) return;
  // TODO: Handle adding clip at clicked position
}

function toggleMute(track: TimelineTrack): void {
  track.muted = !track.muted;
}

function toggleLock(track: TimelineTrack): void {
  track.locked = !track.locked;
}

function zoomIn(): void {
  zoom.value = Math.min(zoom.value * 1.2, 4);
}

function zoomOut(): void {
  zoom.value = Math.max(zoom.value / 1.2, 0.25);
}

function formatTime(seconds: number): string {
  const mins = Math.floor(seconds / 60);
  const secs = Math.floor(seconds % 60);
  return `${mins}:${secs.toString().padStart(2, '0')}`;
}

function addClipFromScene(): void {
  const scenes = story.value.scenes;
  if (scenes.length === 0) {
    alert('No scenes available. Create scenes in the Story Designer first.');
    return;
  }

  // Add clips for all scenes
  let startTime = timeline.value.total_duration;
  for (const scene of scenes) {
    projectStore.addClip({
      track_id: 'main',
      start_time: startTime,
      duration: scene.duration_estimate || 5,
      source_type: 'placeholder',
      scene_id: scene.id,
      status: 'draft',
      script_line_ids: [],
    });
    startTime += scene.duration_estimate || 5;
  }
}

async function generateAll(): Promise<void> {
  const clipIds = timeline.value.clips.map((c) => c.id);
  if (clipIds.length === 0) {
    alert('No clips on timeline');
    return;
  }

  try {
    // Start audio generation first (images and video can follow)
    await jobsStore.generateAudio({ clipIds });
    // Note: Subsequent steps (image, video) can be triggered via UI
    // after audio completes, or wired into a full pipeline
  } catch (e) {
    console.error('Failed to start generation:', e);
  }
}

async function generateImages(): Promise<void> {
  const clipIds = timeline.value.clips.map((c) => c.id);
  if (clipIds.length === 0) {
    alert('No clips on timeline');
    return;
  }

  try {
    await jobsStore.generateImages({ clipIds });
  } catch (e) {
    console.error('Failed to start image generation:', e);
  }
}

async function generateVideos(): Promise<void> {
  const clipIds = timeline.value.clips.map((c) => c.id);
  if (clipIds.length === 0) {
    alert('No clips on timeline');
    return;
  }

  try {
    await jobsStore.generateVideo({ clipIds });
  } catch (e) {
    console.error('Failed to start video generation:', e);
  }
}

async function exportVideo(): Promise<void> {
  try {
    await jobsStore.exportProject();
  } catch (e) {
    console.error('Failed to start export:', e);
  }
}
</script>

<style scoped lang="scss">
.timeline-editor {
  height: 100%;
  display: flex;
  flex-direction: column;
}

.timeline-header {
  flex-shrink: 0;
  border-bottom: 1px solid var(--q-grey-4);
}

.track-label {
  width: 120px;
  flex-shrink: 0;
}

.timeline-ruler {
  flex: 1;
  position: relative;
  height: 24px;
}

.time-marker {
  position: absolute;
  font-size: 10px;
  color: var(--q-grey-7);
  transform: translateX(-50%);
}

.timeline-tracks {
  flex: 1;
  overflow-y: auto;
  background: #ffffff;
}

.timeline-track {
  display: flex;
  border-bottom: 1px solid var(--q-grey-3);
  min-height: 60px;
}

.track-header {
  width: 120px;
  flex-shrink: 0;
  padding: 8px;
  display: flex;
  align-items: center;
  border-right: 1px solid var(--q-grey-3);
}

.track-content {
  flex: 1;
  position: relative;
  background: #f8f9fa;
}

.timeline-clip {
  position: absolute;
  top: 4px;
  bottom: 4px;
  background: var(--q-primary);
  border-radius: 4px;
  cursor: pointer;
  overflow: hidden;
  transition:
    transform 0.1s,
    box-shadow 0.1s;

  &:hover {
    transform: translateY(-1px);
    box-shadow: 0 2px 4px rgba(0, 0, 0, 0.2);
  }

  &.selected {
    box-shadow: 0 0 0 2px var(--q-primary);
  }

  &.status-draft {
    background: var(--q-grey-5);
  }

  &.status-generating {
    background: var(--q-info);
  }

  &.status-done {
    background: var(--q-positive);
  }

  &.status-error {
    background: var(--q-negative);
  }
}

.clip-content {
  padding: 4px 8px;
  color: white;
  font-size: 12px;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.clip-label {
  margin-left: 4px;
}

.stale-indicator {
  position: absolute;
  top: 2px;
  right: 2px;
}

.timeline-controls {
  flex-shrink: 0;
  border-top: 1px solid var(--q-grey-4);
}

.rotating {
  animation: rotate 1s linear infinite;
}

@keyframes rotate {
  from {
    transform: rotate(0deg);
  }
  to {
    transform: rotate(360deg);
  }
}
</style>
