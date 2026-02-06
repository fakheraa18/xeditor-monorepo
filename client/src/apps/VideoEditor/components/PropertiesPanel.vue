<template>
  <div class="properties-panel q-pa-sm">
    <div class="text-subtitle2 q-mb-sm">Properties</div>

    <div v-if="!selectedItem" class="text-center q-pa-lg text-grey">
      <q-icon name="touch_app" size="48px" class="q-mb-md" />
      <div>Select an item to view properties</div>
    </div>

    <!-- Clip Properties -->
    <div v-else-if="selectedItem.type === 'clip'" class="clip-properties">
      <q-list>
        <q-item-label header>Clip Settings</q-item-label>

        <q-item>
          <q-item-section>
            <q-item-label caption>Start Time</q-item-label>
            <q-input
              :model-value="selectedClip?.start_time"
              type="number"
              dense
              outlined
              suffix="s"
              @update:model-value="updateClipStartTime"
            />
          </q-item-section>
        </q-item>

        <q-item>
          <q-item-section>
            <q-item-label caption>Duration</q-item-label>
            <q-input
              :model-value="selectedClip?.duration"
              type="number"
              dense
              outlined
              suffix="s"
              @update:model-value="updateClipDuration"
            />
          </q-item-section>
        </q-item>

        <q-separator />

        <q-item-label header>Generation</q-item-label>

        <q-item>
          <q-item-section>
            <q-item-label caption>Mode</q-item-label>
            <q-select
              :model-value="selectedClip?.generation_spec?.mode || 'prompt_only'"
              :options="generationModes"
              dense
              outlined
              emit-value
              map-options
              @update:model-value="updateGenerationMode"
            />
          </q-item-section>
        </q-item>

        <q-item>
          <q-item-section>
            <q-item-label caption>Prompt</q-item-label>
            <q-input
              :model-value="selectedClip?.generation_spec?.prompt"
              type="textarea"
              dense
              outlined
              rows="3"
              @update:model-value="updatePrompt"
            />
          </q-item-section>
        </q-item>

        <q-separator />

        <q-item-label header>Actions</q-item-label>

        <q-item>
          <q-item-section>
            <div class="q-gutter-sm">
              <q-btn
                flat
                icon="image"
                label="Generate Keyframe"
                size="sm"
                color="primary"
                class="full-width"
              />
              <q-btn
                flat
                icon="videocam"
                label="Generate Video"
                size="sm"
                color="primary"
                class="full-width"
              />
              <q-btn
                flat
                icon="audiotrack"
                label="Generate Audio"
                size="sm"
                color="primary"
                class="full-width"
              />
            </div>
          </q-item-section>
        </q-item>
      </q-list>
    </div>

    <!-- Scene Properties -->
    <div v-else-if="selectedItem.type === 'scene'" class="scene-properties">
      <q-list>
        <q-item-label header>Scene Settings</q-item-label>
        <q-item>
          <q-item-section>
            <q-item-label caption>Title</q-item-label>
            <q-input :model-value="selectedScene?.title" dense outlined />
          </q-item-section>
        </q-item>
      </q-list>
    </div>

    <!-- Character Properties -->
    <div v-else-if="selectedItem.type === 'character'" class="character-properties">
      <q-list>
        <q-item-label header>Character Settings</q-item-label>
        <q-item>
          <q-item-section>
            <q-item-label caption>Name</q-item-label>
            <q-input :model-value="selectedCharacter?.name" dense outlined />
          </q-item-section>
        </q-item>
        <q-item>
          <q-item-section>
            <q-item-label caption>Code</q-item-label>
            <q-input :model-value="selectedCharacter?.code" dense outlined />
          </q-item-section>
        </q-item>
      </q-list>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue';
import { useVideoProjectStore } from '../stores';
import type { TimelineClip, StoryScene, CharacterAsset } from '../types';

const projectStore = useVideoProjectStore();

interface SelectedItem {
  type: 'clip' | 'scene' | 'character' | 'prop' | 'voice';
  id: string;
}

const selectedItem = ref<SelectedItem | null>(null);

const generationModes = [
  { label: 'Prompt Only', value: 'prompt_only' },
  { label: 'Image to Video (I2V)', value: 'i2v' },
  { label: 'First+Last Frame (FLF)', value: 'flf' },
  { label: 'Text to Video (T2V)', value: 't2v' },
];

const selectedClip = computed<TimelineClip | undefined>(() => {
  if (selectedItem.value?.type !== 'clip') return undefined;
  return projectStore.timeline.clips.find((c) => c.id === selectedItem.value?.id);
});

const selectedScene = computed<StoryScene | undefined>(() => {
  if (selectedItem.value?.type !== 'scene') return undefined;
  return projectStore.story.scenes.find((s) => s.id === selectedItem.value?.id);
});

const selectedCharacter = computed<CharacterAsset | undefined>(() => {
  if (selectedItem.value?.type !== 'character') return undefined;
  return projectStore.library.characters.find((c) => c.id === selectedItem.value?.id);
});

function updateClipStartTime(value: string | number | null): void {
  if (!selectedClip.value || value === null) return;
  projectStore.updateClip(selectedClip.value.id, {
    start_time: Number(value),
  });
}

function updateClipDuration(value: string | number | null): void {
  if (!selectedClip.value || value === null) return;
  projectStore.updateClip(selectedClip.value.id, {
    duration: Number(value),
  });
}

function updateGenerationMode(value: string): void {
  if (!selectedClip.value) return;
  const currentSpec = selectedClip.value.generation_spec || {
    mode: 'prompt_only',
    character_refs: [],
    product_refs: [],
    lora_refs: [],
  };
  projectStore.updateClip(selectedClip.value.id, {
    generation_spec: {
      ...currentSpec,
      mode: value as 'prompt_only' | 'i2v' | 'flf' | 't2v',
      product_refs: currentSpec.product_refs || [],
      lora_refs: currentSpec.lora_refs || [],
    },
  });
}

function updatePrompt(value: string | number | null): void {
  if (!selectedClip.value) return;
  const currentSpec = selectedClip.value.generation_spec || {
    mode: 'prompt_only',
    character_refs: [],
    product_refs: [],
    lora_refs: [],
  };
  projectStore.updateClip(selectedClip.value.id, {
    generation_spec: {
      ...currentSpec,
      prompt: String(value || ''),
      product_refs: currentSpec.product_refs || [],
      lora_refs: currentSpec.lora_refs || [],
    },
  });
}

// Expose method to select items
defineExpose({
  selectItem(type: SelectedItem['type'], id: string): void {
    selectedItem.value = { type, id };
  },
  clearSelection(): void {
    selectedItem.value = null;
  },
});
</script>

<style scoped lang="scss">
.properties-panel {
  height: 100%;
  overflow-y: auto;
}
</style>
