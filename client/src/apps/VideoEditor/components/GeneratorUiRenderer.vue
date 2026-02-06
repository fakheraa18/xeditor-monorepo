<template>
  <div class="generator-ui-renderer">
    <template v-for="section in schema.sections" :key="section.key">
      <q-expansion-item
        :label="section.label"
        :caption="section.description"
        :default-opened="!section.default_collapsed"
        dense
        header-class="text-white"
        class="q-mb-xs"
      >
        <q-card flat class="bg-transparent">
          <q-card-section class="q-py-sm">
            <template v-for="field in section.fields" :key="field.key">
              <div v-if="isFieldVisible(field)" class="q-mb-sm">
                <!-- String input -->
                <q-input
                  v-if="field.field_type === 'string'"
                  v-model="values[field.key] as string"
                  :label="field.label"
                  :hint="field.description"
                  :placeholder="field.placeholder"
                  :rules="field.required ? [requiredRule] : []"
                  dense
                  outlined
                  dark
                  @update:model-value="emitChange"
                />

                <!-- Multi-line text -->
                <q-input
                  v-else-if="field.field_type === 'text'"
                  v-model="values[field.key] as string"
                  :label="field.label"
                  :hint="field.description"
                  :placeholder="field.placeholder"
                  type="textarea"
                  :rows="3"
                  dense
                  outlined
                  dark
                  @update:model-value="emitChange"
                />

                <!-- Integer input -->
                <q-input
                  v-else-if="field.field_type === 'int'"
                  v-model.number="values[field.key] as number"
                  :label="field.label"
                  :hint="field.description"
                  type="number"
                  :min="field.constraints?.min_value"
                  :max="field.constraints?.max_value"
                  :step="field.constraints?.step ?? 1"
                  dense
                  outlined
                  dark
                  @update:model-value="emitChange"
                />

                <!-- Float input -->
                <q-input
                  v-else-if="field.field_type === 'float'"
                  v-model.number="values[field.key] as number"
                  :label="field.label"
                  :hint="field.description"
                  type="number"
                  :min="field.constraints?.min_value"
                  :max="field.constraints?.max_value"
                  :step="field.constraints?.step ?? 0.1"
                  dense
                  outlined
                  dark
                  @update:model-value="emitChange"
                />

                <!-- Boolean toggle -->
                <q-toggle
                  v-else-if="field.field_type === 'bool'"
                  v-model="values[field.key]"
                  :label="field.label"
                  dark
                  dense
                  @update:model-value="emitChange"
                />

                <!-- Select dropdown -->
                <q-select
                  v-else-if="field.field_type === 'select'"
                  v-model="values[field.key]"
                  :label="field.label"
                  :hint="field.description"
                  :options="fieldOptions(field)"
                  option-value="value"
                  option-label="label"
                  emit-value
                  map-options
                  dense
                  outlined
                  dark
                  @update:model-value="emitChange"
                />

                <!-- Multi-select -->
                <q-select
                  v-else-if="field.field_type === 'multiselect'"
                  v-model="values[field.key]"
                  :label="field.label"
                  :hint="field.description"
                  :options="fieldOptions(field)"
                  option-value="value"
                  option-label="label"
                  emit-value
                  map-options
                  multiple
                  use-chips
                  dense
                  outlined
                  dark
                  @update:model-value="emitChange"
                />

                <!-- Color picker -->
                <div v-else-if="field.field_type === 'color'" class="row items-center">
                  <span class="text-white text-caption q-mr-sm">{{ field.label }}</span>
                  <q-input
                    v-model="values[field.key] as string"
                    dense
                    outlined
                    dark
                    style="max-width: 120px"
                    @update:model-value="emitChange"
                  >
                    <template #append>
                      <q-icon name="colorize" class="cursor-pointer">
                        <q-popup-proxy>
                          <q-color v-model="values[field.key] as string" @change="emitChange" />
                        </q-popup-proxy>
                      </q-icon>
                    </template>
                  </q-input>
                </div>

                <!-- Asset ref (placeholder for now) -->
                <q-input
                  v-else-if="field.field_type === 'asset_ref' || field.field_type === 'asset_refs'"
                  v-model="values[field.key] as string"
                  :label="field.label + ' (Asset ID)'"
                  :hint="field.description"
                  dense
                  outlined
                  dark
                  @update:model-value="emitChange"
                />

                <!-- JSON editor -->
                <q-input
                  v-else-if="field.field_type === 'json'"
                  v-model="values[field.key] as string"
                  :label="field.label"
                  :hint="field.description"
                  type="textarea"
                  :rows="4"
                  dense
                  outlined
                  dark
                  class="json-field"
                  @update:model-value="emitChange"
                />
              </div>
            </template>
          </q-card-section>
        </q-card>
      </q-expansion-item>
    </template>

    <div v-if="schema.sections.length === 0" class="text-grey-7 text-caption q-pa-sm">
      This generator has no configurable parameters.
    </div>
  </div>
