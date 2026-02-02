<template>
  <!-- Hide command approved/skipped messages entirely -->
  <div v-if="!isHiddenCommandMessage" class="message" :class="`message-${type}`">
    <div
      class="message-bubble"
      :class="[`${type}-bubble`, { 'is-editing': isEditing }]"
      @click="handleMessageClick"
    >
      <!-- Message Label with Edit Button for User Messages -->
      <div class="message-label" :class="`${type}-label`">
        <q-icon
          :name="type === 'user' ? 'person' : type === 'system' ? 'error_outline' : 'smart_toy'"
          size="12px"
          class="q-mr-xs"
        />
        <span>{{ type === 'user' ? 'You' : type === 'system' ? 'System' : 'Assistant' }}</span>
        <!-- Edit button for user messages (not question responses/skipped, not while editing) -->
        <q-btn
          v-if="
            type === 'user' &&
            !questionResponseData &&
            !questionSkippedData &&
            !isEditing &&
            editable
          "
          flat
          dense
          round
          size="xs"
          icon="edit"
          color="grey-6"
          class="edit-btn q-ml-auto"
          @click.stop="startEditing"
        >
          <q-tooltip :delay="300">Edit and resend</q-tooltip>
        </q-btn>
      </div>
      <!-- System Error Header -->
      <div v-if="type === 'system' && error" class="system-error-header">
        <q-icon name="error" size="14px" class="q-mr-xs" />
        <span>Error</span>
      </div>

      <!-- Inline Editor (when editing user message) -->
      <InlineMessageEditor
        v-if="isEditing"
        :initial-text="message"
        @submit="handleEditSubmit"
        @cancel="cancelEditing"
      />

      <!-- Main Message Content (when not editing) -->
      <template v-else>
        <div
          v-if="type === 'system'"
          class="message-content system-error-content"
          v-html="error || message"
        ></div>
        <!-- Question Response Panel (for user messages with question responses) -->
        <QuestionResponsePanel
          v-else-if="questionResponseData"
          :title="questionResponseData.title"
          :responses="questionResponseData.responses"
        />
        <!-- Question Skipped Panel (for user messages with skipped questions) -->
        <QuestionSkippedPanel
          v-else-if="questionSkippedData"
          v-bind="questionSkippedData.title ? { title: questionSkippedData.title } : {}"
          :questions="questionSkippedData.questions"
          :user-message="questionSkippedData.user_message"
        />
        <!-- Unified Activity Timeline for assistant messages -->
        <ActivityTimeline
          v-else-if="type === 'assistant' && traceEvents"
          :trace-events="traceEvents"
          :message-content="message"
          :is-streaming="isStreaming"
          :debug-enabled="debugEnabled"
          @debug-inspect-tool-call="$emit('debug-inspect-tool-call', $event)"
        />
        <!-- Plain message content for user messages without question responses -->
        <div v-else class="message-content" v-html="formatMessage(message, isStreaming)"></div>
      </template>

      <!-- Token Usage (for assistant messages) -->
      <div v-if="type === 'assistant' && usage && !isEditing" class="message-meta">
        <q-icon name="token" size="12px" class="q-mr-xs" />
        <span>{{ formatTokens(usage.totalTokens) }} tokens</span>
        <!-- Show breakdown if sub-agents were used -->
        <q-tooltip v-if="usageBreakdown && usageBreakdown.subAgents.totalTokens > 0" :delay="300">
          <div class="usage-tooltip">
            <div>Main: {{ formatTokens(usageBreakdown.main.totalTokens) }}</div>
            <div>Sub-agents: {{ formatTokens(usageBreakdown.subAgents.totalTokens) }}</div>
            <div v-if="usageBreakdown.llmCallCount && usageBreakdown.llmCallCount > 1">
              LLM calls: {{ usageBreakdown.llmCallCount }}
            </div>
          </div>
        </q-tooltip>
        <!-- Context fill indicator -->
        <span
          v-if="contextUsage && contextUsage.contextWindow > 0"
          class="context-indicator"
          :class="contextFillClass"
        >
          ({{ contextUsage.fillPercent.toFixed(0) }}% ctx)
        </span>
      </div>

      <!-- Artifacts (for assistant messages) -->
      <TurnArtifacts
        v-if="type === 'assistant' && artifacts && artifacts.length > 0 && !isEditing"
        :artifacts="artifacts"
      />

      <!-- File Changes (for assistant messages) -->
      <template v-if="type === 'assistant' && fileChangeEvents.length > 0 && !isEditing">
        <DiffPreview
          v-for="fileChange in fileChangeEvents"
          :key="fileChange.id"
          :file-change="fileChange"
        />
      </template>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue';
