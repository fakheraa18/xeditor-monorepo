<template>
  <div class="ai-input-area">
    <!-- Mode and Model Toolbar -->
    <div class="input-toolbar row items-center justify-between">
      <div class="row items-center q-gutter-xs">
        <q-btn-dropdown flat dense no-caps size="sm" color="primary" class="mode-dropdown">
          <template v-slot:label>
            <div class="row items-center no-wrap">
              <span class="q-mr-xs">{{ props.currentModeLabel }}</span>
            </div>
          </template>
          <q-list dense style="min-width: 100px">
            <q-item
              v-for="option in props.modeOptions"
              :key="option.value"
              clickable
              v-close-popup
              :active="props.selectedMode === option.value"
              active-class="text-primary bg-blue-1"
              @click="$emit('select-mode', option.value)"
            >
              <q-item-section>
                <q-item-label>{{ option.label }}</q-item-label>
              </q-item-section>
              <q-item-section v-if="props.selectedMode === option.value" side>
                <q-icon name="check" size="12px" color="primary" />
              </q-item-section>
            </q-item>
          </q-list>
        </q-btn-dropdown>
        <q-separator vertical class="q-mx-xs" />
        <q-select
          :model-value="props.selectedModelId"
          :options="props.modelOptions"
          option-label="name"
          option-value="id"
          emit-value
          map-options
          dense
          borderless
          class="model-selector"
          @update:model-value="$emit('select-model', $event)"
        >
          <template v-slot:prepend>
            <q-icon name="memory" size="16px" color="grey-6" />
          </template>
          <template v-slot:selected-item="scope">
            <div class="model-selector-selected">
              <div class="model-selector-name">{{ scope.opt.name }}</div>
              <div class="model-selector-family">{{ scope.opt.family }}</div>
            </div>
          </template>
          <template v-slot:option="scope">
            <q-item v-bind="scope.itemProps">
              <q-item-section>
                <q-item-label>{{ scope.opt.name }}</q-item-label>
                <q-item-label caption class="model-option-family">{{
                  scope.opt.family
                }}</q-item-label>
              </q-item-section>
            </q-item>
          </template>
        </q-select>
        <!-- Active Set Indicator -->
        <q-separator vertical class="q-mx-xs" />
        <div
          class="active-set-indicator row items-center no-wrap"
          :class="{
            'set-error': props.currentSetStatus && !props.currentSetStatus.compatible,
            'set-warning':
              props.currentSetStatus &&
              props.currentSetStatus.compatible &&
              !props.currentSetStatus.familyMatch,
          }"
          @click="$emit('show-sets')"
        >
          <q-icon
            :name="
              !props.currentSetStatus?.compatible
                ? 'error_outline'
                : !props.currentSetStatus?.familyMatch
                  ? 'warning_amber'
                  : 'folder'
            "
            size="14px"
            :color="
              !props.currentSetStatus?.compatible
                ? 'negative'
                : !props.currentSetStatus?.familyMatch
                  ? 'warning'
                  : 'grey-6'
            "
            class="q-mr-xs"
          />
          <div class="active-set-content">
            <div class="active-set-name">{{ props.currentSetStatus?.label || 'Select Set' }}</div>
            <div
              v-if="props.currentSetStatus?.families && props.currentSetStatus.families.length > 0"
              class="active-set-families"
            >
              {{ props.currentSetStatus.families.join(', ') }}
            </div>
          </div>
          <q-tooltip v-if="props.currentSetStatus && !props.currentSetStatus.compatible">
            This set does not support {{ props.currentModeLabel }} mode. Click to change.
          </q-tooltip>
          <q-tooltip
            v-else-if="props.currentSetStatus && !props.currentSetStatus.familyMatch"
            class="bg-warning text-black"
          >
            This set is not optimized for {{ props.activeModel?.family }} models. Click to change.
          </q-tooltip>
          <q-tooltip v-else :delay="300">Click to change prompt set</q-tooltip>
        </div>
      </div>
    </div>

    <!-- Input Field -->
    <div class="input-container row items-end q-gutter-xs">
      <div class="col relative-position">
        <q-input
          ref="chatInputRef"
          :model-value="userInput"
          placeholder="Ask a question or describe what you want to do... (type @ to mention files)"
          outlined
          autogrow
          :max-height="120"
          class="chat-input"
          @keydown="onChatKeydown"
          @update:model-value="handleInput"
          :disable="!hasProject"
          :readonly="isLoading"
        >
          <template v-slot:append>
            <q-btn
              v-if="!isLoading"
              round
              dense
              flat
              icon="send"
              color="primary"
              @click="$emit('send-message')"
              :disable="!userInput.trim() || !hasProject"
              class="send-btn"
            >
              <q-tooltip :delay="300">Send message</q-tooltip>
            </q-btn>
          </template>
        </q-input>

        <!-- @ Mention Dropdown -->
        <div v-if="showMentionMenu && filteredMentions.length > 0" class="mention-dropdown">
          <div
            v-for="(file, index) in filteredMentions"
            :key="`${file.folderId}/${file.relativePath}`"
            class="mention-item"
            :class="{ 'mention-item-active': index === mentionSelectedIndex }"
            @click="handleInsertMention(file)"
            @mouseenter="$emit('update:mention-selected-index', index)"
          >
            <q-icon name="description" size="14px" color="grey-6" class="q-mr-xs" />
            <div class="mention-item-content">
              <div class="mention-item-name">{{ file.name }}</div>
              <div class="mention-item-path">
                <span class="mention-folder-badge">{{ getFolderName(file.folderId) }}</span>
                {{ file.relativePath }}
              </div>
            </div>
          </div>
        </div>
      </div>
      <q-btn
        v-if="isLoading"
        round
        dense
        flat
        icon="stop"
        color="negative"
        @click="$emit('stop-generation')"
        class="stop-btn"
      >
        <q-tooltip :delay="300">Stop generation</q-tooltip>
      </q-btn>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue';