</template>

<script setup lang="ts">
import { reactive, watch } from 'vue';
import type { GeneratorUiSchema, UiField, UiFieldOption } from '../types';

const props = defineProps<{
  schema: GeneratorUiSchema;
  modelValue: Record<string, unknown>;
}>();

const emit = defineEmits<{
  'update:modelValue': [value: Record<string, unknown>];
}>();

// Local reactive copy of values with proper typing
const values = reactive<Record<string, string | number | boolean | string[] | null>>({});

// Initialize from defaults and modelValue
function initializeValues(): void {
  // First apply defaults
  for (const section of props.schema.sections) {
    for (const field of section.fields) {
      if (field.default !== undefined) {
        // Convert default to appropriate type
        if (field.field_type === 'json' && typeof field.default === 'object') {
          values[field.key] = JSON.stringify(field.default);
        } else if (field.field_type === 'bool') {
          values[field.key] = Boolean(field.default);
        } else if (field.field_type === 'int' || field.field_type === 'float') {
          values[field.key] = Number(field.default) || 0;
        } else if (field.field_type === 'multiselect' && Array.isArray(field.default)) {
          values[field.key] = field.default;
        } else {
          // Only stringify primitives, not objects
          const def = field.default;
          if (def === null || def === undefined) {
            values[field.key] = '';
          } else if (
            typeof def === 'string' ||
            typeof def === 'number' ||
            typeof def === 'boolean'
          ) {
            values[field.key] = String(def);
          } else {
            values[field.key] = JSON.stringify(def);
          }
        }
      }
    }
  }
  // Then override with modelValue (convert types as needed)
  for (const [key, val] of Object.entries(props.modelValue)) {
    if (val !== undefined) {
      const field = findField(key);
      if (field) {
        if (field.field_type === 'json' && typeof val === 'object') {
          values[key] = JSON.stringify(val);
        } else if (field.field_type === 'bool') {
          values[key] = Boolean(val);
        } else if (field.field_type === 'int' || field.field_type === 'float') {
          values[key] = Number(val) || 0;
        } else if (field.field_type === 'multiselect' && Array.isArray(val)) {
          values[key] = val;
        } else {
          // Only stringify primitives, not objects
          if (val === null || val === undefined) {
            values[key] = '';
          } else if (
            typeof val === 'string' ||
            typeof val === 'number' ||
            typeof val === 'boolean'
          ) {
            values[key] = String(val);
          } else {
            values[key] = JSON.stringify(val);
          }
        }
      } else {
        values[key] = val as string | number | boolean | string[] | null;
      }
    }
  }
}

function findField(key: string): UiField | undefined {
  for (const section of props.schema.sections) {
    const field = section.fields.find((f) => f.key === key);
    if (field) return field;
  }
  return undefined;
}

initializeValues();

// Watch for external changes
watch(
  () => props.modelValue,
  (newVal) => {
    Object.assign(values, newVal);
  },
  { deep: true },
);

watch(
  () => props.schema,
  () => initializeValues(),
  { deep: true },
);

function emitChange(): void {
  emit('update:modelValue', { ...values });
}

function isFieldVisible(field: UiField): boolean {
  if (!field.depends_on) return true;
  return !!values[field.depends_on];
}

function fieldOptions(field: UiField): UiFieldOption[] {
  return field.options ?? [];
}

function requiredRule(val: unknown): boolean | string {
  if (val === null || val === undefined || val === '') return 'This field is required';
  return true;
}
</script>

<style scoped lang="scss">
.generator-ui-renderer {
  :deep(.q-expansion-item__content) {
    padding: 0;
  }

  .json-field :deep(textarea) {
    font-family: 'Roboto Mono', monospace;
    font-size: 12px;
  }
}
</style>
