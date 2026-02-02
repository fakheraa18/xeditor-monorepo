<template>
  <div class="story-designer">
    <div class="row items-center q-mb-md">
      <div class="text-h5">Story Designer</div>
      <q-space />
      <q-btn color="primary" icon="add" label="Add Scene" @click="addScene" />
      <q-btn
        flat
        icon="auto_awesome"
        label="Generate with AI"
        class="q-ml-sm"
        @click="generateWithAI"
      />
    </div>

    <!-- Story Meta -->
    <q-card flat bordered class="q-mb-md">
      <q-card-section>
        <div class="row q-gutter-md">
          <q-input
            v-model="story.title"
            label="Story Title"
            outlined
            dense
            class="col"
            @update:model-value="markDirty"
          />
          <q-select
            v-model="story.genre"
            :options="genreOptions"
            label="Genre"
            outlined
            dense
            emit-value
            map-options
            class="col-3"
            @update:model-value="markDirty"
          />
        </div>
        <q-input
          v-model="story.synopsis"
          label="Synopsis"
          outlined
          dense
          type="textarea"
          rows="2"
          class="q-mt-sm"
          @update:model-value="markDirty"
        />
      </q-card-section>
    </q-card>

    <!-- Scenes List -->
    <div class="scenes-container">
      <q-card
        v-for="(scene, index) in story.scenes"
        :key="scene.id"
        flat
        bordered
        class="scene-card q-mb-md"
      >
        <q-card-section>
          <div class="row items-center q-mb-sm">
            <q-badge :label="`Scene ${index + 1}`" color="primary" class="q-mr-sm" />
            <q-input
              v-model="scene.title"
              placeholder="Scene title"
              dense
              borderless
              class="col text-h6"
              @update:model-value="markDirty"
            />
            <q-btn
              flat
              round
              size="sm"
              icon="arrow_upward"
              :disable="index === 0"
              @click="moveScene(index, -1)"
            />
            <q-btn
              flat
              round
              size="sm"
              icon="arrow_downward"
              :disable="index === story.scenes.length - 1"
              @click="moveScene(index, 1)"
            />
            <q-btn
              flat
              round
              size="sm"
              icon="delete"
              color="negative"
              @click="removeScene(scene.id)"
            />
          </div>

          <div class="row q-gutter-md">
            <!-- Visual Description -->
            <div class="col-6">
              <div class="text-caption text-grey-7 q-mb-xs">Visual Description</div>
              <q-input
                v-model="scene.description.visual_prompt"
                outlined
                dense
                type="textarea"
                rows="3"
                placeholder="Describe the visual scene..."
                @update:model-value="markDirty"
              />
              <q-input
                v-model="scene.description.camera_notes"
                outlined
                dense
                class="q-mt-sm"
                placeholder="Camera notes (angle, movement)"
                @update:model-value="markDirty"
              >
                <template #prepend>
                  <q-icon name="videocam" size="xs" />
                </template>
              </q-input>
            </div>

            <!-- Script/Dialog -->
            <div class="col-6">
              <div class="text-caption text-grey-7 q-mb-xs">Script / Dialog</div>
              <div
                v-for="(line, lineIndex) in scene.script.lines"
                :key="lineIndex"
                class="script-line row items-center q-gutter-sm q-mb-xs"
              >
                <q-select
                  v-model="line.character_id"
                  :options="characterOptions"
                  dense
                  outlined
                  emit-value
                  map-options
                  style="width: 120px"
                  placeholder="Character"
                  @update:model-value="markDirty"
                />
                <q-input
                  v-model="line.text"
                  dense
                  outlined
                  class="col"
                  placeholder="Dialog or narration..."
                  @update:model-value="markDirty"
                />
                <q-btn flat round size="sm" icon="close" @click="removeLine(scene, lineIndex)" />
              </div>
              <q-btn flat size="sm" icon="add" label="Add Line" @click="addLine(scene)" />
            </div>
          </div>

          <!-- Characters in Scene -->
          <div class="q-mt-sm">
            <q-chip
              v-for="charId in scene.character_ids"
              :key="charId"
              removable
              color="primary"
              text-color="white"
              size="sm"
              @remove="removeCharacterFromScene(scene, charId)"
            >
              {{ getCharacterName(charId) }}
            </q-chip>
            <q-btn flat size="sm" icon="person_add" @click="addCharacterToScene(scene)" />
          </div>
        </q-card-section>
      </q-card>

      <div v-if="story.scenes.length === 0" class="text-center q-pa-xl text-grey">
        <q-icon name="movie" size="64px" class="q-mb-md" />
        <div class="text-h6">No scenes yet</div>
        <div class="q-mb-md">Add your first scene or generate a story with AI</div>
        <q-btn color="primary" icon="add" label="Add First Scene" @click="addScene" />
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue';
import { useVideoProjectStore, useVideoJobsStore } from '../stores';
import type { StoryScene, ScriptLine } from '../types';

