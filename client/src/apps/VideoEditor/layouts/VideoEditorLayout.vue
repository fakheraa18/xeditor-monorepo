<template>
  <q-layout view="hHh LpR fFf">
    <!-- Header Toolbar -->
    <q-header v-if="projectStore.isOpen" elevated class="bg-dark">
      <q-toolbar class="ve-toolbar">
        <q-btn flat dense round icon="home" text-color="white" @click="$router.push('/')">
          <q-tooltip>Home</q-tooltip>
        </q-btn>
        <q-separator vertical dark class="q-mx-xs" />

        <q-toolbar-title class="text-subtitle1 ellipsis" style="max-width: 200px">
          {{ projectStore.projectName }}
        </q-toolbar-title>

        <q-separator vertical dark class="q-mx-xs" />

        <!-- Workspace tools -->
        <q-btn-group flat class="q-mx-sm">
          <q-btn
            flat
            dense
            icon="auto_fix_high"
            text-color="white"
            @click="showScriptGenerator = true"
          >
            <q-tooltip>Script Generator</q-tooltip>
          </q-btn>
          <q-btn flat dense icon="music_note" text-color="white" @click="rightPanel = 'audio'">
            <q-tooltip>Audio Generator</q-tooltip>
          </q-btn>
          <q-btn flat dense icon="image" text-color="white" @click="rightPanel = 'image'">
            <q-tooltip>Image Generator</q-tooltip>
          </q-btn>
          <q-btn flat dense icon="movie" text-color="white" @click="rightPanel = 'video'">
            <q-tooltip>Video Generator</q-tooltip>
          </q-btn>
          <q-btn flat dense icon="face" text-color="white" @click="rightPanel = 'character'">
            <q-tooltip>Character Designer</q-tooltip>
          </q-btn>
        </q-btn-group>

        <q-space />

        <!-- Save status -->
        <q-spinner-dots v-if="projectStore.isSaving" color="white" size="20px" class="q-mr-sm" />
        <q-icon
          v-else-if="projectStore.lastSaveError"
          name="error"
          color="negative"
          size="20px"
          class="q-mr-sm"
        >
          <q-tooltip>Save error: {{ projectStore.lastSaveError }}</q-tooltip>
        </q-icon>
        <q-icon
          v-else-if="!projectStore.isDirty"
          name="cloud_done"
          color="positive"
          size="20px"
          class="q-mr-sm"
        >
          <q-tooltip>All changes saved</q-tooltip>
        </q-icon>

        <q-btn
          v-if="projectStore.isDirty"
          flat
          dense
          icon="save"
          text-color="warning"
          :loading="projectStore.isSaving"
          @click="saveProject"
        >
          <q-tooltip>Save Now</q-tooltip>
        </q-btn>

        <q-separator vertical dark class="q-mx-xs" />

        <q-btn flat dense round icon="folder_open" text-color="white" @click="toggleLeftDrawer">
          <q-tooltip>Toggle Asset Panel</q-tooltip>
        </q-btn>
        <q-btn
          flat
          dense
          round
          icon="view_sidebar"
          text-color="white"
          :class="{ 'text-primary': rightDrawerOpen }"
          @click="toggleRightDrawer"
        >
          <q-tooltip>Toggle Properties Panel</q-tooltip>
        </q-btn>
        <q-btn flat dense round icon="settings" text-color="white" @click="showSettings = true">
          <q-tooltip>Project Settings</q-tooltip>
        </q-btn>
      </q-toolbar>
    </q-header>

    <!-- Left Drawer (Asset Library) -->
    <q-drawer
      v-if="projectStore.isOpen"
      v-model="leftDrawerOpen"
      side="left"
      :width="260"
      bordered
      class="bg-grey-10"
    >
      <AssetLibraryPanel />
    </q-drawer>

    <!-- Right Drawer (Properties / Generator Panels) -->
    <q-drawer
      v-if="projectStore.isOpen"
      v-model="rightDrawerOpen"
      side="right"
      :width="360"
      bordered
      class="bg-grey-10"
    >
      <PropertiesPanel :active-panel="rightPanel" @update:active-panel="rightPanel = $event" />
    </q-drawer>

    <!-- Main Content -->
    <q-page-container>
      <router-view
        :right-panel="rightPanel"
        :show-script-generator="showScriptGenerator"
        @update:right-panel="rightPanel = $event"
        @update:show-script-generator="showScriptGenerator = $event"
      />
    </q-page-container>

    <!-- Footer (Job Status Bar) -->
    <q-footer v-if="projectStore.isOpen" elevated class="bg-grey-9 ve-footer">
      <GenerationQueuePanel />
    </q-footer>

    <!-- Settings Dialog -->
    <q-dialog v-model="showSettings" maximized>
      <SettingsDialog @close="showSettings = false" />
    </q-dialog>
  </q-layout>
</template>

<script setup lang="ts">
import { ref, provide, watch } from 'vue';
import { useVideoProjectStore } from '../stores';
import { useVideoCompanionStore } from '../stores/videoCompanion';
import AssetLibraryPanel from '../components/AssetLibraryPanel.vue';
import PropertiesPanel from '../components/PropertiesPanel.vue';
import GenerationQueuePanel from '../components/GenerationQueuePanel.vue';
import SettingsDialog from '../components/SettingsDialog.vue';

const projectStore = useVideoProjectStore();
const companionStore = useVideoCompanionStore();

// UI State
const leftDrawerOpen = ref(true);
const rightDrawerOpen = ref(true);
const showSettings = ref(false);
const showScriptGenerator = ref(false);

// Right panel mode
const rightPanel = ref<'properties' | 'audio' | 'image' | 'video' | 'character' | 'scene'>(
  'properties',
);

// Toggle functions
function toggleLeftDrawer(): void {
  leftDrawerOpen.value = !leftDrawerOpen.value;
}

function toggleRightDrawer(): void {
  rightDrawerOpen.value = !rightDrawerOpen.value;
}

// Provide state to children
provide('leftDrawerOpen', leftDrawerOpen);
provide('rightDrawerOpen', rightDrawerOpen);
provide('rightPanel', rightPanel);

async function saveProject(): Promise<void> {
  try {
    await projectStore.saveProject();
  } catch (e) {
    console.error('Failed to save project:', e);
  }
}

// Load recent projects when connected
let recentProjectsLoaded = false;
let isLoadingRecentProjects = false;

async function loadRecentProjectsWhenReady(): Promise<void> {
  if (recentProjectsLoaded || isLoadingRecentProjects) return;
  isLoadingRecentProjects = true;

  try {
    if (!companionStore.isConnected) {
      let attempts = 0;
      while (!companionStore.isConnected && attempts < 20) {
        await new Promise((resolve) => setTimeout(resolve, 500));
        attempts++;
      }
    }

    if (companionStore.isConnected) {
      await projectStore.loadRecentProjects();
      recentProjectsLoaded = true;
    }
  } catch (e) {
    console.error('Failed to load recent projects:', e);
  } finally {
    isLoadingRecentProjects = false;
  }
}

watch(
  () => companionStore.isConnected,
  (isConnected) => {
    if (isConnected) {
      void loadRecentProjectsWhenReady();
    }
  },
  { immediate: true },
);
</script>

<style scoped lang="scss">
.ve-toolbar {
  min-height: 40px;
  padding: 0 4px;
}

.ve-footer {
  height: 80px;
  border-top: 1px solid rgba(255, 255, 255, 0.1);
}
</style>
