<template>
  <div class="command-confirmation">
    <div class="command-confirmation-header">
      <q-icon name="terminal" size="16px" class="q-mr-sm" />
      <span class="command-confirmation-title">Command Execution Request</span>
    </div>

    <div class="command-confirmation-content">
      <div class="command-label">Command to execute:</div>
      <div class="command-block">
        <pre><code>{{ command }}</code></pre>
      </div>
    </div>

    <div class="command-confirmation-actions">
      <q-btn
        flat
        dense
        label="Skip"
        color="grey-7"
        class="q-mr-sm"
        @click="handleSkip"
      />
      <q-btn
        unelevated
        dense
        label="Allow"
        color="primary"
        @click="handleAllow"
      />
    </div>
  </div>
</template>

<script setup lang="ts">
const props = defineProps<{
  command: string;
  id: string;
}>();

const emit = defineEmits<{
  allow: [id: string];
  skip: [];
}>();

function handleAllow() {
  emit('allow', props.id);
}

function handleSkip() {
  emit('skip');
}
</script>

<style scoped>
.command-confirmation {
  background: #fff3e0;
  border: 1px solid #ffb74d;
  border-radius: 8px;
  margin: 12px 0;
  overflow: hidden;
}

.command-confirmation-header {
  display: flex;
  align-items: center;
  padding: 10px 14px;
  background: #ffe0b2;
  border-bottom: 1px solid #ffb74d;
  font-weight: 600;
  font-size: 13px;
  color: #e65100;
}

.command-confirmation-title {
  color: #5d4037;
}

.command-confirmation-content {
  padding: 14px;
}

.command-label {
  font-size: 13px;
  font-weight: 500;
  color: #333;
  margin-bottom: 8px;
}

.command-block {
  background: #1e1e1e;
  border-radius: 6px;
  padding: 12px;
  overflow-x: auto;
}

.command-block pre {
  margin: 0;
  padding: 0;
  font-family: 'JetBrains Mono', 'Fira Code', Consolas, monospace;
  font-size: 12px;
  line-height: 1.5;
  color: #d4d4d4;
  white-space: pre-wrap;
  word-break: break-all;
}

.command-block code {
  font-family: inherit;
  font-size: inherit;
  color: inherit;
  background: transparent;
  padding: 0;
}

.command-confirmation-actions {
  display: flex;
  justify-content: flex-end;
  padding: 10px 14px;
  background: #fff8e1;
  border-top: 1px solid #ffb74d;
}
</style>