import { useMessageFormatting } from '../composables/useMessageFormatting';
import ActivityTimeline from './ActivityTimeline.vue';
import TurnArtifacts from './TurnArtifacts.vue';
import DiffPreview from './DiffPreview.vue';
import QuestionResponsePanel from './QuestionResponsePanel.vue';
import QuestionSkippedPanel from './QuestionSkippedPanel.vue';
import InlineMessageEditor from './InlineMessageEditor.vue';
import type {
  TraceEvent,
  TraceEventFileChange,
  Artifact,
  TokenUsage,
  UsageBreakdown,
  ContextUsage,
} from 'src/apps/CodeEditor/core/types';
import type { QuestionResponseData, QuestionSkippedData } from '../types/questions';
import { QUESTION_RESPONSE_MARKER, QUESTION_SKIPPED_MARKER } from '../types/questions';
import { COMMAND_APPROVED_MARKER, COMMAND_SKIPPED_MARKER } from '../composables/useChatInput';

const props = defineProps<{
  message: string;
  type: 'user' | 'assistant' | 'system';
  traceEvents?: TraceEvent[] | undefined;
  usage?: TokenUsage | undefined;
  usageBreakdown?: UsageBreakdown | undefined;
  contextUsage?: ContextUsage | undefined;
  error?: string | undefined;
  isStreaming?: boolean | undefined;
  artifacts?: Artifact[] | undefined;
  editable?: boolean | undefined;
  debugEnabled?: boolean | undefined;
}>();

const emit = defineEmits<{
  'edit-submit': [newText: string];
  'debug-inspect-tool-call': [toolCallId: string];
}>();

const { formatMessage, handleMessageClick: handleClick } = useMessageFormatting();

// Editing state
const isEditing = ref(false);

const fileChangeEvents = computed(() => {
  if (!props.traceEvents) return [];
  return props.traceEvents.filter((e): e is TraceEventFileChange => e.type === 'file_change');
});

// Context fill styling
const contextFillClass = computed(() => {
  if (!props.contextUsage) return '';
  const percent = props.contextUsage.fillPercent;
  if (percent >= 90) return 'context-critical';
  if (percent >= 75) return 'context-warning';
  return '';
});

// Format tokens for display
function formatTokens(n: number): string {
  if (n >= 1000000) return `${(n / 1000000).toFixed(1)}M`;
  if (n >= 1000) return `${(n / 1000).toFixed(1)}K`;
  return n.toString();
}

// Detect and parse question response messages
const questionResponseData = computed((): QuestionResponseData | null => {
  if (props.type !== 'user') return null;
  if (!props.message.startsWith(QUESTION_RESPONSE_MARKER)) return null;

  try {
    const jsonStr = props.message.slice(QUESTION_RESPONSE_MARKER.length);
    const parsed = JSON.parse(jsonStr) as unknown;

    // Validate the structure
    if (
      typeof parsed === 'object' &&
      parsed !== null &&
      'type' in parsed &&
      (parsed as { type: unknown }).type === 'question_response' &&
      'title' in parsed &&
      'responses' in parsed &&
      Array.isArray((parsed as { responses: unknown }).responses)
    ) {
      return parsed as QuestionResponseData;
    }
  } catch {
    // Not a valid question response, will render as normal message
  }
  return null;
});

