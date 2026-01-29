<template>
  <q-dialog v-model="dialogVisible" persistent>
    <q-card style="min-width: 600px; max-width: 800px; height: 600px;" class="column">
      <q-card-section class="row items-center q-pb-none">
        <div class="text-h6">Select Project Folder</div>
        <q-space />
        <q-btn icon="close" flat round dense v-close-popup />
      </q-card-section>

      <q-card-section class="q-pt-sm">
        <div class="row q-gutter-sm items-center">
          <q-input
            v-model="currentPathInput"
            label="Path"
            outlined
            dense
            class="col"
            @keyup.enter="navigateToPath"
          >
            <template v-slot:prepend>
              <q-icon name="folder" />
            </template>
            <template v-slot:append>
              <q-btn
                flat
                dense
                round
                icon="arrow_forward"
                @click="navigateToPath"
                :disable="!currentPathInput"
              >
                <q-tooltip>Go to path</q-tooltip>
              </q-btn>
            </template>
          </q-input>
          <q-btn
            flat
            dense
            icon="home"
            @click="goToHome"
            :disable="isLoading"
          >
            <q-tooltip>Go to home directory</q-tooltip>
          </q-btn>
          <q-btn
            flat
            dense
            icon="arrow_upward"
            @click="goUp"
            :disable="isLoading || !canGoUp"
          >
            <q-tooltip>Go to parent directory</q-tooltip>
          </q-btn>
          <q-btn
            flat
            dense
            icon="refresh"
            @click="refreshCurrentDirectory"
            :disable="isLoading"
          >
            <q-tooltip>Refresh</q-tooltip>
          </q-btn>
        </div>
      </q-card-section>

      <!-- Quick access locations -->
      <q-card-section v-if="commonLocations.length > 0" class="q-pt-none q-pb-sm">
        <div class="text-caption text-grey-7 q-mb-xs">Quick Access</div>
        <div class="row q-gutter-xs">
          <q-chip
            v-for="loc in commonLocations"
            :key="loc.path"
            clickable
            dense
            @click="navigateTo(loc.path)"
            color="primary"
            text-color="white"
            size="sm"
          >
            <q-icon name="folder" size="xs" class="q-mr-xs" />
            {{ loc.name }}
          </q-chip>
        </div>
      </q-card-section>

      <q-separator />

      <!-- Directory listing -->
      <q-card-section class="col q-pa-none" style="min-height: 0;">
        <q-scroll-area class="fit">
          <div v-if="isLoading" class="q-pa-md text-center">
            <q-spinner-dots size="40px" color="primary" />
            <div class="q-mt-sm text-grey-7">Loading directory...</div>
          </div>

          <div v-else-if="error" class="q-pa-md text-center text-negative">
            <q-icon name="error" size="48px" />
            <div class="q-mt-sm">{{ error }}</div>
            <q-btn
              flat
              color="primary"
              label="Try Again"
              class="q-mt-md"
              @click="refreshCurrentDirectory"
            />
          </div>

          <div v-else-if="entries.length === 0" class="q-pa-md text-center text-grey-7">
            <q-icon name="folder_off" size="48px" />
            <div class="q-mt-sm">No subdirectories found</div>
          </div>

          <q-list v-else dense>
            <q-item
              v-for="entry in entries"
              :key="entry.path"
              clickable
              :active="selectedPath === entry.path"
              @click="selectEntry(entry)"
              @dblclick="openEntry(entry)"
            >
              <q-item-section avatar>
                <q-icon
                  :name="entry.isDirectory ? 'folder' : 'insert_drive_file'"
                  :color="entry.isDirectory ? 'amber-8' : 'grey-6'"
                />
              </q-item-section>
              <q-item-section>
                <q-item-label>{{ entry.name }}</q-item-label>
              </q-item-section>
              <q-item-section side v-if="entry.isDirectory && entry.hasChildren">
                <q-icon name="chevron_right" color="grey-5" size="sm" />
              </q-item-section>
              <q-item-section side v-if="entry.permissionDenied">
                <q-icon name="lock" color="grey-5" size="sm">
                  <q-tooltip>Permission denied</q-tooltip>
                </q-icon>
              </q-item-section>
            </q-item>
          </q-list>
        </q-scroll-area>
      </q-card-section>

      <q-separator />

      <!-- Selected path display -->
      <q-card-section class="q-py-sm">
        <div class="row items-center">
          <div class="text-caption text-grey-7 q-mr-sm">Selected:</div>
          <div class="text-body2 text-weight-medium ellipsis col">
            {{ selectedPath || currentPath || 'None' }}
          </div>
        </div>
      </q-card-section>

      <q-card-actions align="right">
        <q-btn flat label="Cancel" color="grey-7" v-close-popup />
        <q-btn
          label="Select Folder"
          color="primary"
          :disable="!selectedPath"
          @click="confirmSelection"
        />
      </q-card-actions>
    </q-card>
  </q-dialog>
