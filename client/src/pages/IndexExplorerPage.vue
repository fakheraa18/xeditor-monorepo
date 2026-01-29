<template>
  <q-page class="index-explorer-page">
    <q-scroll-area class="absolute-full">
      <div class="q-pa-md">
        <div class="row items-center q-mb-lg">
          <q-btn flat icon="arrow_back" to="/" class="q-mr-sm" />
          <h4 class="q-ma-none">Index Explorer</h4>
        </div>

        <div class="row q-col-gutter-md">
      <!-- Index Statistics Card -->
      <q-card class="col-12 col-md-6">
        <q-card-section>
          <div class="text-h6 q-mb-md">Index Statistics</div>

          <div class="q-mb-md">
            <q-select
              v-model="selectedEmbeddingModel"
              :options="embeddingModelOptions"
              option-label="label"
              option-value="value"
              emit-value
              map-options
              outlined
              dense
              label="Embedding Model (per project)"
              :disable="!projectStore.activeProjectId"
              @update:model-value="handleEmbeddingModelChange"
            />
            <div class="text-caption text-grey-7 q-mt-xs">
              Changing the embedding model will trigger a reindex for this project.
            </div>
          </div>

          <div v-if="!indexStats" class="text-grey-7 text-center q-pa-md">
            No index available
          </div>
          <div v-else class="column q-gutter-sm">
            <div class="row items-center justify-between">
              <span class="text-body2">Files Indexed:</span>
              <span class="text-weight-bold">{{ indexStats.fileCount.toLocaleString() }}</span>
            </div>
            <div class="row items-center justify-between">
              <span class="text-body2">Symbols Extracted:</span>
              <span class="text-weight-bold">{{ indexStats.symbolCount.toLocaleString() }}</span>
            </div>
            <div class="row items-center justify-between">
              <span class="text-body2">Code Chunks:</span>
              <span class="text-weight-bold">{{ indexStats.chunkCount.toLocaleString() }}</span>
            </div>
            <div class="row items-center justify-between">
              <span class="text-body2">Vectors Stored:</span>
              <span class="text-weight-bold">{{ indexStats.vectorCount.toLocaleString() }}</span>
            </div>
            <q-separator class="q-my-sm" />
            <div class="row items-center justify-between">
              <span class="text-body2">Index Version:</span>
              <span class="text-weight-bold">v{{ indexStats.version }}</span>
            </div>
            <div class="row items-center justify-between">
              <span class="text-body2">Last Updated:</span>
              <span class="text-caption">{{ formatTimestamp(indexStats.lastUpdated) }}</span>
            </div>
          </div>
        </q-card-section>
      </q-card>

      <!-- Indexing Status Card -->
      <q-card class="col-12 col-md-6">
        <q-card-section>
          <div class="text-h6 q-mb-md">Indexing Status</div>
          
          <div v-if="!indexingProgress && !indexStats" class="text-grey-7 text-center q-pa-md">
            Idle
          </div>
          
          <div v-else-if="!indexingProgress && indexStats" class="column q-gutter-sm">
            <div class="row items-center justify-between">
              <span class="text-body2">Status:</span>
              <q-chip
                color="positive"
                text-color="white"
                label="Index Ready"
                size="sm"
                icon="check_circle"
              />
            </div>
            
            <q-separator class="q-my-sm" />
            
            <div class="row items-center justify-between">
              <span class="text-body2">Trigger Reason:</span>
              <span class="text-caption">{{ lastTriggerReason || 'Unknown' }}</span>
            </div>
            
            <!-- Memory Usage -->
            <div v-if="memoryUsage.available" class="q-mt-sm">
              <div class="row items-center justify-between q-mb-xs">
                <span class="text-body2">Memory Usage:</span>
                <span class="text-caption">
                  {{ formatBytes(memoryUsage.used) }} / {{ formatBytes(memoryUsage.limit) }}
                  ({{ Math.round(memoryUsage.percentage) }}%)
                </span>
              </div>
              <q-linear-progress
                :value="memoryUsage.percentage / 100"
                :color="getMemoryColor(memoryUsage.percentage)"
                class="q-mt-xs"
              />
            </div>
            
            <!-- Control Buttons -->
            <div class="row q-gutter-xs q-mt-md">
              <q-btn
                v-if="!isIndexing"
                flat
                dense
                color="primary"
                icon="refresh"
                label="Reindex"
                @click="handleReindex"
              />
            </div>
          </div>
          
          <template v-else-if="indexingProgress">
            <div class="column q-gutter-sm">
              <div class="row items-center justify-between">
                <span class="text-body2">Phase:</span>
                <q-chip
                  :color="getPhaseColor(indexingProgress?.phase ?? '')"
                  text-color="white"
                  :label="indexingProgress?.phase ?? ''"
                  size="sm"
                />
              </div>
              
              <div v-if="(indexingProgress?.totalFiles ?? 0) > 0" class="q-mt-sm">
                <div class="row items-center justify-between q-mb-xs">
                  <span class="text-body2">
                    {{ indexingProgress?.filesProcessed ?? 0 }}/{{ indexingProgress?.totalFiles ?? 0 }} files
                  </span>
                  <span class="text-caption">
                    {{ Math.round(((indexingProgress?.filesProcessed ?? 0) / (indexingProgress?.totalFiles ?? 1)) * 100) }}%
                  </span>
                </div>
                <q-linear-progress
                  :value="(indexingProgress?.filesProcessed ?? 0) / (indexingProgress?.totalFiles ?? 1)"
                  :color="getPhaseColor(indexingProgress?.phase ?? '')"
                  class="q-mt-xs"
                />
              </div>
              
              <div v-if="indexingProgress?.currentFile" class="text-caption text-grey-7 q-mt-xs">
                {{ indexingProgress.currentFile.split('/').pop() }}
              </div>
              
              <div v-if="indexingProgress?.pausedReason" class="text-caption text-warning q-mt-xs">
                Paused: {{ indexingProgress.pausedReason === 'memory' ? 'Memory limit reached' : 'User requested' }}
              </div>
              
              <div v-if="indexingProgress?.error" class="text-caption text-negative q-mt-xs">
                Error: {{ indexingProgress.error }}
              </div>
            
            <q-separator class="q-my-sm" />
            
            <div class="row items-center justify-between">
              <span class="text-body2">Trigger Reason:</span>
              <span class="text-caption">{{ lastTriggerReason || 'Unknown' }}</span>
            </div>
            
            <!-- Memory Usage -->
            <div v-if="memoryUsage.available" class="q-mt-sm">
              <div class="row items-center justify-between q-mb-xs">
                <span class="text-body2">Memory Usage:</span>
                <span class="text-caption">
                  {{ formatBytes(memoryUsage.used) }} / {{ formatBytes(memoryUsage.limit) }}
                  ({{ Math.round(memoryUsage.percentage) }}%)
                </span>
              </div>
              <q-linear-progress
                :value="memoryUsage.percentage / 100"
                :color="getMemoryColor(memoryUsage.percentage)"
                class="q-mt-xs"
              />
            </div>
            
            <!-- Control Buttons -->
            <div class="row q-gutter-xs q-mt-md">
              <q-btn
                v-if="isIndexing && indexingProgress && indexingProgress.phase !== 'paused'"
                flat
                dense
                color="warning"
                icon="pause"
                label="Pause"
                @click="pauseIndexing"
              />
              <q-btn
                v-if="indexingProgress && indexingProgress.phase === 'paused'"
                flat
                dense
                color="positive"
                icon="play_arrow"
                label="Resume"
                @click="resumeIndexing"
              />
              <q-btn
                v-if="isIndexing"
                flat
                dense
                color="negative"
                icon="stop"
                label="Cancel"
                @click="cancelIndexing"
              />
              <q-btn
                v-if="!isIndexing"
                flat
                dense
                color="primary"
                icon="refresh"
                label="Reindex"
                @click="handleReindex"
              />
            </div>
            </div>
          </template>
        </q-card-section>
      </q-card>

      <!-- NLP Search Test Interface -->
      <q-card class="col-12">
        <q-card-section>
          <div class="text-h6 q-mb-md">NLP Code Search</div>
          
          <div class="row q-gutter-md q-mb-md">
            <q-input
              v-model="searchQuery"
              placeholder="Search code with natural language... (e.g., 'where is user authentication handled?')"
              outlined
              dense
              class="col"
              @keyup.enter="performSearch"
            >
              <template v-slot:append>
                <q-icon
                  v-if="searchQuery"
                  name="close"
                  @click="searchQuery = ''"
                  class="cursor-pointer"
                />
              </template>
            </q-input>
            
            <q-select
              v-model="searchType"
              :options="searchTypeOptions"
              option-label="label"
              option-value="value"
              emit-value
              map-options
              outlined
              dense
              style="min-width: 150px"
            />
            
            <q-btn
              color="primary"
              label="Search"
              icon="search"
              :loading="isSearching"
              :disable="!searchQuery.trim() || !hasProject"
              @click="performSearch"
            />
          </div>
          
          <div v-if="searchResults.length > 0" class="q-mt-md">
            <div class="text-subtitle2 q-mb-sm">
              Found {{ searchResults.length }} result(s)
            </div>
            <q-list separator>
              <q-item
                v-for="(result, idx) in searchResults"
                :key="idx"
                clickable
                @click="openFileAtLine(result.filePath, result.startLine)"
              >
                <q-item-section>
                  <q-item-label>
                    {{ result.filePath }}
                    <q-chip
                      :color="getMatchTypeColor(result.matchType)"
                      text-color="white"
                      :label="result.matchType"
                      size="xs"
                      class="q-ml-sm"
                    />
                    <span class="text-caption text-grey-7 q-ml-sm">
                      Lines {{ result.startLine + 1 }}-{{ result.endLine + 1 }}
                    </span>
                    <span class="text-caption text-grey-7 q-ml-sm">
                      Score: {{ result.relevanceScore.toFixed(2) }}
                    </span>
                  </q-item-label>
                  <q-item-label caption>
                    <pre class="code-preview">{{ result.preview }}</pre>
                  </q-item-label>
                </q-item-section>
              </q-item>
            </q-list>
          </div>
          
          <div v-else-if="hasSearched && !isSearching" class="text-grey-7 text-center q-pa-md">
            No results found
          </div>
        </q-card-section>
      </q-card>
        </div>
      </div>
    </q-scroll-area>
  </q-page>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, watch } from 'vue';
