<template>
  <q-page class="video-editor-page">
    <!-- No project open - show wizard -->
    <div
      v-if="!projectStore.isOpen"
      class="flex flex-center"
      style="min-height: calc(100vh - 100px)"
    >
      <ProjectWizard @created="onProjectReady" @opened="onProjectReady" @cancel="goHome" />
    </div>

    <!-- Project open - show workspace -->
    <div v-else class="workspace-container">
      <!-- Top Toolbar -->
      <div class="toolbar bg-dark text-white q-pa-sm">
        <div class="row items-center q-gutter-sm">
          <q-btn flat round icon="menu" @click="leftDrawerOpen = !leftDrawerOpen" />
          <q-separator vertical dark />
          <span class="text-subtitle1">{{ projectStore.projectName }}</span>
          <q-space />
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
            color="warning"
            @click="saveProject"
          />
          <q-btn flat round icon="settings" @click="showSettings = true" />
        </div>
      </div>

      <!-- Main Content Area -->
      <div class="content-area row no-wrap">
        <!-- Left Panel (Asset Library) -->
        <q-drawer v-model="leftDrawerOpen" side="left" :width="280" bordered class="bg-grey-2">
          <AssetLibraryPanel />
        </q-drawer>

        <!-- Center Content -->
        <div class="col main-content q-pa-md">
          <StoryDesigner v-if="activeTab === 'story'" />
          <AssetManager v-else-if="activeTab === 'assets'" />
          <TimelineEditor v-else-if="activeTab === 'timeline'" />
          <ExportPanel v-else-if="activeTab === 'export'" />
        </div>

        <!-- Right Panel (Properties) -->
        <q-drawer v-model="rightDrawerOpen" side="right" :width="320" bordered class="bg-grey-1">
          <PropertiesPanel />
        </q-drawer>
      </div>

      <!-- Bottom Panel (Generation Queue) -->
      <div class="generation-queue bg-grey-9 text-white">
        <GenerationQueuePanel />
      </div>
    </div>

    <!-- Settings Dialog -->
    <q-dialog v-model="showSettings">
      <SettingsDialog @close="showSettings = false" />
    </q-dialog>
  </q-page>
</template>

<script setup lang="ts">
import { ref } from 'vue';
import { useRouter } from 'vue-router';
import { useVideoProjectStore } from '../stores';
import ProjectWizard from '../components/ProjectWizard.vue';
import AssetLibraryPanel from '../components/AssetLibraryPanel.vue';
import StoryDesigner from '../components/StoryDesigner.vue';
import AssetManager from '../components/AssetManager.vue';
import TimelineEditor from '../components/TimelineEditor.vue';
import ExportPanel from '../components/ExportPanel.vue';
import PropertiesPanel from '../components/PropertiesPanel.vue';
import GenerationQueuePanel from '../components/GenerationQueuePanel.vue';
import SettingsDialog from '../components/SettingsDialog.vue';

const router = useRouter();
const projectStore = useVideoProjectStore();

// UI State
const leftDrawerOpen = ref(true);
const rightDrawerOpen = ref(true);
const showSettings = ref(false);
const activeTab = ref<'story' | 'assets' | 'timeline' | 'export'>('story');

// Methods
function onProjectReady(): void {
  // Project is now open, workspace will be shown
  activeTab.value = 'story';
}

function goHome(): void {
  void router.push('/');
}

async function saveProject(): Promise<void> {
  try {
    await projectStore.saveProject();
  } catch (e) {
    console.error('Failed to save project:', e);
  }
}
</script>

<style scoped lang="scss">
.video-editor-page {
  height: 100vh;
  display: flex;
  flex-direction: column;
}

.workspace-container {
  display: flex;
  flex-direction: column;
  height: 100%;
}

.toolbar {
  flex-shrink: 0;
  border-bottom: 1px solid rgba(255, 255, 255, 0.1);
}

.content-area {
  flex: 1;
  overflow: hidden;
  position: relative;
}

.main-content {
  overflow: auto;
  background: var(--q-grey-3);
}

.generation-queue {
  flex-shrink: 0;
  height: 100px;
  border-top: 1px solid rgba(255, 255, 255, 0.1);
}
</style>
