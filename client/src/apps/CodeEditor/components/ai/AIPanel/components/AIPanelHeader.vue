<template>
  <div class="ai-panel-toolbar row items-center justify-between no-wrap">
    <div class="row items-center no-wrap">
      <q-icon name="smart_toy" size="18px" color="primary" class="q-mr-sm" />
      <span class="panel-title">{{
        showHistoryView ? 'Chat History' : showSetsView ? 'Prompt Sets' : 'AI Assistant'
      }}</span>
    </div>
    <div class="row items-center q-gutter-xs">
      <q-btn
        flat
        dense
        round
        size="sm"
        icon="folder_special"
        @click="$emit('toggle-sets')"
        :disable="!hasProject"
        class="toolbar-btn"
        :class="{ 'toolbar-btn-active': showSetsView }"
      >
        <q-tooltip :delay="300">{{ showSetsView ? 'Back to Chat' : 'Prompt Sets' }}</q-tooltip>
      </q-btn>
      <q-btn
        flat
        dense
        round
        size="sm"
        :icon="showHistoryView ? 'chat' : 'history'"
        @click="$emit('toggle-history')"
        :disable="!hasProject"
        class="toolbar-btn"
        :class="{ 'toolbar-btn-active': showHistoryView }"
      >
        <q-tooltip :delay="300">{{
          showHistoryView ? 'Back to Chat' : 'Chat History'
        }}</q-tooltip>
      </q-btn>
      <q-btn
        flat
        dense
        round
        size="sm"
        icon="add_comment"
        @click="$emit('new-chat')"
        :disable="!hasProject"
        class="toolbar-btn"
      >
        <q-tooltip :delay="300">New Chat</q-tooltip>
      </q-btn>
    </div>
  </div>
</template>

<script setup lang="ts">
defineProps<{
  showHistoryView: boolean;
  showSetsView: boolean;
  hasProject: boolean;
}>();

defineEmits<{
  'toggle-history': [];
  'toggle-sets': [];
  'new-chat': [];
}>();
</script>

<style scoped>
.ai-panel-toolbar {
  height: 35px;
  min-height: 35px;
  padding: 0 12px;
  background: #f3f3f3;
  border-bottom: 1px solid #e0e0e0;
  flex-shrink: 0;
}

.panel-title {
  font-size: 11px;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.5px;
  color: #616161;
}

.toolbar-btn {
  color: #757575;
}

.toolbar-btn:hover {
  color: #1976d2;
}

.toolbar-btn-active {
  color: #1976d2;
  background: rgba(25, 118, 210, 0.1);
}
</style>
