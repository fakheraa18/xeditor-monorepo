<template>
  <div class="ai-panel column no-wrap fit">
    <!-- Panel Header -->
    <AIPanelHeader
      :show-history-view="viewState.showHistoryView.value"
      :show-sets-view="viewState.showSetsView.value"
      :has-project="hasProject"
      @toggle-history="viewState.toggleHistory"
      @toggle-sets="viewState.toggleSets"
      @new-chat="handleNewChat"
    />

    <!-- Session Stats (shown when in chat view with stats) -->
    <SessionStats
      v-if="viewState.isChatView.value && sessionTokenStats.totalTokens > 0"
      :stats="sessionTokenStats"
      :context-usage="lastTurnContextUsage"
    />

    <!-- Warning Banner -->
    <div v-if="!hasProject" class="warning-banner row items-center justify-center">
      <q-icon name="warning" size="16px" class="q-mr-xs" />
      <span>Please open a folder first</span>
    </div>

    <!-- Sets View -->
    <SetsView
      v-if="viewState.showSetsView.value"
      :selected-set-id="promptSets.selectedSetId.value"
      :current-mode-label="promptSets.currentModeLabel.value"
      :active-model="promptSets.activeModel.value"
      :filtered-set-options="promptSets.filteredSetOptions.value"
      :get-set-tools-by-mode="promptSets.getSetToolsByMode"
      :get-set-total-tool-count="promptSets.getSetTotalToolCount"
      @select-set="handleSetSelect"
    />

    <!-- History View -->
    <HistoryView
      v-else-if="viewState.showHistoryView.value"
      :is-loading-session="chatHistory.isLoadingSession.value"
      :is-history-view-visible="viewState.showHistoryView.value"
      @load-session="handleLoadSession"
      @rename-session="handleRenameSession"
      @delete-session="handleDeleteSession"
    />

    <!-- Chat Messages -->
    <ChatMessages
      v-else
      :pending-turn="chatInput.pendingTurn.value"
      :pending-question="chatInput.pendingQuestion.value"
      :pending-command="chatInput.pendingCommand.value"
      :debug-enabled="debugEnabled"
      :is-loading-session="chatHistory.isLoadingSession.value"
      @debug-inspect="openDebugDialog"
      @debug-inspect-tool-call="openToolCallDebugDialog"
      @submit-question="handleSubmitQuestion"
      @skip-question="handleSkipQuestion"
      @confirm-command="handleConfirmCommand"
      @skip-command="handleSkipCommand"
      @edit-message="handleEditMessage"
    />

    <!-- Input Area (hidden in history/sets view) -->
    <ChatInput
      v-if="viewState.isChatView.value"
      ref="chatInputComponentRef"
      v-model:user-input="chatInput.userInput.value"
      :is-loading="chatInput.isLoading.value"
      :has-project="hasProject"
      :show-mention-menu="chatInput.mention.showMentionMenu.value"
      :filtered-mentions="chatInput.mention.filteredMentions.value"
      v-model:mention-selected-index="chatInput.mention.mentionSelectedIndex.value"
      :selected-mode="promptSets.selectedMode.value"
      :selected-model-id="promptSets.selectedModelId.value"
      :current-mode-label="promptSets.currentModeLabel.value"
      :mode-options="promptSets.modeOptions.value"
      :model-options="promptSets.modelOptions.value"
      :active-model="promptSets.activeModel.value"
      :current-set-status="promptSets.currentSetStatus.value"
      @select-mode="promptSets.handleModeChange"
      @select-model="promptSets.handleModelChange"
      @show-sets="viewState.showSets"
      @send-message="chatInput.sendMessage"
      @stop-generation="chatInput.stopGeneration"
      @keydown="chatInput.onChatKeydown"
      @input="handleChatInput"
      @insert-mention="handleInsertMention"
    />

    <!-- Debug Turn Dialog -->
    <DebugTurnDialog
      v-model="showDebugDialog"
      :project-id="projectStore.activeProjectId || ''"
      :chat-id="chatStore.currentSession?.id || ''"
      :turn-id="debugTurnId"
    />

    <!-- Debug Tool Call Dialog -->
    <DebugToolCallDialog
      v-model="showToolCallDebugDialog"
      :tool-call="debugToolCall"
      :tool-result="debugToolResult"
      :all-trace-events="debugToolCallTraceEvents"
      :is-streaming="chatInput.isLoading.value"
      @inspect-nested-tool="openToolCallDebugDialog"
    />
  </div>
</template>

