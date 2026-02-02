<template>
  <div v-if="hasStats" class="session-stats">
    <!-- Context Fill Indicator -->
    <div
      v-if="contextUsage && contextUsage.usedPromptTokens > 0"
      class="context-fill"
      :class="contextFillClass"
    >
      <div class="context-bar-wrapper">
        <q-linear-progress
          v-if="contextUsage.contextWindow > 0"
          :value="contextUsage.fillPercent / 100"
          :color="contextFillColor"
          size="3px"
          class="context-bar"
        />
      </div>
      <span class="context-label">
        Context: {{ formatNumber(contextUsage.usedPromptTokens) }}
        <template v-if="contextUsage.contextWindow > 0">
          /{{ formatNumber(contextUsage.contextWindow) }} ({{
            contextUsage.fillPercent.toFixed(0)
          }}%)
        </template>
        <template v-else> tokens used </template>
      </span>
    </div>

    <!-- Token Totals -->
    <div class="token-totals" @click="showDetails = !showDetails">
      <q-icon name="token" size="12px" class="q-mr-xs" />
      <span class="total-label">{{ formatNumber(stats.totalTokens) }} tokens</span>
      <q-icon :name="showDetails ? 'expand_less' : 'expand_more'" size="14px" class="q-ml-xs" />
    </div>

    <!-- Detailed Breakdown (expandable) -->
    <q-slide-transition>
      <div v-show="showDetails" class="stats-details">
        <div class="stats-row">
          <span class="stats-label">Prompt:</span>
          <span class="stats-value">{{ formatNumber(stats.promptTokens) }}</span>
        </div>
        <div class="stats-row">
          <span class="stats-label">Completion:</span>
          <span class="stats-value">{{ formatNumber(stats.completionTokens) }}</span>
        </div>

        <!-- Per-Family Breakdown -->
        <div v-if="Object.keys(stats.byFamily).length > 1" class="family-breakdown">
          <div class="family-header">By Model Family:</div>
          <div v-for="(usage, family) in stats.byFamily" :key="family" class="family-row">
            <span class="family-name">{{ family }}:</span>
            <span class="family-value">{{ formatNumber(usage.totalTokens) }}</span>
          </div>
        </div>
      </div>
    </q-slide-transition>
  </div>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue';
import type { SessionTokenStats, ContextUsage } from '../../../../core/types';

const props = defineProps<{
  stats: SessionTokenStats;
  contextUsage?: ContextUsage | null;
}>();

const showDetails = ref(false);

const hasStats = computed(() => props.stats.totalTokens > 0);

const contextFillColor = computed(() => {
  if (!props.contextUsage) return 'primary';
  const percent = props.contextUsage.fillPercent;
  if (percent >= 90) return 'negative';
  if (percent >= 75) return 'warning';
  return 'primary';
});

const contextFillClass = computed(() => {
  if (!props.contextUsage) return '';
  const percent = props.contextUsage.fillPercent;
  if (percent >= 90) return 'fill-critical';
  if (percent >= 75) return 'fill-warning';
  return '';
});

function formatNumber(n: number): string {
  if (n >= 1000000) return `${(n / 1000000).toFixed(1)}M`;
  if (n >= 1000) return `${(n / 1000).toFixed(1)}K`;
  return n.toString();
}
</script>

<style scoped>
.session-stats {
  padding: 6px 12px;
  background: #fafafa;
  border-bottom: 1px solid #e0e0e0;
  font-size: 11px;
  color: #666;
}

.context-fill {
  display: flex;
  flex-direction: column;
  gap: 4px;
  margin-bottom: 4px;
}

.context-bar-wrapper {
  width: 100%;
}

.context-bar {
  width: 100%;
  border-radius: 2px;
}

.context-label {
  white-space: nowrap;
  font-size: 10px;
}

.fill-warning .context-label {
  color: #f57c00;
}

.fill-critical .context-label {
  color: #d32f2f;
}

.token-totals {
  display: flex;
  align-items: center;
  cursor: pointer;
  user-select: none;
}

.token-totals:hover {
  color: #1976d2;
}

.total-label {
  font-weight: 500;
}

.stats-details {
  margin-top: 8px;
  padding: 8px;
  background: #fff;
  border-radius: 4px;
  border: 1px solid #e0e0e0;
}

.stats-row {
  display: flex;
  justify-content: space-between;
  padding: 2px 0;
}

.stats-label {
  color: #888;
}

.stats-value {
  font-weight: 500;
}

.family-breakdown {
  margin-top: 8px;
  padding-top: 8px;
  border-top: 1px solid #eee;
}

.family-header {
  font-weight: 500;
  margin-bottom: 4px;
  color: #555;
}

.family-row {
  display: flex;
  justify-content: space-between;
  padding: 2px 0 2px 8px;
}

.family-name {
  color: #888;
  text-transform: capitalize;
}

.family-value {
  font-weight: 500;
}
</style>
