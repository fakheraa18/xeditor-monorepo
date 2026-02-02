<template>
  <div class="question-response-panel">
    <div class="question-response-header">
      <q-icon name="check_circle_outline" size="16px" class="q-mr-sm" />
      <span class="question-response-title">{{ title }}</span>
    </div>

    <div class="question-response-content">
      <div v-for="(response, index) in responses" :key="index" class="response-item">
        <div class="response-question">
          <q-icon name="help_outline" size="14px" class="q-mr-xs" />
          {{ response.question }}
        </div>
        <div class="response-answers">
          <q-chip
            v-for="(answer, answerIndex) in response.answers"
            :key="answerIndex"
            dense
            color="amber-3"
            text-color="brown-8"
            class="response-chip"
          >
            {{ answer }}
          </q-chip>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
defineProps<{
  title: string;
  responses: Array<{
    question: string;
    answers: string[];
  }>;
}>();
</script>

<style scoped>
.question-response-panel {
  background: #e8f5e9;
  border: 1px solid #a5d6a7;
  border-radius: 8px;
  overflow: hidden;
}

.question-response-header {
  display: flex;
  align-items: center;
  padding: 10px 14px;
  background: #c8e6c9;
  border-bottom: 1px solid #a5d6a7;
  font-weight: 600;
  font-size: 13px;
  color: #2e7d32;
}

.question-response-title {
  color: #1b5e20;
}

.question-response-content {
  padding: 14px;
}

.response-item {
  margin-bottom: 12px;
}

.response-item:last-child {
  margin-bottom: 0;
}

.response-question {
  display: flex;
  align-items: flex-start;
  font-size: 13px;
  font-weight: 500;
  color: #333;
  margin-bottom: 6px;
}

.response-question .q-icon {
  color: #666;
  flex-shrink: 0;
  margin-top: 2px;
}

.response-answers {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  padding-left: 22px;
}

.response-chip {
  font-size: 12px;
  font-weight: 500;
}
</style>
