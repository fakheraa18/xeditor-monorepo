import { ref, computed, watch, nextTick, type Ref } from 'vue';
import type { QInput } from 'quasar';
import Fuse from 'fuse.js';
import { useProjectStore } from '../../../../stores/project';
import { useLocalCompanionStore } from '../../../../../../stores/localCompanion';
import { useIndexingStore } from '../../../../stores/indexing';
import { useMessageFormatting } from './useMessageFormatting';

export interface MentionFile {
  folderId: string;
  relativePath: string;
  name: string;
}

export function useMention(chatInputRef: Ref<InstanceType<typeof QInput> | null>) {
  const projectStore = useProjectStore();
  const indexingStore = useIndexingStore();
  const { getFolderName } = useMessageFormatting();

  const mentionFiles = ref<MentionFile[]>([]);
  const showMentionMenu = ref(false);
  const mentionQuery = ref('');
  const mentionSelectedIndex = ref(0);
  const mentionStartPos = ref(0);

  // @ mention fuzzy search
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
    if (!projectId) {
      console.log('[Mention] No project ID');
      mentionFiles.value = [];
      return;
    }

    const companionStore = useLocalCompanionStore();
    if (!companionStore.isConnected) {
      console.log('[Mention] Companion not connected');
      mentionFiles.value = [];
      return;
    }

    try {
      console.log('[Mention] Fetching files for project:', projectId);
      const response = await companionStore.request<{
        success: boolean;
        files?: MentionFile[];
        error?: string;
      }>('index_list_files', { projectId });

      if (response.success && response.files) {
        console.log('[Mention] Fetched', response.files.length, 'files');
        mentionFiles.value = response.files;
      } else {
        console.warn('[Mention] No files in response:', response);
        mentionFiles.value = [];
      }
    } catch (error) {
      console.warn('[Mention] Failed to fetch mention files:', error);
      mentionFiles.value = [];
    }
  }

  function detectMention(userInput: string): { active: boolean; query: string; startPos: number } {
    // Try to get cursor position from the input element
    let cursorPos = userInput.length;
    try {
      // For Quasar q-input with autogrow, the textarea is nested
      const inputEl = chatInputRef.value?.$el?.querySelector(
        'textarea',
      ) as HTMLTextAreaElement | null;
      if (inputEl) {
        cursorPos = inputEl.selectionStart ?? userInput.length;
      }
    } catch (_e) {
      // Fallback to end of string
      cursorPos = userInput.length;
    }

    // Look backwards from cursor for @
    let startPos = -1;
    for (let i = cursorPos - 1; i >= 0; i--) {
      const char = userInput[i];
      if (char === '@') {
        // Check if @ is at start or preceded by whitespace
        if (i === 0 || /\s/.test(userInput[i - 1] ?? '')) {
          startPos = i;
          break;
        }
      }
      // Stop if we hit whitespace before finding @
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
      // Debug logging
      console.log('[Mention] Active:', {
        query: result.query,
        files: mentionFiles.value.length,
        filtered: filteredMentions.value.length,
      });
    } else {
      showMentionMenu.value = false;
      mentionQuery.value = '';
    }
  }

  function insertMention(file: MentionFile, userInput: string): string {
    const startPos = mentionStartPos.value;

    // Try to get cursor position from the input element
    let cursorPos = userInput.length;
    try {
      const inputEl = chatInputRef.value?.$el?.querySelector(
        'textarea',
      ) as HTMLTextAreaElement | null;
      if (inputEl) {
        cursorPos = inputEl.selectionStart ?? userInput.length;
      }
    } catch (_e) {
      cursorPos = userInput.length;
    }

    // Insert @folderName/relativePath (user-friendly, shows folder name instead of ID)
    const folderName = getFolderName(file.folderId);
    const fullPath = `${folderName}/${file.relativePath}`;
    const before = userInput.substring(0, startPos);
    const after = userInput.substring(cursorPos);
    const newInput = `${before}@${fullPath} ${after}`;

    // Close menu
    showMentionMenu.value = false;
    mentionQuery.value = '';

    // Focus back to input and set cursor position
    void nextTick(() => {
      const newPos = startPos + fullPath.length + 2; // +2 for @ and space
      try {
        const inputEl = chatInputRef.value?.$el?.querySelector(
          'textarea',
        ) as HTMLTextAreaElement | null;
        if (inputEl) {
          inputEl.setSelectionRange(newPos, newPos);
          inputEl.focus();
        }
      } catch (_e) {
        // Ignore if we can't set cursor position
      }
    });

    return newInput;
  }

  // Watch for project changes to refresh mention files
  watch(
    () => projectStore.activeProjectId,
    () => {
      void fetchMentionFiles();
    },
  );

  // Watch for indexing completion to refresh mention files
  watch(
    () => indexingStore.progress?.phase,
    (phase) => {
      if (phase === 'complete') {
        void fetchMentionFiles();
      }
    },
  );

  return {
    mentionFiles,
    showMentionMenu,
    mentionQuery,
    mentionSelectedIndex,
    mentionStartPos,
    filteredMentions,
    fetchMentionFiles,
    detectMention,
    updateMentionState,
    insertMention,
  };
}
