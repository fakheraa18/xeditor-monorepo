<template>
  <q-scroll-area ref="scrollAreaRef" class="chat-messages-area" @scroll="handleScroll">
    <div class="messages-container">
      <template v-if="currentSession">
        <div v-for="turn in currentSession.turns" :key="turn.id" class="turn-container">
          <!-- Debug Inspect Button (only when debug mode is enabled) -->
          <div v-if="debugEnabled" class="turn-debug-actions">
            <q-btn
              flat
              dense
              round
              size="xs"
              icon="bug_report"
              color="orange"
              class="debug-inspect-btn"
              @click="$emit('debug-inspect', turn.id)"
            >
              <q-tooltip :delay="300"> Inspect debug info for this turn </q-tooltip>
            </q-btn>
          </div>
          <!-- User Message -->
          <MessageBubble
            :message="turn.userMessage"
            type="user"
            :editable="!pendingTurn"
            @edit-submit="(newText) => handleEditSubmit(turn.id, newText)"
          />

          <!-- System/Error Message (shown when turn has error) -->
          <MessageBubble
            v-if="turn.error"
            :message="turn.error"
            type="system"
            :error="turn.error"
          />

          <!-- Assistant Message (shown when turn has no error) -->
          <MessageBubble
            v-else
            :message="turn.assistantMessage"
            type="assistant"
            :trace-events="turn.traceEvents ?? undefined"
            :usage="turn.usage ?? undefined"
            :artifacts="turn.artifacts ?? undefined"
            :debug-enabled="debugEnabled"
            @debug-inspect-tool-call="$emit('debug-inspect-tool-call', $event)"
          />
        </div>

        <!-- Pending Turn -->
        <!-- Only show pendingTurn if it doesn't already exist in the session turns -->
        <div v-if="pendingTurn && !isPendingTurnDuplicate" class="turn-container">
          <MessageBubble :message="pendingTurn.userMessage" type="user" />

          <!-- System/Error Message for pending turn -->
          <MessageBubble
            v-if="pendingTurn.error"
            :message="pendingTurn.error"
            type="system"
            :error="pendingTurn.error"
          />

          <!-- Assistant Message for pending turn (when no error) -->
          <div v-else class="message message-assistant">
            <div class="message-bubble assistant-bubble" @click="handleMessageClick">
              <!-- Message Label -->
              <div class="message-label assistant-label">
                <q-icon name="smart_toy" size="12px" class="q-mr-xs" />
                <span>Assistant</span>
              </div>

              <!-- Unified Activity Timeline -->
              <ActivityTimeline
                ref="lastMessageContentRef"
                :trace-events="pendingTurn.traceEvents"
                :message-content="pendingTurn.assistantMessage"
                :current-activity="pendingTurn.currentActivity"
                :is-streaming="true"
                :debug-enabled="debugEnabled"
                @debug-inspect-tool-call="$emit('debug-inspect-tool-call', $event)"
              />
            </div>
          </div>
        </div>

        <!-- Question Form (for ask_question tool) -->
        <QuestionForm
          v-if="pendingQuestion"
          v-bind="pendingQuestion.title ? { title: pendingQuestion.title } : {}"
          :questions="pendingQuestion.questions"
          @submit="(answers) => $emit('submit-question', answers)"
          @skip="$emit('skip-question')"
        />

        <!-- Command Confirmation (for run_command tool) -->
        <CommandConfirmation
          v-if="pendingCommand"
          :command="pendingCommand.command"
          :id="pendingCommand.id"
          @allow="(id) => $emit('confirm-command', id)"
          @skip="$emit('skip-command')"
        />

        <!-- Scroll anchor - invisible element at the bottom for reliable scrolling -->
        <div ref="scrollAnchorRef" class="scroll-anchor"></div>
      </template>

      <!-- Loading State -->
      <div v-else-if="isLoadingSession" class="empty-state">
        <q-spinner-dots size="48px" color="primary" />
        <div class="empty-title">Loading chat...</div>
        <div class="empty-subtitle">Please wait while we load your conversation</div>
      </div>

      <!-- Empty State -->
      <div v-else class="empty-state">
        <q-icon name="chat_bubble_outline" size="48px" color="grey-4" />
        <div class="empty-title">Start a Conversation</div>
        <div class="empty-subtitle">Ask questions or give commands to the AI assistant</div>
      </div>
    </div>
  </q-scroll-area>
</template>