// Detect and parse skipped question messages
const questionSkippedData = computed((): QuestionSkippedData | null => {
  if (props.type !== 'user') return null;
  if (!props.message.startsWith(QUESTION_SKIPPED_MARKER)) return null;

  try {
    const jsonStr = props.message.slice(QUESTION_SKIPPED_MARKER.length);
    const parsed = JSON.parse(jsonStr) as unknown;

    // Validate the structure
    if (
      typeof parsed === 'object' &&
      parsed !== null &&
      'type' in parsed &&
      (parsed as { type: unknown }).type === 'question_skipped' &&
      'questions' in parsed &&
      Array.isArray((parsed as { questions: unknown }).questions) &&
      'user_message' in parsed &&
      typeof (parsed as { user_message: unknown }).user_message === 'string'
    ) {
      return parsed as QuestionSkippedData;
    }
  } catch {
    // Not a valid skipped question, will render as normal message
  }
  return null;
});

// Detect command approved/skipped messages - these should be hidden from UI
const isHiddenCommandMessage = computed((): boolean => {
  if (props.type !== 'user') return false;
  return (
    props.message.startsWith(COMMAND_APPROVED_MARKER) ||
    props.message.startsWith(COMMAND_SKIPPED_MARKER)
  );
});

function handleMessageClick(event: MouseEvent) {
  if (!isEditing.value) {
    handleClick(event);
  }
}

function startEditing() {
  isEditing.value = true;
}

function cancelEditing() {
  isEditing.value = false;
}

function handleEditSubmit(newText: string) {
  isEditing.value = false;
  emit('edit-submit', newText);
}
</script>

<style scoped>
.message {
  display: block;
  margin-bottom: 16px;
  width: 100%;
  box-sizing: border-box;
}

.message-bubble {
  width: 100%;
  box-sizing: border-box;
  overflow-wrap: break-word;
  word-wrap: break-word;
  overflow-x: hidden;
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

.user-label {
  color: #1976d2;
}

.assistant-label {
  color: #7b1fa2;
}

.system-label {
  color: #c62828;
}

.user-bubble {
  background: #e3f2fd;
  border-left: 3px solid #1976d2;
  border-radius: 0 8px 8px 0;
  padding: 10px 14px;
}

.assistant-bubble {
  background: #fafafa;
  border-left: 3px solid #7b1fa2;
  border-radius: 0 8px 8px 0;
  padding: 12px 14px;
}

.system-bubble {
  background: #ffebee;
  border-left: 3px solid #c62828;
  border-radius: 0 8px 8px 0;
  padding: 12px 14px;
}

.system-error-header {
  display: flex;
  align-items: center;
  color: #c62828;
  font-weight: 600;
  font-size: 12px;
  margin-bottom: 6px;
  text-transform: uppercase;
  letter-spacing: 0.5px;
}

.system-error-content {
  color: #b71c1c;
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

.message-meta {
  margin-top: 8px;
  font-size: 11px;
  color: #9e9e9e;
  display: flex;
  align-items: center;
  gap: 4px;
}

.context-indicator {
  margin-left: 4px;
  color: #888;
}

.context-warning {
  color: #f57c00;
}

.context-critical {
  color: #d32f2f;
}

.usage-tooltip {
  font-size: 11px;
  line-height: 1.4;
}

/* Edit button styling */
.message-label {
  position: relative;
}

.edit-btn {
  opacity: 0;
  transition: opacity 0.2s ease;
}

.message-bubble:hover .edit-btn {
  opacity: 0.6;
}

.edit-btn:hover {
  opacity: 1 !important;
}

/* Editing state */
.message-bubble.is-editing {
  background: #fff;
  border-color: #1976d2;
}
</style>
