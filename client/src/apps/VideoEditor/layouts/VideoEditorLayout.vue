<template>
  <q-layout view="hHh LpR fFf">
    <!-- Header Toolbar -->
    <q-header v-if="projectStore.isOpen" elevated class="bg-dark">
      <q-toolbar>
        <q-btn flat dense round icon="menu" text-color="white" @click="toggleLeftDrawer">
          <q-tooltip>Toggle Asset Library</q-tooltip>
        </q-btn>
        <q-separator vertical dark class="q-mx-sm" />
        <q-toolbar-title class="text-subtitle1">
          {{ projectStore.projectName }}
        </q-toolbar-title>

        <q-btn-group flat>
          <q-btn
            flat
            label="Story"
            :color="activeTab === 'story' ? 'primary' : 'white'"
            @click="activeTab = 'story'"
          />
          <q-btn
            flat
            label="Assets"
            :color="activeTab === 'assets' ? 'primary' : 'white'"
            @click="activeTab = 'assets'"
          />
          <q-btn
            flat
            label="Timeline"
            :color="activeTab === 'timeline' ? 'primary' : 'white'"
            @click="activeTab = 'timeline'"
          />
          <q-btn
            flat
            label="Export"
            :color="activeTab === 'export' ? 'primary' : 'white'"
            @click="activeTab = 'export'"
          />
        </q-btn-group>

        <q-space />

        <!-- Save status indicator -->
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
          v-else-if="!projectStore.isDirty && projectStore.isOpen"
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
          icon="save"
          label="Save Now"
          text-color="warning"
          :loading="projectStore.isSaving"
          @click="saveProject"
        >
          <q-tooltip>Save all pending changes</q-tooltip>
        </q-btn>
        <q-btn
          flat
          round
          dense
          icon="view_sidebar"
          text-color="white"
          :class="{ 'text-primary': rightDrawerOpen }"
          @click="toggleRightDrawer"
        >
          <q-tooltip>Toggle Properties Panel</q-tooltip>
        </q-btn>
        <q-btn flat round dense icon="settings" text-color="white" @click="showSettings = true">
          <q-tooltip>Project Settings</q-tooltip>
        </q-btn>
      </q-toolbar>
    </q-header>

    <!-- Left Drawer (Asset Library) -->
    <q-drawer
      v-if="projectStore.isOpen"
      v-model="leftDrawerOpen"
      side="left"
      :width="280"
      bordered
      class="bg-grey-2"
    >
      <AssetLibraryPanel />
    </q-drawer>

    <!-- Right Drawer (Properties) -->
    <q-drawer
      v-if="projectStore.isOpen"
      v-model="rightDrawerOpen"
      side="right"
      :width="320"
      bordered
      class="bg-grey-1"
    >
      <PropertiesPanel />
    </q-drawer>

    <!-- Main Content -->
    <q-page-container>
      <router-view :active-tab="activeTab" @update:active-tab="activeTab = $event" />
    </q-page-container>

    <!-- Footer (Generation Queue) -->
    <q-footer v-if="projectStore.isOpen" elevated class="bg-grey-9">
      <GenerationQueuePanel />
    </q-footer>

    <!-- Settings Dialog -->
    <q-dialog v-model="showSettings">
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
const activeTab = ref<'story' | 'assets' | 'timeline' | 'export'>('story');

// Toggle functions
function toggleLeftDrawer(): void {
  leftDrawerOpen.value = !leftDrawerOpen.value;
}

function toggleRightDrawer(): void {
  rightDrawerOpen.value = !rightDrawerOpen.value;
}

// Provide drawer state to child components
provide('leftDrawerOpen', leftDrawerOpen);
provide('rightDrawerOpen', rightDrawerOpen);

async function saveProject(): Promise<void> {
  try {
    await projectStore.saveProject();
  } catch (e) {
    console.error('Failed to save project:', e);
  }
}

// Load recent projects after connection is ready
let recentProjectsLoaded = false;
let isLoadingRecentProjects = false;

async function loadRecentProjectsWhenReady(): Promise<void> {
  // Prevent duplicate calls - set flag immediately to block concurrent calls
  if (recentProjectsLoaded || isLoadingRecentProjects) return;
  isLoadingRecentProjects = true;

  try {
    // Wait for connection to be established
    if (!companionStore.isConnected) {
      // Wait up to 10 seconds for connection
      let attempts = 0;
      const maxAttempts = 20; // 20 * 500ms = 10 seconds

      while (!companionStore.isConnected && attempts < maxAttempts) {
        await new Promise((resolve) => setTimeout(resolve, 500));
        attempts++;
      }
    }

    if (companionStore.isConnected) {
      await projectStore.loadRecentProjects();
      recentProjectsLoaded = true;
    } else {
      console.warn('Video Editor companion not connected, skipping recent projects load');
    }
  } catch (e) {
    console.error('Failed to load recent projects:', e);
    // Reset flag on error so it can be retried
    isLoadingRecentProjects = false;
  } finally {
    isLoadingRecentProjects = false;
  }
}

// Watch for connection changes and load when ready
// Using immediate: true handles both cases:
// 1. If already connected when component mounts
// 2. When connection becomes available later
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

<style scoped>
.q-footer {
  height: 100px;
}
</style>
