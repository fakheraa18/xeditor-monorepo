<template>
  <q-card style="min-width: 500px">
    <q-card-section class="bg-primary text-white">
      <div class="text-h6">Project Settings</div>
    </q-card-section>

    <q-card-section>
      <q-tabs v-model="tab" class="text-primary" align="justify">
        <q-tab name="canvas" label="Canvas" icon="aspect_ratio" />
        <q-tab name="generators" label="Generators" icon="auto_awesome" />
        <q-tab name="performance" label="Performance" icon="speed" />
      </q-tabs>

      <q-separator />

      <q-tab-panels v-model="tab" animated class="q-pt-md">
        <!-- Canvas Settings -->
        <q-tab-panel name="canvas">
          <div class="q-gutter-md">
            <q-select
              v-model="localSettings.canvas.preset"
              :options="canvasPresetOptions"
              label="Preset"
              outlined
              emit-value
              map-options
              @update:model-value="applyPreset"
            />

            <div class="row q-gutter-md">
              <q-input
                v-model.number="localSettings.canvas.width"
                label="Width"
                type="number"
                outlined
                class="col"
              />
              <q-input
                v-model.number="localSettings.canvas.height"
                label="Height"
                type="number"
                outlined
                class="col"
              />
            </div>

            <div class="row q-gutter-md">
              <q-input
                v-model.number="localSettings.canvas.fps"
                label="FPS"
                type="number"
                outlined
                class="col"
              />
              <q-select
                v-model="localSettings.canvas.orientation"
                :options="orientationOptions"
                label="Orientation"
                outlined
                emit-value
                map-options
                class="col"
              />
            </div>
          </div>
        </q-tab-panel>

        <!-- Generator Settings -->
        <q-tab-panel name="generators">
          <div class="q-gutter-md">
            <q-select
              v-model="localSettings.default_generators.story_llm"
              :options="llmOptions"
              label="Story LLM"
              outlined
              emit-value
              map-options
              clearable
            />

            <q-select
              v-model="localSettings.default_generators.tts"
              :options="ttsOptions"
              label="TTS Engine"
              outlined
              emit-value
              map-options
              clearable
            />

            <q-select
              v-model="localSettings.default_generators.t2i"
              :options="imageOptions"
              label="Image Generator"
              outlined
              emit-value
              map-options
              clearable
            />

            <q-select
              v-model="localSettings.default_generators.i2v"
              :options="videoOptions"
              label="Video Generator"
              outlined
              emit-value
              map-options
              clearable
            />
          </div>
        </q-tab-panel>

        <!-- Performance Settings -->
        <q-tab-panel name="performance">
          <div class="q-gutter-md">
            <q-select
              v-model="localSettings.vram_target_gb"
              :options="vramOptions"
              label="VRAM Target"
              outlined
              emit-value
              map-options
            />

            <q-banner class="bg-info-1">
              <template #avatar>
                <q-icon name="info" color="info" />
              </template>
              The VRAM target helps the system choose appropriate models and manage GPU memory. Set
              this to your GPU's VRAM capacity.
            </q-banner>
          </div>
        </q-tab-panel>
      </q-tab-panels>
    </q-card-section>

    <q-separator />

    <q-card-actions align="right" class="q-pa-md">
      <q-btn flat label="Cancel" color="grey" @click="emit('close')" />
      <q-btn label="Save" color="primary" @click="saveSettings" />
    </q-card-actions>
  </q-card>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue';
import { useVideoProjectStore, useVideoJobsStore } from '../stores';
import { CANVAS_PRESETS, type ProjectSettings } from '../types';

const emit = defineEmits<{
  close: [];
}>();

const projectStore = useVideoProjectStore();
const jobsStore = useVideoJobsStore();

const tab = ref('canvas');

// Local copy of settings for editing
const localSettings = ref<ProjectSettings>({
  vram_target_gb: 24,
  canvas: {
    preset: '1080p_landscape',
    width: 1920,
    height: 1080,
    fps: 30,
    orientation: 'landscape',
  },
  default_generators: {},
  generator_configs: {},
});

// Options
const canvasPresetOptions = computed(() =>
  Object.entries(CANVAS_PRESETS).map(([key, preset]) => ({
    label: preset.name,
    value: key,
  })),
);

const orientationOptions = [
  { label: 'Landscape', value: 'landscape' },
  { label: 'Portrait', value: 'portrait' },
  { label: 'Square', value: 'square' },
];

const vramOptions = [
  { label: '8 GB', value: 8 },
  { label: '12 GB', value: 12 },
  { label: '16 GB', value: 16 },
  { label: '24 GB', value: 24 },
];

const llmOptions = computed(() =>
  jobsStore.llmGenerators.map((g) => ({
    label: g.title,
    value: g.id,
  })),
);

const ttsOptions = computed(() =>
  jobsStore.ttsGenerators.map((g) => ({
    label: g.title,
    value: g.id,
  })),
);

const imageOptions = computed(() =>
  jobsStore.imageGenerators.map((g) => ({
    label: g.title,
    value: g.id,
  })),
);

const videoOptions = computed(() =>
  jobsStore.videoGenerators.map((g) => ({
    label: g.title,
    value: g.id,
  })),
);

function applyPreset(presetKey: string | null): void {
  if (!presetKey) return;
  const preset = CANVAS_PRESETS[presetKey];
  if (preset) {
    localSettings.value.canvas = {
      preset: presetKey,
      width: preset.width,
      height: preset.height,
      fps: preset.fps,
      orientation: preset.orientation,
    };
  }
}

async function saveSettings(): Promise<void> {
  try {
    await projectStore.updateSettings(localSettings.value);
    emit('close');
  } catch (e) {
    console.error('Failed to save settings:', e);
  }
}

onMounted(() => {
  // Copy current settings
  localSettings.value = JSON.parse(JSON.stringify(projectStore.settings));
});
</script>