import type { QInput } from 'quasar';
import { useMessageFormatting } from '../composables/useMessageFormatting';
import type { MentionFile } from '../composables/useMention';
import type { Mode } from '../../../../core/types';

interface ModelConfig {
  id: string;
  name: string;
  family: string;
}

interface ModeOption {
  label: string;
  value: Mode;
}

interface SetStatus {
  label: string;
  value: string;
  compatible: boolean;
  familyMatch: boolean;
  families: string[];
}

const emit = defineEmits<{
  'update:userInput': [value: string];
  'update:mention-selected-index': [index: number];
  'select-mode': [mode: string];
  'select-model': [modelId: string];
  'show-sets': [];
  'send-message': [];
  'stop-generation': [];
  keydown: [event: KeyboardEvent];
  input: [];
  'insert-mention': [file: MentionFile];
}>();

const props = defineProps<{
  userInput: string;
  isLoading: boolean;
  hasProject: boolean;
  showMentionMenu: boolean;
  filteredMentions: MentionFile[];
  mentionSelectedIndex: number;
  // Prompt sets props
  selectedMode: Mode;
  selectedModelId: string;
  currentModeLabel: string;
  modeOptions: ModeOption[];
  modelOptions: ModelConfig[];
  activeModel: ModelConfig | undefined;
  currentSetStatus: SetStatus | undefined;
}>();

// Create ref for template binding - this will be synced with parent via defineExpose
const chatInputRef = ref<InstanceType<typeof QInput> | null>(null);

// Expose the ref so parent can access it if needed
defineExpose({
  chatInputRef,
});

const { getFolderName } = useMessageFormatting();

function handleInsertMention(file: MentionFile) {
  emit('insert-mention', file);
}

function handleInput(value: string | number | null) {
  const stringValue = typeof value === 'string' ? value : (value?.toString() ?? '');
  emit('update:userInput', stringValue);
  emit('input');
}

function onChatKeydown(event: KeyboardEvent) {
  emit('keydown', event);
}
</script>

