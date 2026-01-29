<template>
  <div class="question-skipped-panel">
    <div class="question-skipped-header">
      <q-icon name="skip_next" size="16px" class="q-mr-sm" />
      <span class="question-skipped-title">{{ title || 'Questions Skipped' }}</span>
    </div>

    <div class="question-skipped-content">
      <!-- User's continuation message -->
      <div v-if="userMessage" class="user-message-section">
        <div class="user-message-label">User message:</div>
        <div class="user-message-text">{{ userMessage }}</div>
      </div>

      <!-- Skipped questions (expandable) -->
      <q-expansion-item
        v-model="expanded"
        icon="help_outline"
        label="View skipped questions"
        class="questions-expansion"
        dense
      >
        <div class="skipped-questions-list">
          <div v-for="question in questions" :key="question.id" class="skipped-question-item">
            <div class="skipped-question-prompt">
              <q-icon name="help_outline" size="14px" class="q-mr-xs" />
              {{ question.prompt }}
            </div>
            <div class="skipped-question-options">
              <q-chip
                v-for="option in question.options"
                :key="option.id"
                dense
                color="grey-4"
                text-color="grey-8"
                class="skipped-option-chip"
              >
                {{ option.label }}
              </q-chip>
            </div>
          </div>
        </div>
      </q-expansion-item>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue';
import type { Question } from '../types/questions';

defineProps<{
  title?: string;
  questions: Question[];
  userMessage: string;
}>();

const expanded = ref(false);
</script>

<style scoped>
.question-skipped-panel {
  background: #f5f5f5;
  border: 1px solid #bdbdbd;
  border-radius: 8px;
  overflow: hidden;
}

.question-skipped-header {
  display: flex;
  align-items: center;
  padding: 10px 14px;
  background: #e0e0e0;
  border-bottom: 1px solid #bdbdbd;
  font-weight: 600;
  font-size: 13px;
  color: #616161;
}

.question-skipped-title {
  color: #424242;
}

.question-skipped-content {
  padding: 14px;
}

.user-message-section {
  margin-bottom: 12px;
  padding-bottom: 12px;
  border-bottom: 1px solid #e0e0e0;
}

.user-message-label {
  font-size: 11px;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.5px;
  color: #757575;
  margin-bottom: 6px;
}

.user-message-text {
  font-size: 13px;
  color: #333;
  line-height: 1.5;
}

.questions-expansion {
  border: 1px solid #e0e0e0;
  border-radius: 4px;
  background: #fafafa;
}

.questions-expansion :deep(.q-expansion-item__container) {
  border: none;
}

.questions-expansion :deep(.q-expansion-item__header) {
  padding: 8px 12px;
  min-height: 36px;
}

.questions-expansion :deep(.q-expansion-item__content) {
  padding: 12px;
  background: #ffffff;
}

.skipped-questions-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.skipped-question-item {
  padding-bottom: 12px;
  border-bottom: 1px solid #f0f0f0;
}

.skipped-question-item:last-child {
  border-bottom: none;
  padding-bottom: 0;
}

.skipped-question-prompt {
  display: flex;
  align-items: flex-start;
  font-size: 13px;
  font-weight: 500;
  color: #333;
  margin-bottom: 8px;
}

.skipped-question-prompt .q-icon {
  color: #9e9e9e;
  flex-shrink: 0;
  margin-top: 2px;
}

.skipped-question-options {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  padding-left: 22px;
}

.skipped-option-chip {
  font-size: 12px;
  opacity: 0.7;
}
</style>