import { storeToRefs } from 'pinia';
import { useIndexingStore } from '../stores/indexing';
import { useProjectStore } from '../stores/project';
import { useEditorStore } from '../stores/editor';
import { retrieval } from '../core/indexing/Retrieval';
import type { SearchResult } from '../core/indexing/types';
import type { EmbeddingModelId } from '../core/types';

const indexingStore = useIndexingStore();
const projectStore = useProjectStore();
const editorStore = useEditorStore();

const { progress: indexingProgress, isIndexing, lastTriggerReason, indexStats, memoryUsage } =
  storeToRefs(indexingStore);

const hasProject = computed(() => projectStore.hasConnectedFolders);

const searchQuery = ref('');
const searchType = ref<'text' | 'symbol' | 'semantic'>('semantic');
const searchResults = ref<SearchResult[]>([]);
const isSearching = ref(false);
const hasSearched = ref(false);

const searchTypeOptions = [
  { label: 'Semantic', value: 'semantic' },
  { label: 'Symbol', value: 'symbol' },
  { label: 'Text', value: 'text' },
];

const embeddingModelOptions: Array<{ label: string; value: EmbeddingModelId }> = [
  { label: 'MiniLM (384d) — sentence-transformers/all-MiniLM-L6-v2', value: 'sentence-transformers/all-MiniLM-L6-v2' },
  { label: 'BGE Small (384d) — BAAI/bge-small-en', value: 'BAAI/bge-small-en' },
  { label: 'GTE Small (384d) — thenlper/gte-small', value: 'thenlper/gte-small' },
  { label: 'CodeBERT (768d) — microsoft/codebert-base', value: 'microsoft/codebert-base' },
];