<script setup lang="ts">
import { ref, computed, watch, onMounted, type Ref } from 'vue';
import { storeToRefs } from 'pinia';
import type { QInput } from 'quasar';
import { useQuasar } from 'quasar';
import { useProjectStore } from '../../../stores/project';
import { useChatStore } from '../../../stores/chat';
import { useAiConfigStore } from '../../../stores/aiConfig';
import DebugTurnDialog from '../DebugTurnDialog.vue';
import DebugToolCallDialog from '../DebugToolCallDialog.vue';
import AIPanelHeader from './components/AIPanelHeader.vue';
import SetsView from './components/SetsView.vue';
import HistoryView from './components/HistoryView.vue';
import ChatMessages from './components/ChatMessages.vue';
import ChatInput from './components/ChatInput.vue';
import SessionStats from './components/SessionStats.vue';
import { useViewState } from './composables/useViewState';
import { usePromptSets } from './composables/usePromptSets';
import { useChatInput } from './composables/useChatInput';
import { useChatHistory } from './composables/useChatHistory';
import type { TraceEvent, TraceEventToolCall, TraceEventToolResult } from '../../../core/types';

const projectStore = useProjectStore();
const chatStore = useChatStore();
const aiConfig = useAiConfigStore();
const $q = useQuasar();

const { debugEnabled } = storeToRefs(aiConfig);
const { sessionTokenStats, lastTurnContextUsage } = storeToRefs(chatStore);

const hasProject = computed(() => projectStore.hasConnectedFolders);

// View state management
const viewState = useViewState();

// Prompt sets management
const promptSets = usePromptSets();

// Chat history management
const chatHistory = useChatHistory();

// Chat input management
const chatInputRef = ref<InstanceType<typeof QInput> | null>(null);
const chatInputComponentRef = ref<InstanceType<typeof ChatInput> | null>(null);
const chatInput = useChatInput(chatInputRef);

// Sync ref from ChatInput component to our ref for composables after mount
watch(
  chatInputComponentRef,
  (component) => {
    if (component) {
      // Access the exposed ref - TypeScript doesn't know it's a Ref, so we assert it
      const exposedRef = (
        component as unknown as { chatInputRef: Ref<InstanceType<typeof QInput> | null> }
      ).chatInputRef;
      if (exposedRef) {
        // Watch the exposed ref's value and sync to our ref
        watch(
          () => exposedRef.value,
          (value) => {
            chatInputRef.value = value;
          },
          { immediate: true },
        );
      }
    }
  },
  { immediate: true },
);

// Debug dialog state
const showDebugDialog = ref(false);
const debugTurnId = ref('');

// Tool call debug dialog state
const showToolCallDebugDialog = ref(false);
const debugToolCall = ref<TraceEventToolCall | null>(null);
const debugToolResult = ref<TraceEventToolResult | null>(null);
const debugToolCallTraceEvents = ref<TraceEvent[]>([]);

function handleNewChat() {
  // Switch to chat view and clear current session
  // Session will be created lazily when user sends a message
  viewState.showChat();
  chatStore.clearCurrentSession();
}

function openDebugDialog(turnId: string) {
  debugTurnId.value = turnId;
  showDebugDialog.value = true;
}

function openToolCallDebugDialog(toolCallId: string) {
  // Search for tool call in current session turns
  const session = chatStore.currentSession;
  let toolCall: TraceEventToolCall | null = null;
  let toolResult: TraceEventToolResult | null = null;
  let allTraceEvents: typeof debugToolCallTraceEvents.value = [];

  if (session) {
    // Search through all turns
    for (const turn of session.turns) {
      if (turn.traceEvents) {
        for (const event of turn.traceEvents) {
          if (event.type === 'tool_call' && event.id === toolCallId) {
            toolCall = event;
            allTraceEvents = turn.traceEvents || [];
          }
          if (event.type === 'tool_result' && event.toolCallId === toolCallId) {
            toolResult = event;
          }
        }
      }
    }
  }

  // Also check pending turn if not found
  if (!toolCall && chatInput.pendingTurn.value?.traceEvents) {
    for (const event of chatInput.pendingTurn.value.traceEvents) {
      if (event.type === 'tool_call' && event.id === toolCallId) {
        toolCall = event;
        allTraceEvents = chatInput.pendingTurn.value.traceEvents;
      }
      if (event.type === 'tool_result' && event.toolCallId === toolCallId) {
        toolResult = event;
      }
    }
  }

  if (toolCall) {
    debugToolCall.value = toolCall;
    debugToolResult.value = toolResult;
    debugToolCallTraceEvents.value = allTraceEvents;
    showToolCallDebugDialog.value = true;
  }
}

async function handleLoadSession(sessionId: string) {
  // Ensure we're in history view to show the loader
  if (!viewState.showHistoryView.value) {
    viewState.showHistory();
  }
  // Load the session (this will show loading state in history view)
  await chatHistory.handleLoadSession(sessionId);
  // Switch to chat view after loading completes
  viewState.showChat();
}

async function handleRenameSession(sessionId: string) {
  await chatHistory.handleRenameSession(sessionId);
}

async function handleDeleteSession(sessionId: string) {
  await chatHistory.handleDeleteSession(sessionId);
}

