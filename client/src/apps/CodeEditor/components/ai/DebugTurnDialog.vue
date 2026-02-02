<template>
  <q-dialog v-model="isOpen" persistent maximized>
    <q-card class="debug-dialog-card">
      <!-- Header -->
      <q-card-section class="debug-dialog-header row items-center no-wrap">
        <q-icon name="bug_report" size="24px" color="orange" class="q-mr-sm" />
        <div class="text-h6">Debug Inspector</div>
        <q-space />
        <q-btn flat round dense icon="close" @click="close" />
      </q-card-section>

      <q-separator />

      <!-- Loading State -->
      <q-card-section v-if="isLoading" class="column items-center justify-center q-pa-xl">
        <q-spinner-dots size="48px" color="primary" />
        <div class="q-mt-md text-grey-6">Loading debug bundle...</div>
      </q-card-section>

      <!-- Error State -->
      <q-card-section v-else-if="error" class="column items-center justify-center q-pa-xl">
        <q-icon name="error_outline" size="48px" color="negative" />
        <div class="q-mt-md text-negative text-center">{{ error }}</div>
        <q-btn flat color="primary" label="Close" @click="close" class="q-mt-md" />
      </q-card-section>

      <!-- Debug Content -->
      <template v-else-if="debugBundle">
        <!-- Summary Chips -->
        <q-card-section class="debug-summary">
          <div class="row items-center q-gutter-sm wrap">
            <q-chip dense color="blue-1" text-color="primary" icon="tag">
              Turn: {{ debugBundle.turnId?.substring(0, 8) }}...
            </q-chip>
            <q-chip dense color="purple-1" text-color="purple" icon="psychology">
              Mode: {{ debugBundle.prompt?.mode || 'unknown' }}
            </q-chip>
            <q-chip dense color="green-1" text-color="positive" icon="memory">
              Model: {{ debugBundle.model?.id || 'unknown' }}
            </q-chip>
            <q-chip dense color="orange-1" text-color="warning" icon="folder">
              Set: {{ debugBundle.prompt?.setId || 'default' }}
            </q-chip>
            <q-chip
              v-if="debugBundle.model?.family"
              dense
              color="grey-3"
              text-color="grey-7"
              icon="category"
            >
              Family: {{ debugBundle.model.family }}
            </q-chip>
          </div>
        </q-card-section>

        <q-separator />

        <!-- Tabs -->
        <q-tabs
          v-model="activeTab"
          dense
          class="debug-tabs text-grey-8"
          active-color="primary"
          indicator-color="primary"
          align="left"
        >
          <q-tab name="system" label="System Prompt" icon="description" />
          <q-tab
            name="messages"
            label="LLM Messages"
            icon="chat"
            :disable="!debugBundle.llmMessages"
          />
          <q-tab
            name="trace"
            label="Trace Events"
            icon="timeline"
            :disable="!debugBundle.traceEvents?.length"
          />
          <q-tab
            name="tools"
            label="Tool Calls"
            icon="build"
            :disable="!debugBundle.toolCalls?.length"
          />
          <q-tab name="files" label="Files" icon="folder_open" />
        </q-tabs>

        <q-separator />

        <q-tab-panels v-model="activeTab" animated class="debug-tab-panels">
          <!-- System Prompt Tab -->
          <q-tab-panel name="system" class="q-pa-none">
            <div class="debug-tab-content">
              <div class="debug-section-header row items-center justify-between">
                <span>Resolved System Prompt</span>
                <q-btn
                  flat
                  dense
                  icon="content_copy"
                  size="sm"
                  @click="copyToClipboard(debugBundle.resolvedSystemPrompt || '')"
                >
                  <q-tooltip>Copy to clipboard</q-tooltip>
                </q-btn>
              </div>
              <pre class="debug-code-block">{{
                debugBundle.resolvedSystemPrompt || 'No system prompt'
              }}</pre>
            </div>
          </q-tab-panel>

          <!-- LLM Messages Tab -->
          <q-tab-panel name="messages" class="q-pa-none">
            <div class="debug-tab-content">
              <div class="debug-section-header row items-center justify-between">
                <div class="row items-center q-gutter-sm">
                  <span>Messages Sent to LLM ({{ currentMessages.length || 0 }} messages)</span>
                  <q-btn-toggle
                    v-if="availableSteps.length > 1"
                    v-model="activeStep"
                    toggle-color="primary"
                    :options="availableSteps"
                    dense
                    flat
                    size="sm"
                  />
                </div>
                <q-btn
                  flat
                  dense
                  icon="content_copy"
                  size="sm"
                  @click="copyToClipboard(JSON.stringify(currentMessages, null, 2))"
                >
                  <q-tooltip>Copy JSON to clipboard</q-tooltip>
                </q-btn>
              </div>
              <div class="messages-list">
                <div
                  v-for="(msg, index) in currentMessages"
                  :key="index"
                  class="llm-message-item"
                  :class="`llm-message-${msg.role}`"
                >
                  <div class="llm-message-header">
                    <q-chip dense size="sm" :color="getRoleColor(msg.role)" text-color="white">
                      {{ msg.role }}
                    </q-chip>
                    <span class="llm-message-index">#{{ index + 1 }}</span>
                  </div>
                  <pre class="llm-message-content">{{ msg.content }}</pre>
                </div>
              </div>
            </div>
          </q-tab-panel>

          <!-- Trace Events Tab -->
          <q-tab-panel name="trace" class="q-pa-none">
            <div class="debug-tab-content">
              <div class="debug-section-header row items-center justify-between">
                <span>Trace Events ({{ debugBundle.traceEvents?.length || 0 }} events)</span>
                <q-btn
                  flat
                  dense
                  icon="content_copy"
                  size="sm"
                  @click="copyToClipboard(JSON.stringify(debugBundle.traceEvents, null, 2))"
                >
                  <q-tooltip>Copy JSON to clipboard</q-tooltip>
                </q-btn>
              </div>
              <div class="trace-events-list">
                <div
                  v-for="(event, index) in debugBundle.traceEvents"
                  :key="index"
                  class="trace-event-item"
                >
                  <div class="trace-event-header">
                    <q-chip dense size="sm" color="blue-grey-3" text-color="grey-8">
                      {{ event.type }}
                    </q-chip>
                    <span class="trace-event-index">#{{ index + 1 }}</span>
                  </div>
                  <pre class="trace-event-content">{{ JSON.stringify(event, null, 2) }}</pre>
                </div>
              </div>
            </div>
          </q-tab-panel>

          <!-- Tool Calls Tab -->
          <q-tab-panel name="tools" class="q-pa-none">
            <div class="debug-tab-content">
              <div class="debug-section-header row items-center justify-between">
                <span>Tool Calls ({{ debugBundle.toolCalls?.length || 0 }} calls)</span>
                <q-btn
                  flat
                  dense
                  icon="content_copy"
                  size="sm"
                  @click="copyToClipboard(JSON.stringify(debugBundle.toolCalls, null, 2))"
                >
                  <q-tooltip>Copy JSON to clipboard</q-tooltip>
                </q-btn>
              </div>
              <div class="tool-calls-list">
                <div
                  v-for="(tool, index) in debugBundle.toolCalls"
                  :key="index"
                  class="tool-call-item"
                >
                  <div class="tool-call-header">
                    <q-chip dense color="teal-3" text-color="grey-9" icon="build">
                      {{ tool.tool }}
                    </q-chip>
                    <span class="tool-call-id">{{ tool.id?.substring(0, 8) }}...</span>
                  </div>
                  <div class="tool-call-section">
                    <div class="tool-call-label">Arguments:</div>
                    <pre class="tool-call-content">{{ JSON.stringify(tool.args, null, 2) }}</pre>
                  </div>
                  <div v-if="tool.result" class="tool-call-section">
                    <div class="tool-call-label">
                      Result:
                      <q-chip
                        v-if="tool.resultTruncated"
                        dense
                        size="xs"
                        color="warning"
                        text-color="white"
                      >
                        truncated
                      </q-chip>
                    </div>
                    <pre class="tool-call-content">{{
                      typeof tool.result === 'string'
                        ? tool.result
                        : JSON.stringify(tool.result, null, 2)
                    }}</pre>
                  </div>
                  <div v-if="tool.error" class="tool-call-section tool-call-error">
                    <div class="tool-call-label">Error:</div>
                    <pre class="tool-call-content error-content">{{ tool.error }}</pre>
                  </div>
                </div>
              </div>
            </div>
          </q-tab-panel>

          <!-- Files Tab -->
          <q-tab-panel name="files" class="q-pa-none">
            <div class="debug-tab-content">
              <div class="debug-section-header">File References</div>
              <div class="files-info">
                <div class="file-info-item">
                  <div class="file-info-label">Prompt File:</div>
                  <div class="file-info-value">
                    {{ debugBundle.prompt?.promptFilePath || 'N/A' }}
                  </div>
                </div>
                <div class="file-info-item">
                  <div class="file-info-label">Parser File:</div>
                  <div class="file-info-value">
                    {{ debugBundle.parser?.parserFilePath || 'N/A' }}
                  </div>
                </div>
                <div class="file-info-item">
                  <div class="file-info-label">Template ID:</div>
                  <div class="file-info-value">{{ debugBundle.prompt?.templateId || 'N/A' }}</div>
                </div>
              </div>
            </div>
          </q-tab-panel>
        </q-tab-panels>
      </template>
    </q-card>
  </q-dialog>
