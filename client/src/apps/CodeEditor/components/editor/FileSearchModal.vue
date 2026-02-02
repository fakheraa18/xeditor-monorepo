<template>
  <q-dialog
    v-model="isSearchModalOpen"
    position="top"
    transition-show="jump-down"
    transition-hide="jump-up"
    @show="onModalShow"
  >
    <q-card style="width: 700px; max-width: 90vw" class="search-modal-card">
      <q-card-section class="q-pa-none">
        <q-input
          ref="searchInputRef"
          v-model="searchQuery"
          placeholder="Search files by name..."
          dense
          borderless
          autofocus
          class="search-input q-px-md q-py-sm"
          @keydown="handleKeyDown"
        >
          <template v-slot:prepend>
            <q-icon name="search" />
          </template>
          <template v-slot:append>
            <q-btn
              flat
              dense
              round
              size="sm"
              :icon="showSettings ? 'settings' : 'settings_applications'"
              @click="showSettings = !showSettings"
              :color="showSettings ? 'primary' : 'grey'"
            >
              <q-tooltip>Search Settings</q-tooltip>
            </q-btn>
            <q-btn flat dense round size="sm" icon="close" v-close-popup />
          </template>
        </q-input>

        <q-separator v-if="showSettings" />
        <q-slide-transition>
          <div v-if="showSettings">
            <SearchSettings />
          </div>
        </q-slide-transition>

        <q-separator />

        <q-scroll-area style="height: 400px">
          <q-list v-if="searchResults.length > 0" class="q-py-none">
            <q-item
              v-for="(result, index) in searchResults"
              :key="result.item.path"
              clickable
              v-ripple
              :active="selectedIndex === index"
              active-class="bg-blue-1 text-primary"
              class="search-result-item"
              @click="selectResult(result.item)"
            >
              <q-item-section avatar>
                <q-icon name="description" color="grey-7" size="sm" />
              </q-item-section>
              <q-item-section>
                <q-item-label class="text-weight-medium">
                  {{ result.item.name }}
                </q-item-label>
                <q-item-label caption class="ellipsis">
                  {{ result.item.relativePath }}
                </q-item-label>
              </q-item-section>
              <q-item-section side v-if="selectedIndex === index">
                <q-item-label caption>Enter to open</q-item-label>
              </q-item-section>
            </q-item>
          </q-list>
          <div v-else-if="searchQuery" class="q-pa-md text-center text-grey-7">
            No files match your search.
          </div>
          <div v-else class="q-pa-md text-center text-grey-7">Type to start searching files...</div>
        </q-scroll-area>
      </q-card-section>

      <q-separator />

      <q-card-actions align="right" class="bg-grey-1 text-grey-7 q-py-xs q-px-md footer-hint">
        <div class="row q-gutter-x-md items-center">
          <div class="row items-center q-gutter-x-xs">
            <q-badge color="grey-4" text-color="grey-9" label="↑↓" />
            <span>to navigate</span>
          </div>
          <div class="row items-center q-gutter-x-xs">
            <q-badge color="grey-4" text-color="grey-9" label="Enter" />
            <span>to open</span>
          </div>
          <div class="row items-center q-gutter-x-xs">
            <q-badge color="grey-4" text-color="grey-9" label="Esc" />
            <span>to dismiss</span>
          </div>
        </div>
      </q-card-actions>
    </q-card>
  </q-dialog>
</template>

<script setup lang="ts">
import { ref, computed, watch, nextTick } from 'vue';
import { storeToRefs } from 'pinia';
import { QInput } from 'quasar';
import Fuse from 'fuse.js';
import { useSearchStore } from '../../stores/search';
import { useProjectStore } from '../../stores/project';
import { useEditorStore } from '../../stores/editor';
import { useShortcuts } from '../../composables/useShortcuts';
import SearchSettings from './SearchSettings.vue';
import type { FileNode } from 'src/apps/CodeEditor/core/types';

interface SearchableFile {
  name: string;
  path: string;
  relativePath: string;
}

const searchStore = useSearchStore();
const projectStore = useProjectStore();
const editorStore = useEditorStore();
const { pushScope, popScope } = useShortcuts();

const { isSearchModalOpen, includePattern, excludePattern } = storeToRefs(searchStore);
const { fileTree } = storeToRefs(projectStore);

