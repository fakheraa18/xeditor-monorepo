<template>
  <q-card class="project-wizard" style="min-width: 600px; max-width: 800px">
    <q-card-section class="bg-primary text-white">
      <div class="text-h5">
        <q-icon name="movie" class="q-mr-sm" />
        {{ isCreating ? 'Create New Project' : 'Open Project' }}
      </div>
    </q-card-section>

    <q-card-section>
      <q-tabs v-model="tab" class="text-primary" align="justify">
        <q-tab name="new" label="New Project" icon="add" />
        <q-tab name="open" label="Open Project" icon="folder_open" />
        <q-tab name="recent" label="Recent" icon="history" />
      </q-tabs>

      <q-separator />

      <q-tab-panels v-model="tab" animated class="q-pt-md">
        <!-- New Project Tab -->
        <q-tab-panel name="new">
          <div class="q-gutter-md">
            <!-- Project Name -->
            <q-input
              v-model="projectName"
              label="Project Name"
              outlined
              :rules="[(val) => !!val || 'Name is required']"
            >
              <template #prepend>
                <q-icon name="label" />
              </template>
            </q-input>

            <!-- Folder Selection -->
            <q-input
              v-model="folderPath"
              label="Project Folder"
              outlined
              readonly
              :error="!!folderError"
              :error-message="folderError"
            >
              <template #prepend>
                <q-icon name="folder" />
              </template>
              <template #append>
                <q-btn flat round icon="folder_open" @click="showFolderPicker = true" />
              </template>
            </q-input>

            <!-- Canvas Preset -->
            <q-select
              v-model="canvasPreset"
              :options="canvasPresetOptions"
              label="Canvas Size"
              outlined
              emit-value
              map-options
            >
              <template #prepend>
                <q-icon name="aspect_ratio" />
              </template>
            </q-select>

            <!-- VRAM Target -->
            <q-select
              v-model="vramTarget"
              :options="vramOptions"
              label="VRAM Target"
              outlined
              emit-value
              map-options
            >
              <template #prepend>
                <q-icon name="memory" />
              </template>
            </q-select>

            <!-- Preview -->
            <div class="q-pa-md bg-grey-2 rounded-borders">
              <div class="text-subtitle2 text-grey-8 q-mb-sm">Preview</div>
              <div class="row q-gutter-md">
                <div class="col">
                  <div class="text-caption text-grey-7">Resolution</div>
                  <div class="text-body1">
                    {{ selectedPreset?.width }} × {{ selectedPreset?.height }}
                  </div>
                </div>
                <div class="col">
                  <div class="text-caption text-grey-7">FPS</div>
                  <div class="text-body1">{{ selectedPreset?.fps }}</div>
                </div>
                <div class="col">
                  <div class="text-caption text-grey-7">Orientation</div>
                  <div class="text-body1 text-capitalize">
                    {{ selectedPreset?.orientation }}
                  </div>
                </div>
              </div>
            </div>
          </div>
        </q-tab-panel>

        <!-- Open Project Tab -->
        <q-tab-panel name="open">
          <div class="q-gutter-md">
            <q-input
              v-model="openFolderPath"
              label="Project Folder"
              outlined
              readonly
              :error="!!openFolderError"
              :error-message="openFolderError"
            >
              <template #prepend>
                <q-icon name="folder" />
              </template>
              <template #append>
                <q-btn flat round icon="folder_open" @click="showOpenFolderPicker = true" />
              </template>
            </q-input>

            <div
              v-if="openFolderPath && hasExistingProject"
              class="q-pa-md bg-positive-1 rounded-borders"
            >
              <q-icon name="check_circle" color="positive" class="q-mr-sm" />
              Valid video project found
            </div>
          </div>
        </q-tab-panel>

        <!-- Recent Projects Tab -->
        <q-tab-panel name="recent">
          <q-list v-if="recentProjects.length > 0" bordered separator>
            <q-item
              v-for="recent in recentProjects"
              :key="recent.id"
              clickable
              @click="openRecentProject(recent)"
            >
              <q-item-section avatar>
                <q-icon name="movie" color="primary" />
              </q-item-section>
              <q-item-section>
                <q-item-label>{{ recent.name }}</q-item-label>
                <q-item-label caption>{{ recent.path }}</q-item-label>
              </q-item-section>
              <q-item-section side>
                <q-item-label caption>
                  {{ formatDate(recent.opened_at) }}
                </q-item-label>
              </q-item-section>
            </q-item>
          </q-list>
          <div v-else class="text-center q-pa-lg text-grey">
            <q-icon name="history" size="48px" class="q-mb-md" />
            <div>No recent projects</div>
          </div>
        </q-tab-panel>
      </q-tab-panels>
    </q-card-section>

    <q-separator />

    <q-card-actions align="right" class="q-pa-md">
      <q-btn flat label="Cancel" color="grey" @click="emit('cancel')" />
      <q-btn
        v-if="tab === 'new'"
        :loading="isLoading"
        :disable="!canCreate"
        label="Create Project"
        color="primary"
        icon="add"
        @click="createProject"
      />
      <q-btn
        v-if="tab === 'open'"
        :loading="isLoading"
        :disable="!canOpen"
        label="Open Project"
        color="primary"
        icon="folder_open"
        @click="openProject"
      />
    </q-card-actions>
  </q-card>

  <!-- Folder Picker Dialog for New Project -->
  <FolderPickerDialog
    v-model="showFolderPicker"
    :request-fn="veRequestFn"
    @select="onFolderSelected"
    @cancel="showFolderPicker = false"
  />

  <!-- Folder Picker Dialog for Open Project -->
  <FolderPickerDialog
    v-model="showOpenFolderPicker"
    :request-fn="veRequestFn"
    @select="onOpenFolderSelected"
    @cancel="showOpenFolderPicker = false"
  />