</template>

<script setup lang="ts">
import { ref, watch, computed } from 'vue';
import { useQuasar } from 'quasar';
import { useLocalCompanionStore } from '../../../../stores/localCompanion';
import type { DebugBundle } from 'src/apps/CodeEditor/core/types';

interface Props {
  modelValue: boolean;
  projectId: string;
  chatId: string;
  turnId: string;
}

const props = defineProps<Props>();
const emit = defineEmits<{
  (e: 'update:modelValue', value: boolean): void;
}>();

const $q = useQuasar();
const companionStore = useLocalCompanionStore();

const isOpen = ref(props.modelValue);
const isLoading = ref(false);
const error = ref<string | null>(null);
const debugBundle = ref<DebugBundle | null>(null);
const activeTab = ref('system');
const activeStep = ref(1);

const availableSteps = computed(() => {
  if (!debugBundle.value?.llmCalls?.length) return [];
  return debugBundle.value.llmCalls.map((call) => ({
    label: `Step ${call.step}`,
    value: call.step,
    timestamp: call.timestamp,
  }));
});

const currentMessages = computed(() => {
  if (!debugBundle.value) return [];

  // If we have explicit LLM calls, use the selected step
  if (debugBundle.value.llmCalls?.length) {
    const call = debugBundle.value.llmCalls.find((c) => c.step === activeStep.value);
    return call?.messages || [];
  }

  // Fallback to initial messages (backward compatibility)
  return debugBundle.value.llmMessages || [];
});

