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

        <q-btn
          v-if="projectStore.isDirty"
          flat
          icon="save"
          label="Save"
          text-color="warning"
          @click="saveProject"
        />
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
import { ref, provide } from 'vue';
import { useVideoProjectStore } from '../stores';
import AssetLibraryPanel from '../components/AssetLibraryPanel.vue';
import PropertiesPanel from '../components/PropertiesPanel.vue';
import GenerationQueuePanel from '../components/GenerationQueuePanel.vue';
import SettingsDialog from '../components/SettingsDialog.vue';

const projectStore = useVideoProjectStore();

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
</script>

<style scoped>
.q-footer {
  height: 100px;
}
</style>
