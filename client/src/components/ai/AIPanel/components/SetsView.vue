<template>
  <q-scroll-area class="sets-area">
    <div class="sets-container">
      <!-- Current Selection Info -->
      <div class="sets-current-info">
        <div class="sets-info-row">
          <span class="sets-info-label">Mode:</span>
          <span class="sets-info-value">{{ props.currentModeLabel }}</span>
        </div>
        <div class="sets-info-row">
          <span class="sets-info-label">Model:</span>
          <span class="sets-info-value">{{ props.activeModel?.name || 'None' }}</span>
          <span v-if="props.activeModel?.family" class="sets-info-family">({{ props.activeModel.family }})</span>
        </div>
      </div>

      <!-- Sets List -->
      <div class="sets-list">
        <div
          v-for="setOption in props.filteredSetOptions"
          :key="setOption.value"
          class="set-item"
          :class="{
            'set-item-active': props.selectedSetId === setOption.value,
            'set-item-incompatible': !setOption.compatible,
            'set-item-warning': setOption.compatible && !setOption.familyMatch,
          }"
          @click="$emit('select-set', setOption.value)"
        >
          <div class="set-item-icon">
            <q-icon
              :name="
                !setOption.compatible
                  ? 'error_outline'
                  : !setOption.familyMatch
                    ? 'warning_amber'
                    : 'folder'
              "
              :color="
                !setOption.compatible
                  ? 'negative'
                  : !setOption.familyMatch
                    ? 'warning'
                    : props.selectedSetId === setOption.value
                      ? 'primary'
                      : 'grey-6'
              "
              size="20px"
            />
          </div>
          <div class="set-item-content">
            <div class="set-item-header">
              <span class="set-item-name">{{ setOption.label }}</span>
              <q-icon
                v-if="props.selectedSetId === setOption.value"
                name="check_circle"
                color="primary"
                size="14px"
                class="q-ml-xs"
              />
            </div>
            <div class="set-item-description">{{ setOption.description }}</div>
            <div
              v-if="setOption.families && setOption.families.length > 0"
              class="set-item-families"
            >
              <q-icon name="memory" size="12px" color="grey-6" class="q-mr-xs" />
              <span>Supports: {{ setOption.families.join(', ') }}</span>
            </div>
            <div v-if="setOption.author" class="set-item-author">
              <q-icon name="person" size="12px" color="grey-6" class="q-mr-xs" />
              <span>{{ setOption.author }}</span>
            </div>
            <div class="set-item-meta">
              <q-chip
                v-if="!setOption.compatible"
                size="xs"
                color="red-1"
                text-color="negative"
                dense
                class="set-status-chip"
              >
                Not compatible with {{ props.currentModeLabel }}
              </q-chip>
              <q-chip
                v-else-if="!setOption.familyMatch"
                size="xs"
                color="orange-1"
                text-color="warning"
                dense
                class="set-status-chip"
              >
                Not optimized for {{ props.activeModel?.family }}
              </q-chip>
              <q-chip
                v-else-if="setOption.familyMatch"
                size="xs"
                color="green-1"
                text-color="positive"
                dense
                class="set-status-chip"
              >
                Optimized for {{ props.activeModel?.family }}
              </q-chip>
              <q-chip
                v-if="props.getSetTotalToolCount(setOption.value) > 0"
                size="xs"
                color="blue-1"
                text-color="primary"
                dense
                class="set-status-chip set-tools-chip"
                icon="construction"
                clickable
                @click.stop
              >
                {{ props.getSetTotalToolCount(setOption.value) }} tools
                <q-menu
                  anchor="bottom middle"
                  self="top middle"
                  :offset="[0, 4]"
                  class="tools-popup-menu"
                >
                  <q-card flat class="tools-popup-card">
                    <q-card-section class="q-pa-sm">
                      <div class="tools-popup-header">
                        <q-icon
                          name="construction"
                          size="14px"
                          color="primary"
                          class="q-mr-xs"
                        />
                        <span>Tools for {{ setOption.label }}</span>
                      </div>
                      <q-separator class="q-my-sm" />
                      <div class="tools-popup-content">
                        <div
                          v-for="(tools, mode) in props.getSetToolsByMode(setOption.value)"
                          :key="mode"
                          class="tools-mode-section"
                        >
                          <div class="tools-mode-header">
                            <q-icon
                              name="settings"
                              size="12px"
                              color="grey-6"
                              class="q-mr-xs"
                            />
                            <span class="tools-mode-name">{{
                              mode.charAt(0).toUpperCase() + mode.slice(1)
                            }}</span>
                            <q-chip
                              size="xs"
                              color="grey-3"
                              text-color="grey-7"
                              dense
                              class="q-ml-xs"
                            >
                              {{ tools.length }}
                            </q-chip>
                          </div>
                          <div class="tools-popup-list">
                            <q-chip
                              v-for="tool in tools"
                              :key="tool"
                              size="xs"
                              color="blue-1"
                              text-color="primary"
                              dense
                              class="tool-chip"
                            >
                              {{ tool }}
                            </q-chip>
                          </div>
                        </div>
                        <div
                          v-if="Object.keys(props.getSetToolsByMode(setOption.value)).length === 0"
                          class="tools-empty"
                        >
                          No tools configured
                        </div>
                      </div>
                    </q-card-section>
                  </q-card>
                </q-menu>
              </q-chip>
            </div>
          </div>
        </div>

        <!-- Empty State -->
        <div v-if="props.filteredSetOptions.length === 0" class="sets-empty">
          <q-icon name="folder_off" size="40px" color="grey-4" />
          <div class="sets-empty-text">No prompt sets available</div>
        </div>
      </div>
    </div>
  </q-scroll-area>