const projectStore = useVideoProjectStore();
const jobsStore = useVideoJobsStore();

const story = computed(() => projectStore.story);
const library = computed(() => projectStore.library);

const genreOptions = [
  { label: 'Advertising', value: 'advertising' },
  { label: 'Movie', value: 'movie' },
  { label: 'Documentary', value: 'documentary' },
  { label: 'Music Video', value: 'music_video' },
  { label: 'Educational', value: 'educational' },
  { label: 'Other', value: 'other' },
];

const characterOptions = computed(() => [
  { label: 'Narrator', value: null },
  ...library.value.characters.map((c) => ({
    label: c.name,
    value: c.id,
  })),
]);

function markDirty(): void {
  // Trigger autosave via the store
  projectStore.markDirty();
}

function addScene(): void {
  projectStore.addScene({
    order: story.value.scenes.length,
    title: `Scene ${story.value.scenes.length + 1}`,
    script: { lines: [] },
    description: { visual_prompt: '' },
    character_ids: [],
    prop_ids: [],
  });
}

function removeScene(id: string): void {
  if (confirm('Remove this scene?')) {
    projectStore.removeScene(id);
  }
}

function moveScene(index: number, direction: number): void {
  const newIndex = index + direction;
  if (newIndex < 0 || newIndex >= story.value.scenes.length) return;

  const sceneIds = story.value.scenes.map((s) => s.id).filter((id): id is string => !!id);
  if (sceneIds[index] && sceneIds[newIndex]) {
    [sceneIds[index], sceneIds[newIndex]] = [sceneIds[newIndex], sceneIds[index]];
    projectStore.reorderScenes(sceneIds);
  }
}

function addLine(scene: StoryScene): void {
  const newLine: ScriptLine = {
    text: '',
  };
  scene.script.lines.push(newLine);
  markDirty();
}

function removeLine(scene: StoryScene, index: number): void {
  scene.script.lines.splice(index, 1);
  markDirty();
}

function getCharacterName(id: string): string {
  const char = library.value.characters.find((c) => c.id === id);
  return char?.name || 'Unknown';
}

function addCharacterToScene(scene: StoryScene): void {
  const charId = prompt('Enter character ID to add:');
  if (charId && !scene.character_ids.includes(charId)) {
    scene.character_ids.push(charId);
    markDirty();
  }
}

function removeCharacterFromScene(scene: StoryScene, charId: string): void {
  scene.character_ids = scene.character_ids.filter((id) => id !== charId);
  markDirty();
}

async function generateWithAI(): Promise<void> {
  try {
    await jobsStore.generateStory({
      topic: story.value.title || 'A compelling video story',
      ...(story.value.genre && { genre: story.value.genre }),
      numScenes: 5,
    });
  } catch (e) {
    console.error('Failed to start story generation:', e);
  }
}
</script>

<style scoped lang="scss">
.story-designer {
  max-width: 1200px;
  margin: 0 auto;
}

.scenes-container {
  .scene-card {
    transition: box-shadow 0.2s;

    &:hover {
      box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
    }
  }
}

.script-line {
  background: rgba(0, 0, 0, 0.02);
  padding: 4px;
  border-radius: 4px;
}
</style>