<script setup lang="ts">
import { computed, watch, nextTick, ref } from 'vue';
import { useChatStore } from '../../../../stores/chat';
import { useScroll } from '../composables/useScroll';
import { useMessageFormatting } from '../composables/useMessageFormatting';
import MessageBubble from './MessageBubble.vue';
import ActivityTimeline from './ActivityTimeline.vue';
import QuestionForm from './QuestionForm.vue';
import CommandConfirmation from './CommandConfirmation.vue';
import type { PendingTurn, PendingCommand } from '../composables/useChatInput';
import type { PendingQuestion } from '../types/questions';

type QScrollAreaScrollInfo = {
  verticalPosition: number;
  verticalSize: number;
  verticalContainerSize: number;
};

const props = defineProps<{
  pendingTurn: PendingTurn | null;
  pendingQuestion: PendingQuestion | null;
  pendingCommand: PendingCommand | null;
  debugEnabled: boolean;
  isLoadingSession?: boolean;
}>();

const emit = defineEmits<{
  'debug-inspect': [turnId: string];
  'debug-inspect-tool-call': [toolCallId: string];
  'submit-question': [answers: Record<string, string[]>];
  'skip-question': [];
  'confirm-command': [id: string];
  'skip-command': [];
  'edit-message': [turnId: string, newText: string];
}>();

function handleEditSubmit(turnId: string, newText: string) {
  emit('edit-message', turnId, newText);
}

const chatStore = useChatStore();
const { scrollAreaRef } = useScroll();
const { handleMessageClick } = useMessageFormatting();

const currentSession = computed(() => chatStore.currentSession);

// Check if pendingTurn is a duplicate of an existing turn in the session
const isPendingTurnDuplicate = computed(() => {
  if (!props.pendingTurn || !currentSession.value) {
    return false;
  }
  // Check if any turn in the session has the same user message as pendingTurn
  return currentSession.value.turns.some(
    (turn) => turn.userMessage === props.pendingTurn!.userMessage,
  );
});

const isPinnedToBottom = ref(true);
const isAutoScrolling = ref(false);
const scrollAnchorRef = ref<HTMLElement | null>(null);
const lastMessageContentRef = ref<HTMLElement | null>(null);

function isScrollInfo(value: unknown): value is QScrollAreaScrollInfo {
  if (typeof value !== 'object' || value === null) return false;
  return (
    'verticalPosition' in value &&
    'verticalSize' in value &&
    'verticalContainerSize' in value &&
    typeof (value as Record<string, unknown>).verticalPosition === 'number' &&
    typeof (value as Record<string, unknown>).verticalSize === 'number' &&
    typeof (value as Record<string, unknown>).verticalContainerSize === 'number'
  );
}

function handleScroll(payload: unknown) {
  if (isAutoScrolling.value) return;
  if (!isScrollInfo(payload)) return;

  // How far from bottom are we?
  // Use a more lenient threshold (50px) to prevent stopping auto-scroll too early
  const distanceToBottom =
    payload.verticalSize - (payload.verticalPosition + payload.verticalContainerSize);
  isPinnedToBottom.value = distanceToBottom <= 50;
}

function followToBottom() {
  if (!isPinnedToBottom.value) return;

  isAutoScrolling.value = true;
  void nextTick(() => {
    // Use requestAnimationFrame to wait for DOM updates and layout
    requestAnimationFrame(() => {
      requestAnimationFrame(() => {
        // Use scrollIntoView on the anchor element for reliable CSS-based scrolling
        const targetElement = scrollAnchorRef.value || lastMessageContentRef.value;
        if (targetElement) {
          targetElement.scrollIntoView({ behavior: 'instant', block: 'end' });
        }
        requestAnimationFrame(() => {
          // Retry once more to catch delayed layout changes from markdown rendering
          const retryElement = scrollAnchorRef.value || lastMessageContentRef.value;
          if (retryElement) {
            retryElement.scrollIntoView({ behavior: 'instant', block: 'end' });
          }
          isAutoScrolling.value = false;
        });
      });
    });
  });
}

// When a new streaming turn starts, assume user wants to follow it.
watch(
  () => props.pendingTurn,
  (turn, prevTurn) => {
    if (turn && !prevTurn) {
      isPinnedToBottom.value = true;
      followToBottom();
    }
  },
);

// Watch for streaming updates to auto-scroll
watch(
  () => props.pendingTurn?.assistantMessage,
  () => {
    // Always try to scroll during streaming if we're pinned to bottom
    // This ensures we keep following even if isPinnedToBottom temporarily becomes false
    if (isPinnedToBottom.value) {
      followToBottom();
    }
  },
);