const selectedEmbeddingModel = ref<EmbeddingModelId>(projectStore.getEmbeddingModelId());

async function handleEmbeddingModelChange(modelId: EmbeddingModelId) {
  if (!projectStore.activeProjectId) return;
  await projectStore.setEmbeddingModelId(modelId);
}

async function performSearch() {
  if (!searchQuery.value.trim() || !projectStore.activeProjectId) {
    return;
  }

  isSearching.value = true;
  hasSearched.value = true;
  searchResults.value = [];

  try {
    const results = await retrieval.search(
      projectStore.activeProjectId,
      searchQuery.value,
      searchType.value,
      20,
    );
    searchResults.value = results;
  } catch (error) {
    console.error('Search failed:', error);
  } finally {
    isSearching.value = false;
  }
}

function pauseIndexing() {
  indexingStore.pauseIndexing();
}

function resumeIndexing() {
  indexingStore.resumeIndexing();
}

function cancelIndexing() {
  indexingStore.cancelIndexing();
}

async function handleReindex() {
  if (!projectStore.activeProjectId) return;
  await indexingStore.reindex(projectStore.activeProjectId);
}

function openFileAtLine(filePath: string, _lineNumber: number) {
  void editorStore.openFile(filePath);
  // Note: Monaco editor line navigation would need to be implemented separately
}