watch(
  () => props.modelValue,
  (val) => {
    isOpen.value = val;
    if (val) {
      void fetchDebugBundle();
    }
  },
);

watch(isOpen, (val) => {
  emit('update:modelValue', val);
});

async function fetchDebugBundle() {
  if (!props.projectId || !props.chatId || !props.turnId) {
    error.value = 'Missing required parameters';
    return;
  }

  isLoading.value = true;
  error.value = null;
  debugBundle.value = null;

  try {
    const response = await companionStore.request<{
      success: boolean;
      debug?: DebugBundle;
      error?: string;
    }>('chat_turn_debug_get', {
      projectId: props.projectId,
      chatId: props.chatId,
      turnId: props.turnId,
    });

    if (response.success && response.debug) {
      const bundle = response.debug;
      debugBundle.value = bundle;
      // Initialize active step
      if (bundle.llmCalls && bundle.llmCalls.length > 0) {
        const firstCall = bundle.llmCalls[0];
        if (firstCall) {
          activeStep.value = firstCall.step;
        }
      }
    } else {
      error.value = response.error || 'Failed to fetch debug bundle';
    }
  } catch (e) {
    error.value = e instanceof Error ? e.message : 'Failed to fetch debug bundle';
  } finally {
    isLoading.value = false;
  }
}