</template>

<script setup lang="ts">
import { ref, computed, watch, onMounted } from 'vue';
import { useLocalCompanionStore } from '../../stores/localCompanion';

interface DirectoryEntry {
  name: string;
  path: string;
  isDirectory: boolean;
  hasChildren?: boolean;
  permissionDenied?: boolean;
}

interface CommonLocation {
  name: string;
  path: string;
}

const emit = defineEmits<{
  (e: 'select', path: string): void;
  (e: 'cancel'): void;
}>();

const props = defineProps<{
  modelValue: boolean;
  initialPath?: string;
}>();

const companionStore = useLocalCompanionStore();

const dialogVisible = computed({
  get: () => props.modelValue,
  set: (val: boolean) => {
    if (!val) {
      emit('cancel');
    }
  },
});

const currentPath = ref<string>('');
const currentPathInput = ref<string>('');
const selectedPath = ref<string>('');
const entries = ref<DirectoryEntry[]>([]);
const commonLocations = ref<CommonLocation[]>([]);
const isLoading = ref(false);
const error = ref<string | null>(null);
const homeDirectory = ref<string>('');

const canGoUp = computed(() => {
  if (!currentPath.value) return false;
  // Check if we're at root (Unix: /, Windows: C:\)
  const path = currentPath.value;
  if (path === '/') return false;
  if (/^[A-Z]:\\?$/i.test(path)) return false;
  return true;
});

async function loadHomeDirectory(): Promise<void> {
  if (!companionStore.isConnected) {
    error.value = 'Local Companion is not connected';
    return;
  }

  try {
    const response = await companionStore.request<{
      home: string;
      system: string;
      commonLocations: CommonLocation[];
      xeditorPath: string;
    }>('get_home_directory', {});

    homeDirectory.value = response.home;
    commonLocations.value = response.commonLocations;

    // Navigate to initial path or home
    const targetPath = props.initialPath || response.home;
    await navigateTo(targetPath);
  } catch (err) {
    error.value = err instanceof Error ? err.message : 'Failed to load home directory';
  }
}

async function navigateTo(path: string): Promise<void> {
  if (!companionStore.isConnected) {
    error.value = 'Local Companion is not connected';
    return;
  }

  isLoading.value = true;
  error.value = null;
  entries.value = [];

  try {
    const response = await companionStore.request<{
      success: boolean;
      path: string;
      entries: DirectoryEntry[];
      error: string | null;
    }>('list_directory', { path, showHidden: false, showFiles: false });

    if (!response.success) {
      error.value = response.error || 'Failed to list directory';
      return;
    }

    currentPath.value = response.path;
    currentPathInput.value = response.path;
    entries.value = response.entries;
    // Clear selection when navigating to a new directory
    selectedPath.value = response.path;
  } catch (err) {
    error.value = err instanceof Error ? err.message : 'Failed to list directory';
  } finally {
    isLoading.value = false;
  }
}

function navigateToPath(): void {
  if (currentPathInput.value) {
    void navigateTo(currentPathInput.value);
  }
}

function goToHome(): void {
  if (homeDirectory.value) {
    void navigateTo(homeDirectory.value);
  }
}

function goUp(): void {
  if (!currentPath.value || !canGoUp.value) return;

  // Get parent directory
  let parent: string;
  if (currentPath.value.includes('/')) {
    const parts = currentPath.value.split('/').filter(Boolean);
    parts.pop();
    parent = parts.length > 0 ? '/' + parts.join('/') : '/';
  } else {
    // Windows path
    const parts = currentPath.value.split('\\').filter(Boolean);
    parts.pop();
    parent = parts.length > 0 ? parts.join('\\') : currentPath.value.substring(0, 3);
  }

  void navigateTo(parent);
}

function refreshCurrentDirectory(): void {
  if (currentPath.value) {
    void navigateTo(currentPath.value);
  } else {
    void loadHomeDirectory();
  }
}

function selectEntry(entry: DirectoryEntry): void {
  if (entry.isDirectory) {
    selectedPath.value = entry.path;
  }
}

function openEntry(entry: DirectoryEntry): void {
  if (entry.isDirectory && !entry.permissionDenied) {
    void navigateTo(entry.path);
  }
}

function confirmSelection(): void {
  if (selectedPath.value) {
    emit('select', selectedPath.value);
  }
}

watch(
  () => props.modelValue,
  (visible) => {
    if (visible) {
      selectedPath.value = '';
      error.value = null;
      void loadHomeDirectory();
    }
  }
);

onMounted(() => {
  if (props.modelValue) {
    void loadHomeDirectory();
  }
});
</script>

<style scoped>
.q-item--active {
  background-color: rgba(25, 118, 210, 0.1);
}

.q-item:hover {
  background-color: rgba(0, 0, 0, 0.04);
}
</style>