// Watch for trace events changes to auto-scroll
watch(
  () => props.pendingTurn?.traceEvents?.length,
  () => {
    // Scroll when new trace events are added
    if (isPinnedToBottom.value) {
      followToBottom();
    }
  },
);

// Watch for new turns added to auto-scroll
watch(
  () => chatStore.currentSession?.turns.length,
  () => {
    if (isPinnedToBottom.value) {
      followToBottom();
    }
  },
);

// Watch for session changes (e.g., when loading a session) to scroll to bottom
watch(
  () => chatStore.currentSession?.id,
  () => {
    isPinnedToBottom.value = true;
    followToBottom();
  },
);
</script>

<style scoped>
.chat-messages-area {
  flex: 1;
  min-height: 0;
  width: 100%;
  background: #ffffff;
}

/* Hide horizontal scrollbar on q-scroll-area */
.chat-messages-area :deep(.q-scrollarea__container) {
  overflow-x: hidden !important;
  /* Prevent Chrome "scroll anchoring" from jumping the view during streaming DOM updates */
  overflow-anchor: none;
}

.chat-messages-area :deep(.q-scrollarea__content) {
  width: 100% !important;
  max-width: 100% !important;
}

.messages-container {
  padding: 12px;
  width: 100%;
  box-sizing: border-box;
  overflow-anchor: none;
}

.scroll-anchor {
  height: 1px;
  width: 100%;
  flex-shrink: 0;
  /* Ensure anchor is always at the bottom for reliable scrolling */
}

.turn-container {
  margin-bottom: 16px;
  width: 100%;
  box-sizing: border-box;
}

.loading-indicator {
  display: flex;
  align-items: center;
  gap: 8px;
  color: #757575;
  font-size: 13px;
}

.empty-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 60px 20px;
  text-align: center;
}

.empty-title {
  font-size: 16px;
  font-weight: 500;
  color: #424242;
  margin-top: 16px;
}

.empty-subtitle {
  font-size: 13px;
  color: #9e9e9e;
  margin-top: 4px;
}

.turn-debug-actions {
  display: flex;
  justify-content: flex-end;
  padding: 4px 8px 0 8px;
}

.debug-inspect-btn {
  opacity: 0.6;
  transition: opacity 0.2s ease;
}

.debug-inspect-btn:hover {
  opacity: 1;
}

.turn-container:hover .debug-inspect-btn {
  opacity: 0.8;
}

.message {
  display: block;
  margin-bottom: 16px;
  width: 100%;
  box-sizing: border-box;
}

.message-label {
  display: flex;
  align-items: center;
  font-size: 11px;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.5px;
  margin-bottom: 6px;
}

.assistant-label {
  color: #7b1fa2;
}

.message-bubble {
  width: 100%;
  box-sizing: border-box;
  overflow-wrap: break-word;
  word-wrap: break-word;
}

.assistant-bubble {
  background: #fafafa;
  border-left: 3px solid #7b1fa2;
  border-radius: 0 8px 8px 0;
  padding: 12px 14px;
}

.message-content {
  color: #333333;
  line-height: 1.6;
  font-size: 13px;
  word-break: break-word;
  overflow-wrap: break-word;
}

/* Inline code */
.message-content :deep(code) {
  font-family: 'JetBrains Mono', 'Fira Code', Consolas, monospace;
  font-size: 12px;
  padding: 2px 6px;
  border-radius: 4px;
  background: #f0f4f8;
  color: #d63384;
  word-break: break-all;
}

/* Code blocks */
.message-content :deep(pre) {
  background: #1e1e1e;
  border-radius: 8px;
  padding: 12px 16px;
  margin: 12px 0;
  overflow-x: auto;
  position: relative;
}

.message-content :deep(pre code) {
  background: transparent;
  color: #d4d4d4;
  padding: 0;
  font-size: 12px;
  line-height: 1.5;
  display: block;
  white-space: pre;
  word-break: normal;
}

/* Syntax highlighting overrides for dark code blocks */
.message-content :deep(pre code .hljs-keyword) {
  color: #569cd6;
}

.message-content :deep(pre code .hljs-string) {
  color: #ce9178;
}

.message-content :deep(pre code .hljs-comment) {
  color: #6a9955;
}

.message-content :deep(pre code .hljs-function) {
  color: #dcdcaa;
}

.message-content :deep(pre code .hljs-number) {
  color: #b5cea8;
}

.message-content :deep(pre code .hljs-class) {
  color: #4ec9b0;
}

.message-content :deep(pre code .hljs-variable) {
  color: #9cdcfe;
}

.message-content :deep(pre code .hljs-attr) {
  color: #9cdcfe;
}

