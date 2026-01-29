<template>
  <div class="inline-editor">
    <div class="inline-editor-container relative-position">
      <q-input
        ref="editorInputRef"
        v-model="editText"
        outlined
        autogrow
        :max-height="200"
        class="inline-editor-input"
        placeholder="Edit your message..."
        @keydown="onKeydown"
        @update:model-value="onInput"
      />

      <!-- @ Mention Dropdown -->
      <div v-if="showMentionMenu && filteredMentions.length > 0" class="mention-dropdown">
        <div
          v-for="(file, index) in filteredMentions"
          :key="`${file.folderId}/${file.relativePath}`"
          class="mention-item"
          :class="{ 'mention-item-active': index === mentionSelectedIndex }"
          @click="handleInsertMention(file)"
          @mouseenter="mentionSelectedIndex = index"
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

    <div class="inline-editor-actions row items-center q-gutter-xs q-mt-xs">
      <q-btn
        flat
        dense
        size="sm"
        color="primary"
        icon="send"
        label="Send"
        :disable="!editText.trim()"
        @click="handleSubmit"
      />
      <q-btn
        flat
        dense
        size="sm"
        color="grey"
        icon="close"
        label="Cancel"
        @click="handleCancel"
      />
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, nextTick, computed, watch } from 'vue';
import type { QInput } from 'quasar';
import Fuse from 'fuse.js';
import { useProjectStore } from '../../../../stores/project';
import { useLocalCompanionStore } from '../../../../stores/localCompanion';
import { useMessageFormatting } from '../composables/useMessageFormatting';

interface MentionFile {
  folderId: string;
  relativePath: string;
  name: string;
}

const props = defineProps<{
  initialText: string;
}>();

const emit = defineEmits<{
  submit: [text: string];
  cancel: [];
}>();

const projectStore = useProjectStore();
const companionStore = useLocalCompanionStore();
const { getFolderName } = useMessageFormatting();

const editorInputRef = ref<InstanceType<typeof QInput> | null>(null);
const editText = ref(props.initialText);

// Mention state
const mentionFiles = ref<MentionFile[]>([]);
const showMentionMenu = ref(false);
const mentionQuery = ref('');
const mentionSelectedIndex = ref(0);
const mentionStartPos = ref(0);

// Fuzzy search for mentions
const mentionFuse = computed(() => {
  return new Fuse(mentionFiles.value, {
    keys: ['name', 'relativePath'],
    threshold: 0.4,
    includeMatches: true,
    shouldSort: true,
  });
});

const filteredMentions = computed(() => {
  if (!mentionQuery.value) {
    return mentionFiles.value.slice(0, 10);
  }
  return mentionFuse.value
    .search(mentionQuery.value)
    .slice(0, 10)
    .map((r) => r.item);
});

async function fetchMentionFiles() {
  const projectId = projectStore.activeProjectId;
  if (!projectId || !companionStore.isConnected) {
    mentionFiles.value = [];
    return;
  }

  try {
    const response = await companionStore.request<{
      success: boolean;
      files?: MentionFile[];
      error?: string;
    }>('index_list_files', { projectId });

    if (response.success && response.files) {
      mentionFiles.value = response.files;
    } else {
      mentionFiles.value = [];
    }
  } catch {
    mentionFiles.value = [];
  }
}

function detectMention(userInput: string): { active: boolean; query: string; startPos: number } {
  let cursorPos = userInput.length;
  try {
    const inputEl = editorInputRef.value?.$el?.querySelector('textarea') as HTMLTextAreaElement | null;
    if (inputEl) {
      cursorPos = inputEl.selectionStart ?? userInput.length;
    }
  } catch {
    cursorPos = userInput.length;
  }

  let startPos = -1;
  for (let i = cursorPos - 1; i >= 0; i--) {
    const char = userInput[i];
    if (char === '@') {
      if (i === 0 || /\s/.test(userInput[i - 1] ?? '')) {
        startPos = i;
        break;
      }
    }
    if (char && /\s/.test(char)) {
      break;
    }
  }

  if (startPos === -1) {
    return { active: false, query: '', startPos: 0 };
  }

  const query = userInput.substring(startPos + 1, cursorPos);
  return { active: true, query, startPos };
}