</template>

<script setup lang="ts">
import { ref, computed, watch } from 'vue';
import { useVideoProjectStore } from '../stores';
import { useVideoCompanionStore } from '../stores/videoCompanion';
import { CANVAS_PRESETS, type RecentProject, type CanvasPreset } from '../types';
import FolderPickerDialog from '../../CodeEditor/components/editor/FolderPickerDialog.vue';

const emit = defineEmits<{
  cancel: [];
  created: [];
  opened: [];
}>();

const projectStore = useVideoProjectStore();
const videoCompanion = useVideoCompanionStore();

/** Provide the video companion's request function to the folder picker */
function veRequestFn<T>(type: string, payload: Record<string, unknown>): Promise<T> {
  return videoCompanion.request<T>(type, payload);
}

// State
const tab = ref<'new' | 'open' | 'recent'>('new');
const isLoading = ref(false);

// New project form
const projectName = ref('My Video Project');
const folderPath = ref('');
const folderError = ref('');
const canvasPreset = ref('1080p_landscape');
const vramTarget = ref(24);
const showFolderPicker = ref(false);

// Open project form
const openFolderPath = ref('');
const openFolderError = ref('');
const hasExistingProject = ref(false);
const showOpenFolderPicker = ref(false);

// Computed
const isCreating = computed(() => tab.value === 'new');

const canvasPresetOptions = computed(() =>
  Object.entries(CANVAS_PRESETS).map(([key, preset]) => ({
    label: preset.name,
    value: key,
  })),
);

const selectedPreset = computed<CanvasPreset | undefined>(() => CANVAS_PRESETS[canvasPreset.value]);

const vramOptions = [
  { label: '8 GB (RTX 3070/4070)', value: 8 },
  { label: '12 GB (RTX 3080/4070 Ti)', value: 12 },
  { label: '16 GB (RTX 4080)', value: 16 },
  { label: '24 GB (RTX 3090/4090)', value: 24 },
];

const recentProjects = computed(() => projectStore.recentProjects);

const canCreate = computed(() => projectName.value && folderPath.value && !folderError.value);

const canOpen = computed(
  () => openFolderPath.value && hasExistingProject.value && !openFolderError.value,
);

// Methods
async function onFolderSelected(path: string): Promise<void> {
  showFolderPicker.value = false;
  folderPath.value = path;
  folderError.value = '';

  try {
    const result = await projectStore.checkFolder(path);
    if (result.hasProject) {
      folderError.value = 'Folder already contains a video project. Use "Open Project" instead.';
    } else if (!result.isEmpty) {
      folderError.value = 'Folder is not empty. Please select an empty folder.';
    }
  } catch (e) {
    folderError.value = (e as Error).message;
  }
}

async function onOpenFolderSelected(path: string): Promise<void> {
  showOpenFolderPicker.value = false;
  openFolderPath.value = path;
  openFolderError.value = '';
  hasExistingProject.value = false;

  try {
    const result = await projectStore.checkFolder(path);
    if (!result.hasProject) {
      openFolderError.value = 'No video project found in this folder.';
    } else {
      hasExistingProject.value = true;
    }
  } catch (e) {
    openFolderError.value = (e as Error).message;
  }
}

async function createProject(): Promise<void> {
  if (!canCreate.value) return;

  isLoading.value = true;
  try {
    const preset = selectedPreset.value;
    await projectStore.createProject(folderPath.value, projectName.value, {
      vram_target_gb: vramTarget.value,
      canvas: {
        preset: canvasPreset.value,
        width: preset?.width ?? 1920,
        height: preset?.height ?? 1080,
        fps: preset?.fps ?? 30,
        orientation: preset?.orientation ?? 'landscape',
      },
      default_generators: {},
    });
    emit('created');
  } catch (e) {
    console.error('Failed to create project:', e);
  } finally {
    isLoading.value = false;
  }
}

async function openProject(): Promise<void> {
  if (!canOpen.value) return;

  isLoading.value = true;
  try {
    await projectStore.openProject(openFolderPath.value);
    emit('opened');
  } catch (e) {
    console.error('Failed to open project:', e);
  } finally {
    isLoading.value = false;
  }
}

async function openRecentProject(recent: RecentProject): Promise<void> {
  isLoading.value = true;
  try {
    await projectStore.openProject(recent.path);
    emit('opened');
  } catch (e) {
    console.error('Failed to open recent project:', e);
  } finally {
    isLoading.value = false;
  }
}

function formatDate(timestamp: number): string {
  return new Date(timestamp * 1000).toLocaleDateString();
}

// Watch for tab changes to refresh recent projects
watch(tab, async (newTab) => {
  if (newTab === 'recent') {
    await projectStore.loadRecentProjects();
  }
});
</script>

<style scoped lang="scss">
.project-wizard {
  .q-tab-panels {
    min-height: 300px;
  }
}
</style>