</template>

<script setup lang="ts">
interface SetOption {
  label: string;
  value: string;
  description: string;
  author?: string;
  compatible: boolean;
  familyMatch: boolean;
  families: string[];
}

interface ModelConfig {
  id: string;
  name: string;
  family: string;
}

const props = defineProps<{
  selectedSetId: string;
  currentModeLabel: string;
  activeModel: ModelConfig | undefined;
  filteredSetOptions: SetOption[];
  getSetToolsByMode: (setId: string) => Record<string, string[]>;
  getSetTotalToolCount: (setId: string) => number;
}>();

defineEmits<{
  'select-set': [setId: string];
}>();
</script>

<style scoped>
.sets-area {
  flex: 1;
  min-height: 0;
  width: 100%;
  background: #ffffff;
}

.sets-container {
  padding: 12px;
}

.sets-current-info {
  background: #f8f9fa;
  border: 1px solid #e0e0e0;
  border-radius: 8px;
  padding: 10px 12px;
  margin-bottom: 12px;
}

.sets-info-row {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 12px;
}

.sets-info-row + .sets-info-row {
  margin-top: 4px;
}

.sets-info-label {
  color: #757575;
  font-weight: 500;
}

.sets-info-value {
  color: #333333;
  font-weight: 600;
}

.sets-info-family {
  color: #9e9e9e;
  font-size: 11px;
}

.sets-list {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.set-item {
  display: flex;
  align-items: flex-start;
  gap: 12px;
  padding: 12px;
  border-radius: 8px;
  cursor: pointer;
  transition: all 0.15s ease;
  background: #f8f9fa;
  border: 1px solid transparent;
}

.set-item:hover {
  background: #f0f4f8;
  border-color: #e0e0e0;
}

.set-item-active {
  background: #e3f2fd;
  border-color: #90caf9;
}

.set-item-active:hover {
  background: #bbdefb;
  border-color: #64b5f6;
}

.set-item-incompatible {
  background: #ffebee;
  border-color: #ffcdd2;
  opacity: 0.8;
}

.set-item-incompatible:hover {
  background: #ffcdd2;
  border-color: #ef9a9a;
}

.set-item-warning {
  background: #fff8e1;
  border-color: #ffe082;
}

.set-item-warning:hover {
  background: #ffecb3;
  border-color: #ffd54f;
}

.set-item-icon {
  flex-shrink: 0;
  width: 32px;
  height: 32px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: #ffffff;
  border-radius: 6px;
  border: 1px solid #e0e0e0;
}

.set-item-active .set-item-icon {
  background: #e3f2fd;
  border-color: #90caf9;
}

.set-item-content {
  flex: 1;
  min-width: 0;
}

.set-item-header {
  display: flex;
  align-items: center;
  margin-bottom: 2px;
}

.set-item-name {
  font-size: 13px;
  font-weight: 600;
  color: #333333;
}

.set-item-active .set-item-name {
  color: #1976d2;
}

.set-item-description {
  font-size: 12px;
  color: #757575;
  line-height: 1.4;
  margin-bottom: 4px;
}

.set-item-families {
  display: flex;
  align-items: center;
  font-size: 11px;
  color: #757575;
  margin-bottom: 4px;
}

.set-item-author {
  display: flex;
  align-items: center;
  font-size: 11px;
  color: #9e9e9e;
  margin-bottom: 6px;
}

.set-item-meta {
  display: flex;
  flex-wrap: wrap;
  gap: 4px;
}

.set-status-chip {
  font-size: 10px !important;
  font-weight: 500;
}

.sets-empty {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 48px 20px;
  text-align: center;
}

.sets-empty-text {
  font-size: 14px;
  font-weight: 500;
  color: #757575;
  margin-top: 12px;
}

.set-tools-chip {
  cursor: pointer;
}

.set-tools-chip:hover {
  background: #bbdefb !important;
}

.tools-popup-menu {
  border-radius: 8px;
  box-shadow: 0 4px 15px rgba(0, 0, 0, 0.15);
  border: 1px solid #e0e0e0;
}

.tools-popup-card {
  min-width: 200px;
  max-width: 300px;
}

.tools-popup-header {
  display: flex;
  align-items: center;
  font-size: 11px;
  font-weight: 600;
  color: #424242;
  text-transform: uppercase;
  letter-spacing: 0.3px;
}

.tools-popup-content {
  max-height: 400px;
  overflow-y: auto;
}

.tools-mode-section {
  margin-bottom: 12px;
}

.tools-mode-section:last-child {
  margin-bottom: 0;
}

.tools-mode-header {
  display: flex;
  align-items: center;
  font-size: 11px;
  font-weight: 600;
  color: #616161;
  margin-bottom: 6px;
  padding-bottom: 4px;
  border-bottom: 1px solid #f0f0f0;
}

.tools-mode-name {
  text-transform: capitalize;
}

.tools-popup-list {
  display: flex;
  flex-wrap: wrap;
  gap: 4px;
  padding-top: 4px;
}

.tool-chip {
  font-family: 'JetBrains Mono', monospace;
  font-weight: 500;
  font-size: 10px !important;
}

.tools-empty {
  font-size: 11px;
  color: #9e9e9e;
  font-style: italic;
  text-align: center;
  padding: 8px 0;
}
</style>