// Manage scope for this modal
watch(isSearchModalOpen, async (isOpen) => {
  if (isOpen) {
    pushScope('fileSearchModal', 10); // Higher priority than global
    // Reset search query when opening
    searchQuery.value = '';
    selectedIndex.value = 0;

    // Ensure focus after modal opens and animations start
    await nextTick();
    setTimeout(() => {
      searchInputRef.value?.focus();
    }, 100);
  } else {
    popScope('fileSearchModal');
  }
});

const searchQuery = ref('');
const showSettings = ref(false);
const selectedIndex = ref(0);
const searchInputRef = ref<QInput | null>(null);

// Flatten the file tree into a searchable list
const allFiles = computed<SearchableFile[]>(() => {
  const files: SearchableFile[] = [];

  function traverse(nodes: FileNode[], _currentPath: string = '') {
    for (const node of nodes) {
      if (node.type === 'file') {
        files.push({
          name: node.name,
          path: node.path,
          relativePath: node.path.includes('/')
            ? node.path.split('/').slice(1).join('/')
            : node.name,
        });
      } else if (node.type === 'directory' && node.children) {
        traverse(node.children, node.path);
      }
    }
  }

  traverse(fileTree.value);
  return files;
});

// Fuse.js setup
const fuseOptions = {
  keys: ['name', 'relativePath'],
  threshold: 0.4,
  includeMatches: true,
  shouldSort: true,
};

const fuse = computed(() => new Fuse(allFiles.value, fuseOptions));

// Search logic
const searchResults = computed(() => {
  if (!searchQuery.value) return [];

  let results = fuse.value.search(searchQuery.value);

  // Apply include/exclude patterns if they exist
  if (includePattern.value || excludePattern.value) {
    const includes = includePattern.value
      .split(',')
      .map((p) => p.trim())
      .filter(Boolean);
    const excludes = excludePattern.value
      .split(',')
      .map((p) => p.trim())
      .filter(Boolean);

    results = results.filter((result) => {
      const path = result.item.relativePath;

      // Simple glob-to-regex conversion for demonstration
      // In a real app, you might want a library like 'picomatch'
      const matchPattern = (pattern: string, target: string) => {
        const regexStr = pattern
          .replace(/\*\*/g, '(.+)')
          .replace(/\*/g, '([^/]+)')
          .replace(/\?/g, '(.)');
        const regex = new RegExp(`^${regexStr}$`);
        return regex.test(target);
      };

      if (includes.length > 0) {
        if (!includes.some((pattern) => matchPattern(pattern, path))) return false;
      }

      if (excludes.length > 0) {
        if (excludes.some((pattern) => matchPattern(pattern, path))) return false;
      }

      return true;
    });
  }

  return results.slice(0, 50); // Limit to top 50 results
});

// Watch search query and reset selected index
watch(searchQuery, () => {
  selectedIndex.value = 0;
});

function onModalShow() {
  // Reset and focus again on show to be sure
  searchQuery.value = '';
  selectedIndex.value = 0;
  setTimeout(() => {
    searchInputRef.value?.focus();
  }, 50);
}

function handleKeyDown(event: KeyboardEvent) {
  if (event.key === 'ArrowDown') {
    event.preventDefault();
    selectedIndex.value = (selectedIndex.value + 1) % searchResults.value.length;
  } else if (event.key === 'ArrowUp') {
    event.preventDefault();
    selectedIndex.value =
      (selectedIndex.value - 1 + searchResults.value.length) % searchResults.value.length;
  } else if (event.key === 'Enter') {
    event.preventDefault();
    const selectedResult = searchResults.value[selectedIndex.value];
    if (selectedResult) {
      selectResult(selectedResult.item);
    }
  } else if (event.key === 'Escape') {
    searchStore.toggleSearchModal(false);
  }
}

function selectResult(file: SearchableFile) {
  void editorStore.openFile(file.path);
  searchStore.toggleSearchModal(false);
}
</script>

<style scoped>
.search-modal-card {
  border-radius: 8px;
  overflow: hidden;
  box-shadow: 0 8px 32px rgba(0, 0, 0, 0.2);
}

.search-input {
  font-size: 1.1rem;
}

.search-result-item {
  min-height: 48px;
}

.footer-hint {
  font-size: 0.75rem;
}

:deep(.q-item--active) {
  border-left: 3px solid var(--q-primary);
}
</style>