function getPhaseColor(phase: string): string {
  switch (phase) {
    case 'scanning':
    case 'parsing':
    case 'embedding':
      return 'primary';
    case 'paused':
      return 'warning';
    case 'complete':
      return 'positive';
    case 'error':
      return 'negative';
    default:
      return 'grey';
  }
}

function getMemoryColor(percentage: number): string {
  if (percentage < 50) return 'positive';
  if (percentage < 75) return 'warning';
  return 'negative';
}

function getMatchTypeColor(matchType: string): string {
  switch (matchType) {
    case 'semantic':
      return 'primary';
    case 'symbol':
      return 'secondary';
    case 'text':
      return 'accent';
    default:
      return 'grey';
  }
}

function formatBytes(bytes: number): string {
  if (bytes === 0) return '0 B';
  const k = 1024;
  const sizes = ['B', 'KB', 'MB', 'GB'];
  const i = Math.floor(Math.log(bytes) / Math.log(k));
  return `${(bytes / Math.pow(k, i)).toFixed(1)} ${sizes[i]}`;
}

function formatTimestamp(timestamp: number): string {
  const date = new Date(timestamp);
  return date.toLocaleString();
}

onMounted(() => {
  // Load stats when page mounts
  void indexingStore.loadStats();
  selectedEmbeddingModel.value = projectStore.getEmbeddingModelId();
});

// Watch for project changes and reload stats
watch(
  () => projectStore.activeProjectId,
  (projectId) => {
    if (projectId) {
      void indexingStore.loadStats();
      selectedEmbeddingModel.value = projectStore.getEmbeddingModelId();
    }
  },
  { immediate: true },
);
</script>

<style scoped>
.index-explorer-page {
  height: 100%;
  width: 100%;
}

.index-explorer-page .q-pa-md {
  max-width: 1400px;
  margin: 0 auto;
}

.code-preview {
  margin: 0;
  padding: 8px;
  background: #f5f5f5;
  border-radius: 4px;
  font-family: 'Courier New', monospace;
  font-size: 12px;
  white-space: pre-wrap;
  word-break: break-word;
  max-height: 100px;
  overflow: hidden;
}
</style>

