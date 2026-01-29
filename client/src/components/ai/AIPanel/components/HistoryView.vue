<template>
  <q-scroll-area class="history-area">
    <div class="history-container">
      <!-- Search Box -->
      <div class="history-search">
        <q-input
          v-model="historySearch"
          placeholder="Search chats..."
          dense
          outlined
          clearable
          class="history-search-input"
        >
          <template v-slot:prepend>
            <q-icon name="search" size="16px" color="grey-6" />
          </template>
        </q-input>
      </div>

      <!-- Loading State -->
      <div v-if="isLoadingHistory" class="history-loading">
        <q-spinner-dots size="48px" color="primary" />
        <div class="history-loading-text">Loading chat history...</div>
      </div>

      <!-- History List -->
      <div v-else class="history-list">
        <div
          v-for="session in filteredSessions"
          :key="session.id"
          class="history-item"
          :class="{
            'history-item-active': chatStore.currentSession?.id === session.id,
            'history-item-loading': isLoadingSession && loadingSessionId === session.id,
          }"
          @click="handleLoadSession(session.id)"
        >
          <div class="history-item-content">
            <div class="history-item-title">{{ session.title }}</div>
            <div class="history-item-meta">
              <span>{{ formatDate(session.updatedAt) }}</span>
              <span class="history-item-dot">•</span>
              <span>{{ session.turnCount }} {{ session.turnCount === 1 ? 'turn' : 'turns' }}</span>
            </div>
          </div>
          <div class="history-item-actions">
            <q-spinner-dots
              v-if="isLoadingSession && loadingSessionId === session.id"
              size="16px"
              color="primary"
              class="history-loading-spinner"
            />
            <q-btn
              v-else
              flat
              dense
              round
              size="xs"
              icon="edit"
              @click.stop="$emit('rename-session', session.id)"
              class="history-action-btn"
            >
              <q-tooltip :delay="300">Rename</q-tooltip>
            </q-btn>
            <q-btn
              v-if="!isLoadingSession || loadingSessionId !== session.id"
              flat
              dense
              round
              size="xs"
              icon="delete_outline"
              @click.stop="$emit('delete-session', session.id)"
              class="history-action-btn history-action-delete"
            >
              <q-tooltip :delay="300">Delete</q-tooltip>
            </q-btn>
          </div>
        </div>

        <!-- Empty State -->
        <div v-if="filteredSessions.length === 0" class="history-empty">
          <q-icon name="inbox" size="40px" color="grey-4" />
          <div class="history-empty-text">
            {{ historySearch ? 'No matching chats found' : 'No chat history yet' }}
          </div>
          <div v-if="!historySearch" class="history-empty-hint">
            Start a new conversation to begin
          </div>
        </div>
      </div>
    </div>
  </q-scroll-area>
</template>

<script setup lang="ts">
import { computed, ref, watch } from 'vue';
import { storeToRefs } from 'pinia';
import { useChatStore } from '../../../../stores/chat';
import { useChatHistory } from '../composables/useChatHistory';

const props = defineProps<{
  isLoadingSession?: boolean;
  isHistoryViewVisible?: boolean;
}>();

const chatStore = useChatStore();
const { isLoading: isLoadingHistoryRaw } = storeToRefs(chatStore);
const { historySearch, filteredSessions, formatDate } = useChatHistory();

// Only show loading state when history view is actually visible
const isLoadingHistory = computed(() => {
  return (props.isHistoryViewVisible ?? true) && isLoadingHistoryRaw.value;
});

const isLoadingSession = computed(() => props.isLoadingSession ?? false);
const loadingSessionId = ref<string | null>(null);

const emit = defineEmits<{
  'load-session': [sessionId: string];
  'rename-session': [sessionId: string];
  'delete-session': [sessionId: string];
}>();

function handleLoadSession(sessionId: string) {
  loadingSessionId.value = sessionId;
  emit('load-session', sessionId);
}

// Clear loading session ID when loading completes
watch(isLoadingSession, (isLoading) => {
  if (!isLoading) {
    loadingSessionId.value = null;
  }
});
</script>

<style scoped>
.history-area {
  flex: 1;
  min-height: 0;
  width: 100%;
  background: #ffffff;
}

.history-container {
  padding: 12px;
}

.history-search {
  margin-bottom: 12px;
}

.history-search-input {
  background: #f8f9fa;
  border-radius: 8px;
}

:deep(.history-search-input .q-field__control) {
  border-radius: 8px;
}

:deep(.history-search-input .q-field__native) {
  font-size: 13px;
  padding: 6px 8px;
}

.history-list {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.history-item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 10px 12px;
  border-radius: 8px;
  cursor: pointer;
  transition: all 0.15s ease;
  background: #f8f9fa;
  border: 1px solid transparent;
}

.history-item:hover {
  background: #f0f4f8;
  border-color: #e0e0e0;
}

.history-item:hover .history-item-actions {
  opacity: 1;
}

.history-item-active {
  background: #e3f2fd;
  border-color: #90caf9;
}

.history-item-active:hover {
  background: #bbdefb;
  border-color: #64b5f6;
}

.history-item-content {
  flex: 1;
  min-width: 0;
}

.history-item-title {
  font-size: 13px;
  font-weight: 500;
  color: #333333;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  margin-bottom: 2px;
}

.history-item-meta {
  font-size: 11px;
  color: #9e9e9e;
  display: flex;
  align-items: center;
  gap: 4px;
}

.history-item-dot {
  color: #bdbdbd;
}

.history-item-actions {
  display: flex;
  gap: 2px;
  opacity: 0;
  transition: opacity 0.15s ease;
}

.history-action-btn {
  color: #757575;
}

.history-action-btn:hover {
  color: #1976d2;
}

.history-action-delete:hover {
  color: #d32f2f;
}

.history-item-loading {
  opacity: 0.7;
  pointer-events: none;
}

.history-item-loading .history-item-actions {
  opacity: 1;
}

.history-loading-spinner {
  margin-right: 4px;
}

.history-loading {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 48px 20px;
  text-align: center;
}

.history-loading-text {
  font-size: 14px;
  font-weight: 500;
  color: #757575;
  margin-top: 16px;
}

.history-empty {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 48px 20px;
  text-align: center;
}

.history-empty-text {
  font-size: 14px;
  font-weight: 500;
  color: #757575;
  margin-top: 12px;
}

.history-empty-hint {
  font-size: 12px;
  color: #9e9e9e;
  margin-top: 4px;
}
</style>
