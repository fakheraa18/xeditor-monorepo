<template>
  <div class="status-bar row items-center no-wrap">
    <!-- Left Section -->
    <div class="status-section row items-center no-wrap">
      <!-- Git Branch (placeholder) -->
      <div class="status-item" v-if="false">
        <q-icon name="call_split" size="14px" />
        <span>main</span>
      </div>

      <!-- Indexing Status -->
      <div
        v-if="statusText"
        class="status-item clickable"
        :class="statusClass"
        @click="navigateToIndex"
      >
        <q-icon :name="statusIcon" size="14px" :class="{ rotating: isProcessing }" />
        <span>{{ statusText }}</span>
        <q-tooltip :delay="300">{{ statusTooltip }}</q-tooltip>
      </div>

      <!-- Reindex Button -->
      <div
        v-if="hasFolders && (!isIndexing || (progress && progress.phase === 'paused'))"
        class="status-item clickable"
        @click="handleReindexOrResume"
      >
        <q-icon :name="progress?.phase === 'paused' ? 'play_arrow' : 'refresh'" size="14px" />
        <q-tooltip :delay="300">
          {{ progress?.phase === 'paused' ? 'Resume Indexing' : 'Reindex Codebase' }}
        </q-tooltip>
      </div>

      <!-- Companion Status -->
      <div
        class="status-item clickable"
        :class="companionConnected ? 'status-positive' : 'status-muted'"
        @click="toggleCompanion"
      >
        <q-icon :name="companionConnected ? 'terminal' : 'portable_wifi_off'" size="14px" />
        <span>{{ companionConnected ? 'Companion' : 'Offline' }}</span>
        <q-tooltip :delay="300">
          {{
            companionConnected
              ? 'Local Companion connected'
              : 'Local Companion disconnected - Click to connect'
          }}
        </q-tooltip>
      </div>

      <!-- Update Info -->
      <div
        v-if="updateInfo"
        class="status-item"
        :class="updateInfo.link ? 'clickable' : ''"
        @click="updateInfo.link ? handleUpdateLinkClick(updateInfo.link) : undefined"
      >
        <q-icon name="system_update" size="14px" class="status-warning" />
        <span class="status-warning">
          {{
            updateInfo.text ||
            updateInfo.message ||
            (updateInfo.version ? `v${updateInfo.version} available` : 'Update available')
          }}
        </span>
        <q-tooltip v-if="updateInfo.message || updateInfo.text" :delay="300">
          {{ updateInfo.message || updateInfo.text }}
        </q-tooltip>
      </div>

      <!-- Errors/Warnings (placeholder for future) -->
      <div class="status-item" v-if="false">
        <q-icon name="error_outline" size="14px" color="negative" />
        <span>0</span>
        <q-icon name="warning" size="14px" color="warning" class="q-ml-sm" />
        <span>0</span>
      </div>
    </div>

    <q-space />

    <!-- Right Section -->
    <div class="status-section row items-center no-wrap">
      <!-- Cursor Position -->
      <div v-if="cursorPosition" class="status-item">
        <span>Ln {{ cursorPosition.line }}, Col {{ cursorPosition.column }}</span>
        <q-tooltip :delay="300">Go to Line</q-tooltip>
      </div>

      <!-- Selection Info -->
      <div v-if="selectionInfo" class="status-item">
        <span>{{ selectionInfo }}</span>
        <q-tooltip :delay="300">Selection</q-tooltip>
      </div>

      <!-- Indentation -->
      <div class="status-item">
        <span>Spaces: 2</span>
      </div>

      <!-- Encoding -->
      <div class="status-item">
        <span>UTF-8</span>
      </div>

      <!-- Line Endings -->
      <div class="status-item">
        <span>LF</span>
      </div>

      <!-- Language -->
      <div v-if="activeLanguage" class="status-item clickable">
        <span>{{ formatLanguage(activeLanguage) }}</span>
        <q-tooltip :delay="300">Select Language Mode</q-tooltip>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue';
import { useRouter } from 'vue-router';
import { storeToRefs } from 'pinia';
import { useEditorStore } from '../../../../stores/editor';
import { useIndexingStore } from '../../../../stores/indexing';
import { useProjectStore } from '../../../../stores/project';
import { useLocalCompanionStore } from '../../../../stores/localCompanion';
import { useUpdateInfo } from '../../../../composables/useUpdateInfo';

const router = useRouter();
const editorStore = useEditorStore();
const indexingStore = useIndexingStore();
const projectStore = useProjectStore();
const companionStore = useLocalCompanionStore();
const { updateInfo, handleLinkClick } = useUpdateInfo();

const { cursorPosition, selectedText, activeTab } = storeToRefs(editorStore);
const { statusText, statusIcon, statusTooltip, statusClass, isProcessing, progress, isIndexing } =
  storeToRefs(indexingStore);
const { hasFolders, activeProjectId } = storeToRefs(projectStore);

const companionConnected = computed(() => companionStore.isConnected);

const activeLanguage = computed(() => activeTab.value?.language || null);

const selectionInfo = computed(() => {
  if (!selectedText.value) return null;
  const lines = selectedText.value.split('\n').length;
  const chars = selectedText.value.length;
  if (lines > 1) {
    return `${lines} lines, ${chars} chars`;
  }
  if (chars > 0) {
    return `${chars} selected`;
  }
  return null;
});

function formatLanguage(lang: string): string {
  const languageNames: Record<string, string> = {
    typescript: 'TypeScript',
    javascript: 'JavaScript',
    python: 'Python',
    html: 'HTML',
    css: 'CSS',
    scss: 'SCSS',
    json: 'JSON',
    markdown: 'Markdown',
    rust: 'Rust',
    go: 'Go',
    java: 'Java',
    cpp: 'C++',
    c: 'C',
    shell: 'Shell',
    sql: 'SQL',
    yaml: 'YAML',
    xml: 'XML',
    plaintext: 'Plain Text',
  };

  return languageNames[lang] || lang.charAt(0).toUpperCase() + lang.slice(1);
}

function navigateToIndex() {
  void router.push('/index-explorer');
}

async function toggleCompanion() {
  if (companionConnected.value) {
    companionStore.disconnect();
  } else {
    await companionStore.connect();
  }
}

async function handleReindexOrResume() {
  if (!activeProjectId.value) return;
  if (progress.value?.phase === 'paused') {
    indexingStore.resumeIndexing();
  } else {
    await indexingStore.reindex(activeProjectId.value);
  }
}

function handleUpdateLinkClick(link: string): void {
  handleLinkClick(link);
}
</script>

<style scoped>
.status-bar {
  height: 22px;
  min-height: 22px;
  max-height: 22px;
  background: #007acc;
  color: #ffffff;
  font-size: 12px;
  padding: 0 10px;
  user-select: none;
}

.status-section {
  gap: 2px;
}

.status-item {
  display: flex;
  align-items: center;
  gap: 4px;
  padding: 0 6px;
  height: 22px;
  white-space: nowrap;
}

.status-item.clickable {
  cursor: pointer;
  border-radius: 2px;
  transition: background-color 0.15s ease;
}

.status-item.clickable:hover {
  background: rgba(255, 255, 255, 0.12);
}

.status-primary {
  color: #ffffff;
}

.status-positive {
  color: #89d185;
}

.status-warning {
  color: #ddb64c;
}

.status-negative {
  color: #f48771;
}

.status-muted {
  color: rgba(255, 255, 255, 0.6);
}

.rotating {
  animation: rotate 2s linear infinite;
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