function updateMentionState(userInput: string) {
  const result = detectMention(userInput);
  if (result.active) {
    mentionQuery.value = result.query;
    mentionStartPos.value = result.startPos;
    showMentionMenu.value = true;
    mentionSelectedIndex.value = 0;
  } else {
    showMentionMenu.value = false;
    mentionQuery.value = '';
  }
}

function insertMention(file: MentionFile): void {
  const startPos = mentionStartPos.value;
  const userInput = editText.value;

  let cursorPos = userInput.length;
  try {
    const inputEl = editorInputRef.value?.$el?.querySelector('textarea') as HTMLTextAreaElement | null;
    if (inputEl) {
      cursorPos = inputEl.selectionStart ?? userInput.length;
    }
  } catch {
    cursorPos = userInput.length;
  }

  const folderName = getFolderName(file.folderId);
  const fullPath = `${folderName}/${file.relativePath}`;
  const before = userInput.substring(0, startPos);
  const after = userInput.substring(cursorPos);
  editText.value = `${before}@${fullPath} ${after}`;

  showMentionMenu.value = false;
  mentionQuery.value = '';

  void nextTick(() => {
    const newPos = startPos + fullPath.length + 2;
    try {
      const inputEl = editorInputRef.value?.$el?.querySelector('textarea') as HTMLTextAreaElement | null;
      if (inputEl) {
        inputEl.setSelectionRange(newPos, newPos);
        inputEl.focus();
      }
    } catch {
      // Ignore
    }
  });
}

function handleInsertMention(file: MentionFile) {
  insertMention(file);
}

function onInput() {
  updateMentionState(editText.value);
}

function onKeydown(event: KeyboardEvent) {
  if (showMentionMenu.value && filteredMentions.value.length > 0) {
    if (event.key === 'ArrowDown') {
      event.preventDefault();
      mentionSelectedIndex.value = (mentionSelectedIndex.value + 1) % filteredMentions.value.length;
      return;
    }
    if (event.key === 'ArrowUp') {
      event.preventDefault();
      mentionSelectedIndex.value =
        (mentionSelectedIndex.value - 1 + filteredMentions.value.length) % filteredMentions.value.length;
      return;
    }
    if (event.key === 'Enter' || event.key === 'Tab') {
      event.preventDefault();
      const selected = filteredMentions.value[mentionSelectedIndex.value];
      if (selected) {
        insertMention(selected);
      }
      return;
    }
    if (event.key === 'Escape') {
      event.preventDefault();
      showMentionMenu.value = false;
      return;
    }
  }

  // Submit on Enter (without shift)
  if (event.key === 'Enter' && !event.shiftKey && !showMentionMenu.value) {
    event.preventDefault();
    handleSubmit();
  }

  // Cancel on Escape
  if (event.key === 'Escape' && !showMentionMenu.value) {
    event.preventDefault();
    handleCancel();
  }
}

function handleSubmit() {
  if (editText.value.trim()) {
    emit('submit', editText.value.trim());
  }
}

function handleCancel() {
  emit('cancel');
}

// Watch for changes to editText to detect mentions
watch(() => editText.value, () => {
  updateMentionState(editText.value);
});

onMounted(async () => {
  await fetchMentionFiles();
  // Focus and select all text
  await nextTick();
  const inputEl = editorInputRef.value?.$el?.querySelector('textarea') as HTMLTextAreaElement | null;
  if (inputEl) {
    inputEl.focus();
    inputEl.select();
  }
});
</script>

<style scoped>
.inline-editor {
  width: 100%;
}

.inline-editor-container {
  position: relative;
}

.inline-editor-input {
  background: #ffffff;
  border-radius: 8px;
}

:deep(.inline-editor-input .q-field__control) {
  border-radius: 8px;
}

:deep(.inline-editor-input .q-field__native) {
  font-size: 13px;
  line-height: 1.5;
  padding: 8px 10px;
}

:deep(.inline-editor-input .q-field--outlined .q-field__control:before) {
  border-color: #1976d2;
}

.inline-editor-actions {
  justify-content: flex-end;
}

.mention-dropdown {
  position: absolute;
  bottom: 100%;
  left: 0;
  right: 0;
  max-height: 200px;
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