.message-content :deep(pre code .hljs-built_in) {
  color: #4ec9b0;
}

.message-content :deep(pre code .hljs-title) {
  color: #dcdcaa;
}

.message-content :deep(pre code .hljs-params) {
  color: #9cdcfe;
}

/* Strong/Bold */
.message-content :deep(strong) {
  font-weight: 600;
  color: #1a1a1a;
}

/* Emphasis/Italic */
.message-content :deep(em) {
  font-style: italic;
}

/* Headers */
.message-content :deep(h1) {
  font-size: 1.25em !important;
  font-weight: 600 !important;
  line-height: 1.4 !important;
  margin: 10px 0 6px 0 !important;
  padding-bottom: 3px !important;
  border-bottom: 1px solid #e8e8e8;
  color: #1a1a1a;
}

.message-content :deep(h2) {
  font-size: 1.15em !important;
  font-weight: 600 !important;
  line-height: 1.4 !important;
  margin: 8px 0 4px 0 !important;
  color: #1a1a1a;
}

.message-content :deep(h3) {
  font-size: 1.1em !important;
  font-weight: 600 !important;
  line-height: 1.4 !important;
  margin: 6px 0 4px 0 !important;
  color: #1a1a1a;
}

.message-content :deep(h4),
.message-content :deep(h5),
.message-content :deep(h6) {
  font-size: 1.05em !important;
  font-weight: 600 !important;
  line-height: 1.4 !important;
  margin: 6px 0 3px 0 !important;
  color: #333;
}

/* Paragraphs */
.message-content :deep(p) {
  margin: 8px 0;
}

.message-content :deep(p:first-child) {
  margin-top: 0;
}

.message-content :deep(p:last-child) {
  margin-bottom: 0;
}

/* Lists */
.message-content :deep(ul),
.message-content :deep(ol) {
  margin: 8px 0;
  padding-left: 24px;
}

.message-content :deep(li) {
  margin: 4px 0;
}

.message-content :deep(li > ul),
.message-content :deep(li > ol) {
  margin: 4px 0;
}

/* Blockquotes */
.message-content :deep(blockquote) {
  margin: 12px 0;
  padding: 8px 16px;
  border-left: 4px solid #7b1fa2;
  background: #faf5fc;
  color: #555;
  font-style: italic;
}

.message-content :deep(blockquote p) {
  margin: 0;
}

/* Tables */
.message-content :deep(table) {
  border-collapse: collapse;
  margin: 12px 0;
  overflow-x: auto;
  display: block;
}

.message-content :deep(th),
.message-content :deep(td) {
  border: 1px solid #e0e0e0;
  padding: 8px 12px;
  text-align: left;
}

.message-content :deep(th) {
  background: #f5f5f5;
  font-weight: 600;
}

.message-content :deep(tr:nth-child(even)) {
  background: #fafafa;
}

/* Links */
.message-content :deep(a) {
  color: #1976d2;
  text-decoration: none;
}

.message-content :deep(a:hover) {
  text-decoration: underline;
}

/* Horizontal rule */
.message-content :deep(hr) {
  border: none;
  border-top: 1px solid #e0e0e0;
  margin: 16px 0;
}

/* Images */
.message-content :deep(img) {
  max-width: 100%;
  height: auto;
  border-radius: 4px;
  margin: 8px 0;
}

/* Code Block Wrapper with Header */
.message-content :deep(.code-block-wrapper) {
  margin: 12px 0;
  border-radius: 8px;
  overflow: hidden;
  background: #1e1e1e;
  border: 1px solid #333;
}

.message-content :deep(.code-block-wrapper.is-streaming) {
  border-color: #7b1fa2;
}

.message-content :deep(.code-block-header) {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 6px 12px;
  background: #2d2d2d;
  border-bottom: 1px solid #333;
}

.message-content :deep(.code-language) {
  font-size: 11px;
  font-weight: 500;
  color: #888;
  text-transform: uppercase;
  letter-spacing: 0.5px;
}

.message-content :deep(.code-copy-btn) {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 24px;
  height: 24px;
  padding: 0;
  border: none;
  background: transparent;
  color: #888;
  cursor: pointer;
  border-radius: 4px;
  transition: all 0.2s ease;
}

.message-content :deep(.code-copy-btn:hover) {
  background: rgba(255, 255, 255, 0.1);
  color: #fff;
}

.message-content :deep(.code-copy-btn:active) {
  background: rgba(255, 255, 255, 0.2);
}

.message-content :deep(.code-block-wrapper pre) {
  margin: 0;
  border-radius: 0;
  border: none;
}
</style>