function handleSetSelect(setId: string) {
  promptSets.handleSetSelect(setId);
  viewState.showChat();
}

function handleChatInput() {
  chatInput.onChatInput();
}

function handleInsertMention(file: { folderId: string; relativePath: string; name: string }) {
  chatInput.userInput.value = chatInput.mention.insertMention(file, chatInput.userInput.value);
}

function handleSubmitQuestion(answers: Record<string, string[]>) {
  void chatInput.submitQuestionAnswers(answers);
}

function handleSkipQuestion() {
  chatInput.skipQuestion();
}

function handleConfirmCommand(id: string) {
  void chatInput.confirmCommand(id);
}

function handleSkipCommand() {
  chatInput.skipCommand();
}

function handleEditMessage(turnId: string, newText: string) {
  // Find how many messages will be lost
  const session = chatStore.currentSession;
  if (!session) return;

  const turnIndex = session.turns.findIndex((t) => t.id === turnId);
  if (turnIndex === -1) return;

  const turnsToRemove = session.turns.length - turnIndex;

  // Show confirmation dialog
  $q.dialog({
    title: 'Edit Message',
    message:
      turnsToRemove > 1
        ? `This will remove ${turnsToRemove} message(s) from this point onwards. Continue?`
        : 'This will regenerate the response for this message. Continue?',
    cancel: true,
    persistent: true,
  }).onOk(() => {
    void (async () => {
      try {
        // Truncate the chat from this turn onwards
        await chatStore.truncateFromTurn(turnId);

        // Set the edited text as user input and send
        chatInput.userInput.value = newText;
        await chatInput.sendMessage();
      } catch (error) {
        console.error('Failed to edit message:', error);
        $q.notify({
          type: 'negative',
          message: 'Failed to edit message',
          caption: error instanceof Error ? error.message : 'Unknown error',
          position: 'top',
          timeout: 3000,
        });
      }
    })();
  });
}

// Watch for view state changes and persist to localStorage
watch(
  () => viewState.currentView.value,
  (newView) => {
    localStorage.setItem('xeditor-ai-panel-view', newView);
  },
);

// Reload sessions when history view opens (only if not already loading)
watch(
  () => viewState.showHistoryView.value,
  async (isShowing) => {
    if (isShowing && projectStore.activeProjectId && !chatStore.isLoading) {
      // Reload sessions to show fresh data and loading state
      await chatStore.initialize(projectStore.activeProjectId);
    }
  },
);

// Initialize AI config and chat store on mount
onMounted(async () => {
  await aiConfig.initialize();
  promptSets.selectedMode.value = aiConfig.activeMode;
  promptSets.selectedModelId.value = aiConfig.activeModelId;
  promptSets.selectedSetId.value = aiConfig.activeSetId;

  // Initialize chat store for current project
  await chatStore.initialize(projectStore.activeProjectId);

  // Restore view state
  const storedView = localStorage.getItem('xeditor-ai-panel-view');
  if (storedView === 'history') {
    viewState.showHistory();
  } else if (storedView === 'sets') {
    viewState.showSets();
  } else {
    viewState.showChat();
  }

  // Load tools after initialization (with a small delay to ensure companion is ready)
  setTimeout(() => {
    void promptSets.loadAllSetTools();
  }, 500);

  // Load mention files for @ autocomplete
  setTimeout(() => {
    void chatInput.mention.fetchMentionFiles();
  }, 600);
});
</script>

<style scoped>
.ai-panel {
  background: #fafafa;
  color: #333333;
  height: 100%;
  width: 100%;
  display: flex;
  flex-direction: column;
  overflow: hidden;
  box-sizing: border-box;
}

/* Warning Banner */
.warning-banner {
  padding: 6px 12px;
  background: #fff3e0;
  border-bottom: 1px solid #ffe0b2;
  color: #e65100;
  font-size: 12px;
  flex-shrink: 0;
}

/* Scrollbar styling */
:deep(.q-scrollarea__thumb) {
  background: rgba(0, 0, 0, 0.15);
  border-radius: 4px;
  width: 6px;
}

:deep(.q-scrollarea__thumb:hover) {
  background: rgba(0, 0, 0, 0.25);
}

/* File Mention Chip in Messages */
:deep(.file-mention-chip) {
  display: inline-flex;
  align-items: center;
  padding: 2px 8px;
  margin: 0 2px;
  background: #e3f2fd;
  border: 1px solid #90caf9;
  border-radius: 12px;
  font-size: 12px;
  font-weight: 500;
  color: #1976d2;
  cursor: pointer;
  transition: all 0.15s ease;
  vertical-align: middle;
}

:deep(.file-mention-chip:hover) {
  background: #bbdefb;
  border-color: #64b5f6;
}

:deep(.file-mention-chip::before) {
  content: '📄';
  margin-right: 4px;
  font-size: 11px;
}
</style>