function close() {
  isOpen.value = false;
}

function getRoleColor(role: string): string {
  switch (role) {
    case 'system':
      return 'purple';
    case 'user':
      return 'blue';
    case 'assistant':
      return 'green';
    default:
      return 'grey';
  }
}

function copyToClipboard(text: string) {
  void navigator.clipboard.writeText(text).then(() => {
    $q.notify({
      type: 'positive',
      message: 'Copied to clipboard',
      position: 'bottom',
      timeout: 1500,
    });
  });
}
</script>

<style scoped>
.debug-dialog-card {
  width: 100%;
  max-width: 1200px;
  height: 90vh;
  display: flex;
  flex-direction: column;
}

.debug-dialog-header {
  background: #fafafa;
}

.debug-summary {
  background: #f5f5f5;
  padding: 12px 16px;
}

.debug-tabs {
  background: #fff;
}

.debug-tab-panels {
  flex: 1;
  overflow: hidden;
}

.debug-tab-content {
  height: 100%;
  overflow: auto;
  padding: 16px;
}

.debug-section-header {
  font-weight: 600;
  font-size: 14px;
  color: #333;
  margin-bottom: 12px;
  padding-bottom: 8px;
  border-bottom: 1px solid #e0e0e0;
}

.debug-code-block {
  background: #1e1e1e;
  color: #d4d4d4;
  padding: 16px;
  border-radius: 8px;
  font-family: 'Fira Code', 'Monaco', 'Consolas', monospace;
  font-size: 13px;
  line-height: 1.5;
  overflow-x: auto;
  white-space: pre-wrap;
  word-break: break-word;
  max-height: calc(100% - 50px);
}

.messages-list,
.trace-events-list,
.tool-calls-list {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.llm-message-item {
  border: 1px solid #e0e0e0;
  border-radius: 8px;
  overflow: hidden;
}

.llm-message-header {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 12px;
  background: #f5f5f5;
}

.llm-message-index {
  font-size: 12px;
  color: #888;
}

.llm-message-content {
  background: #1e1e1e;
  color: #d4d4d4;
  padding: 12px;
  margin: 0;
  font-family: 'Fira Code', 'Monaco', 'Consolas', monospace;
  font-size: 12px;
  line-height: 1.5;
  overflow-x: auto;
  white-space: pre-wrap;
  word-break: break-word;
  max-height: 400px;
}

.trace-event-item,
.tool-call-item {
  border: 1px solid #e0e0e0;
  border-radius: 8px;
  overflow: hidden;
}

.trace-event-header,
.tool-call-header {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 12px;
  background: #f5f5f5;
}

.trace-event-index,
.tool-call-id {
  font-size: 12px;
  color: #888;
  margin-left: auto;
}

.trace-event-content,
.tool-call-content {
  background: #1e1e1e;
  color: #d4d4d4;
  padding: 12px;
  margin: 0;
  font-family: 'Fira Code', 'Monaco', 'Consolas', monospace;
  font-size: 12px;
  line-height: 1.5;
  overflow-x: auto;
  white-space: pre-wrap;
  word-break: break-word;
  max-height: 300px;
}

.tool-call-section {
  padding: 8px 12px;
  border-top: 1px solid #e0e0e0;
}

.tool-call-label {
  font-size: 12px;
  font-weight: 600;
  color: #666;
  margin-bottom: 4px;
  display: flex;
  align-items: center;
  gap: 8px;
}

.tool-call-error .error-content {
  color: #ff6b6b;
}

.files-info {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.file-info-item {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.file-info-label {
  font-size: 12px;
  font-weight: 600;
  color: #666;
}

.file-info-value {
  font-family: 'Fira Code', 'Monaco', 'Consolas', monospace;
  font-size: 13px;
  color: #333;
  background: #f5f5f5;
  padding: 8px 12px;
  border-radius: 4px;
  word-break: break-all;
}
</style>