<style scoped>
.ai-input-area {
  flex-shrink: 0;
  background: #ffffff;
  border-top: 1px solid #e0e0e0;
  padding: 8px 12px 12px;
}

.input-toolbar {
  margin-bottom: 8px;
}

.mode-dropdown {
  border: 1px solid #e0e0e0;
  border-radius: 6px;
  background: #f8f9fa;
}

:deep(.mode-dropdown .q-btn__content) {
  font-size: 11px;
  padding: 0 4px;
  min-height: 26px;
  font-weight: 600;
}

.model-selector {
  font-size: 12px;
  min-width: 120px;
}

:deep(.model-selector .q-field__control) {
  min-height: 26px;
  padding: 0 8px;
}

.model-selector-selected {
  display: flex;
  flex-direction: column;
  line-height: 1.2;
}

.model-selector-name {
  font-size: 12px;
  font-weight: 500;
  color: #333333;
}

.model-selector-family {
  font-size: 10px;
  color: #9e9e9e;
  margin-top: 1px;
}

.model-option-family {
  color: #9e9e9e;
  font-size: 11px;
}

.input-container {
  position: relative;
}

.chat-input {
  background: #f8f9fa;
  border-radius: 12px;
}

:deep(.chat-input .q-field__control) {
  border-radius: 12px;
}

:deep(.chat-input .q-field__native) {
  font-size: 13px;
  line-height: 1.5;
  padding: 10px 12px;
}

:deep(.chat-input .q-field--outlined .q-field__control:before) {
  border-color: #e0e0e0;
}

:deep(.chat-input .q-field--outlined .q-field__control:hover:before) {
  border-color: #1976d2;
}

.send-btn,
.stop-btn {
  margin-right: 4px;
}

.active-set-indicator {
  border: 1px solid #e0e0e0;
  border-radius: 6px;
  background: #f8f9fa;
  padding: 4px 8px;
  min-height: 26px;
  height: auto;
  cursor: pointer;
  transition: all 0.2s ease;
}

.active-set-indicator:hover {
  border-color: #1976d2;
  background: #e3f2fd;
}

.active-set-indicator.set-error {
  border-color: #f44336;
  background: #ffebee;
}

.active-set-indicator.set-error:hover {
  border-color: #d32f2f;
  background: #ffcdd2;
}

.active-set-indicator.set-warning {
  border-color: #ff9800;
  background: #fff3e0;
}

.active-set-indicator.set-warning:hover {
  border-color: #f57c00;
  background: #ffe0b2;
}

.active-set-content {
  display: flex;
  flex-direction: column;
  line-height: 1.2;
  min-width: 0;
}

.active-set-name {
  font-size: 11px;
  font-weight: 600;
  color: #424242;
  max-width: 100px;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.active-set-families {
  font-size: 9px;
  color: #9e9e9e;
  margin-top: 1px;
  max-width: 100px;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.mention-dropdown {
  position: absolute;
  bottom: 100%;
  left: 0;
  right: 0;
  max-height: 250px;
  overflow-y: auto;
  background: #ffffff;
  border: 1px solid #e0e0e0;
  border-radius: 8px;
  box-shadow: 0 -4px 12px rgba(0, 0, 0, 0.1);
  margin-bottom: 4px;
  z-index: 100;
}

.mention-item {
  display: flex;
  align-items: center;
  padding: 8px 12px;
  cursor: pointer;
  transition: background-color 0.1s ease;
}

.mention-item:hover,
.mention-item-active {
  background: #f0f4f8;
}

.mention-item-content {
  flex: 1;
  min-width: 0;
}

.mention-item-name {
  font-size: 13px;
  font-weight: 500;
  color: #333333;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.mention-item-path {
  font-size: 11px;
  color: #9e9e9e;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  display: flex;
  align-items: center;
  gap: 6px;
}

.mention-folder-badge {
  display: inline-block;
  padding: 1px 6px;
  background: #e3f2fd;
  color: #1976d2;
  border-radius: 4px;
  font-size: 10px;
  font-weight: 500;
  flex-shrink: 0;
}
</style>
