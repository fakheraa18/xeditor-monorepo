<template>
  <div class="search-settings q-pa-sm q-gutter-y-sm bg-grey-2 border-radius-sm">
    <div class="text-caption text-weight-bold text-grey-7">Search Settings</div>
    <div class="row q-col-gutter-sm">
      <div class="col-12 col-sm-6">
        <q-input
          v-model="includePattern"
          label="Include patterns"
          placeholder="e.g. **/*.ts"
          dense
          outlined
          stack-label
          bg-color="white"
          @update:model-value="updateInclude"
        >
          <template v-slot:append>
            <q-icon name="help_outline" size="xs">
              <q-tooltip>Comma separated glob patterns to include</q-tooltip>
            </q-icon>
          </template>
        </q-input>
      </div>
      <div class="col-12 col-sm-6">
        <q-input
          v-model="excludePattern"
          label="Exclude patterns"
          placeholder="e.g. **/tests/**"
          dense
          outlined
          stack-label
          bg-color="white"
          @update:model-value="updateExclude"
        >
          <template v-slot:append>
            <q-icon name="help_outline" size="xs">
              <q-tooltip>Comma separated glob patterns to exclude</q-tooltip>
            </q-icon>
          </template>
        </q-input>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue';
import { useSearchStore } from '../../stores/search';

const searchStore = useSearchStore();

const includePattern = ref(searchStore.includePattern);
const excludePattern = ref(searchStore.excludePattern);

function updateInclude(val: string | number | null) {
  searchStore.setIncludePattern(String(val || ''));
}

function updateExclude(val: string | number | null) {
  searchStore.setExcludePattern(String(val || ''));
}
</script>

<style scoped>
.search-settings {
  border: 1px solid rgba(0, 0, 0, 0.12);
  border-radius: 4px;
}
</style>
