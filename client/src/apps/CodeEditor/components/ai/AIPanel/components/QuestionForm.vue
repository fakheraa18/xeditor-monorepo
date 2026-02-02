<template>
  <div class="question-form">
    <div class="question-form-header">
      <q-icon name="help_outline" size="16px" class="q-mr-sm" />
      <span class="question-form-title">{{ title || 'Questions' }}</span>
    </div>

    <div class="question-form-content">
      <div v-for="question in questions" :key="question.id" class="question-item">
        <div class="question-prompt">{{ question.prompt }}</div>

        <div class="question-options">
          <!-- Multi-select with checkboxes -->
          <template v-if="question.allow_multiple">
            <q-checkbox
              v-for="option in question.options"
              :key="option.id"
              v-model="answers[question.id]"
              :val="option.id"
              :label="option.label"
              dense
              class="question-option"
            />
          </template>

          <!-- Single-select with radio buttons -->
          <template v-else>
            <q-radio
              v-for="option in question.options"
              :key="option.id"
              v-model="singleAnswers[question.id]"
              :val="option.id"
              :label="option.label"
              dense
              class="question-option"
            />
          </template>
        </div>
      </div>
    </div>

    <div class="question-form-actions">
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
        label="Submit"
        color="primary"
        :disable="!hasAnswers"
        @click="handleSubmit"
      />
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, watch } from 'vue';
import type { Question } from '../types/questions';

const props = defineProps<{
  title?: string;
  questions: Question[];
}>();

const emit = defineEmits<{
  submit: [answers: Record<string, string[]>];
  skip: [];
}>();

// Multi-select answers (array of selected option IDs)
const answers = ref<Record<string, string[]>>({});

// Single-select answers (single option ID)
const singleAnswers = ref<Record<string, string>>({});

// Initialize answers when questions change
watch(
  () => props.questions,
  (questions) => {
    const newAnswers: Record<string, string[]> = {};
    const newSingleAnswers: Record<string, string> = {};

    for (const q of questions) {
      if (q.allow_multiple) {
        newAnswers[q.id] = [];
      } else {
        newSingleAnswers[q.id] = '';
      }
    }

    answers.value = newAnswers;
    singleAnswers.value = newSingleAnswers;
  },
  { immediate: true },
);

const hasAnswers = computed(() => {
  // Check if at least one question has an answer
  for (const q of props.questions) {
    if (q.allow_multiple) {
      const answerArray = answers.value[q.id];
      if (answerArray && answerArray.length > 0) {
        return true;
      }
    } else {
      if (singleAnswers.value[q.id]) {
        return true;
      }
    }
  }
  return false;
});

function handleSubmit() {
  // Combine single and multi-select answers
  const combinedAnswers: Record<string, string[]> = {};

  for (const q of props.questions) {
    if (q.allow_multiple) {
      combinedAnswers[q.id] = answers.value[q.id] || [];
    } else {
      const singleAnswer = singleAnswers.value[q.id];
      combinedAnswers[q.id] = singleAnswer ? [singleAnswer] : [];
    }
  }

  emit('submit', combinedAnswers);
}

function handleSkip() {
  emit('skip');
}
</script>

<style scoped>
.question-form {
  background: #fff8e1;
  border: 1px solid #ffe082;
  border-radius: 8px;
  margin: 12px 0;
  overflow: hidden;
}

.question-form-header {
  display: flex;
  align-items: center;
  padding: 10px 14px;
  background: #fff3c4;
  border-bottom: 1px solid #ffe082;
  font-weight: 600;
  font-size: 13px;
  color: #f57f17;
}

.question-form-title {
  color: #5d4037;
}

.question-form-content {
  padding: 14px;
}

.question-item {
  margin-bottom: 16px;
}

.question-item:last-child {
  margin-bottom: 0;
}

.question-prompt {
  font-size: 13px;
  font-weight: 500;
  color: #333;
  margin-bottom: 8px;
}

.question-options {
  display: flex;
  flex-direction: column;
  gap: 4px;
  padding-left: 4px;
}

.question-option {
  font-size: 13px;
}

.question-option :deep(.q-checkbox__label),
.question-option :deep(.q-radio__label) {
  font-size: 13px;
  color: #555;
}

.question-form-actions {
  display: flex;
  justify-content: flex-end;
  padding: 10px 14px;
  background: #fffde7;
  border-top: 1px solid #ffe082;
}
</style>
