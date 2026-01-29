<template>
  <q-dialog
    v-model="dialogOpen"
    persistent
    maximized
    transition-show="slide-up"
    transition-hide="slide-down"
  >
    <q-card class="column no-wrap">
      <!-- Header -->
      <q-card-section class="row items-center q-pb-none bg-primary text-white">
        <div class="text-h6">{{ isNewModel ? 'Add New Model' : 'Edit Model' }}</div>
        <q-space />
        <q-btn flat round dense icon="close" v-close-popup />
      </q-card-section>

      <q-separator />

      <!-- Form Content -->
      <q-card-section class="col q-pt-md" style="overflow: auto">
        <!-- Provider Selection - Primary Choice -->
        <div class="text-subtitle1 q-mb-sm text-weight-medium">Provider</div>
        <div class="row q-gutter-md q-mb-md">
          <q-select
            v-model="modelData.provider"
            :options="providerOptions"
            label="Provider"
            outlined
            dense
            emit-value
            map-options
            class="col-4"
            @update:model-value="handleProviderChange"
          >
            <template #prepend>
              <q-icon name="cloud" />
            </template>
          </q-select>
          <q-select
            v-if="modelData.provider === 'local_companion'"
            v-model="selectedLocalCompanionRunner"
            :options="localCompanionRunnerOptions"
            label="Local Runner"
            outlined
            dense
            emit-value
            map-options
            class="col-3"
          />
        </div>

        <!-- Provider Parameters - Right after provider selection -->
        <template v-if="hasProviderParameters">
          <div class="q-pa-md bg-grey-2 rounded-borders q-mb-md">
            <div class="text-subtitle2 q-mb-sm">
              {{ providerOptions.find((p) => p.value === modelData.provider)?.label }} Settings
            </div>
            <div class="row q-gutter-md items-center">
              <template v-for="field in currentPreset?.parameterSchema" :key="field.id">
                <!-- Boolean field (checkbox/toggle) -->
                <q-toggle
                  v-if="field.type === 'boolean' && isFieldVisible(field)"
                  :model-value="getProviderParamValue(field) as boolean"
                  :label="field.label"
                  dense
                  class="col-auto"
                  @update:model-value="setProviderParamValue(field, $event)"
                >
                  <q-tooltip v-if="field.helpText">{{ field.helpText }}</q-tooltip>
                </q-toggle>

                <!-- Select field (dropdown) -->
                <q-select
                  v-if="field.type === 'select' && isFieldVisible(field)"
                  :model-value="getProviderParamValue(field)"
                  :options="field.options"
                  option-value="value"
                  option-label="label"
                  emit-value
                  map-options
                  :label="field.label"
                  outlined
                  dense
                  class="col-3"
                  @update:model-value="setProviderParamValue(field, $event)"
                >
                  <template v-if="field.helpText" #hint>
                    {{ field.helpText }}
                  </template>
                </q-select>

                <!-- Number field -->
                <q-input
                  v-if="field.type === 'number' && isFieldVisible(field)"
                  :model-value="getProviderParamValue(field) as number"
                  type="number"
                  :label="field.label"
                  outlined
                  dense
                  class="col-2"
                  :hint="field.helpText"
                  @update:model-value="setProviderParamValue(field, Number($event))"
                />

                <!-- String field -->
                <q-input
                  v-if="field.type === 'string' && isFieldVisible(field)"
                  :model-value="getProviderParamValue(field) as string"
                  :label="field.label"
                  outlined
                  dense
                  class="col-3"
                  :hint="field.helpText"
                  @update:model-value="setProviderParamValue(field, $event)"
                />
              </template>
            </div>
          </div>
        </template>

        <q-separator class="q-my-md" />

        <!-- Model Identity -->
        <div class="text-subtitle1 q-mb-sm">Model Identity</div>
        <div class="row q-gutter-md q-mb-md">
          <q-input
            v-model="modelData.id"
            label="Model ID"
            outlined
            dense
            class="col"
            hint="Unique identifier (e.g. gpt-4o, llama3:latest)"
          />
          <q-input v-model="modelData.name" label="Display Name" outlined dense class="col" />
        </div>

        <div class="row q-gutter-md q-mb-md">
          <q-select
            v-model="modelData.family"
            :options="familyOptions"
            option-label="name"
            option-value="id"
            emit-value
            map-options
            label="Model Family"
            outlined
            dense
            class="col"
            @update:model-value="handleFamilyChange"
          />
          <q-select
            v-model="modelData.version"
            :options="versionOptions"
            label="Version"
            outlined
            dense
            emit-value
            map-options
            class="col"
            :disable="!modelData.family"
          />
          <q-input
            v-model.number="modelData.contextWindow"
            label="Context Window"
            type="number"
            outlined
            dense
            class="col"
          />
        </div>

        <div class="row q-gutter-sm q-mb-md items-center">
          <span class="text-caption text-grey-7 q-mr-sm">Capabilities:</span>
          <q-checkbox v-model="modelData.capabilities.jsonMode" label="JSON Mode" dense />
          <q-checkbox
            v-model="modelData.capabilities.functionCalling"
            label="Function Calling"
            dense
          />
          <q-checkbox v-model="modelData.capabilities.streaming" label="Streaming" dense />
          <q-checkbox v-model="modelData.capabilities.vision" label="Vision" dense />
        </div>

        <q-separator class="q-my-md" />

        <div class="text-subtitle1 q-mb-sm">Connection Settings</div>

        <div class="row q-gutter-md q-mb-md">
          <q-input
            v-model="modelData.connection.baseUrl"
            label="Base URL"
            outlined
            dense
            class="col"
            :disable="modelData.provider === 'local_companion'"
            :hint="getBaseUrlHint(modelData.provider)"
          />
          <q-input
            v-model="modelData.connection.path"
            label="API Path"
            outlined
            dense
            class="col-4"
            :disable="modelData.provider === 'local_companion'"
            :hint="getPathHint(modelData.provider)"
          />
        </div>

        <div class="row q-gutter-md q-mb-md">
          <q-select
            v-model="authType"
            :options="authOptions"
            label="Authentication"
            outlined
            dense
            emit-value
            map-options
            class="col-3"
            @update:model-value="handleAuthTypeChange"
          >
            <template v-if="currentPreset?.authDefaults?.[authType]?.helpText" #hint>
              {{ currentPreset?.authDefaults?.[authType]?.helpText }}
            </template>
          </q-select>
          <template v-if="authType === 'bearer'">
            <q-input
              v-model="apiKeyInput"
              label="API Key"
              outlined
              dense
              :type="showApiKey ? 'text' : 'password'"
              class="col"
            >
              <template #append>
                <q-icon
                  :name="showApiKey ? 'visibility_off' : 'visibility'"
                  class="cursor-pointer"
                  @click="showApiKey = !showApiKey"
                />
              </template>
            </q-input>
          </template>
          <template v-if="authType === 'header'">
            <q-input
              v-model="headerName"
              label="Header Name"
              outlined
              dense
              class="col-3"
              hint="e.g., x-goog-api-key, Authorization"
            />
            <q-input
              v-model="headerValue"
              label="Header Value"
              outlined
              dense
              :type="showApiKey ? 'text' : 'password'"
              class="col"
            >
              <template #append>
                <q-icon
                  :name="showApiKey ? 'visibility_off' : 'visibility'"
                  class="cursor-pointer"
                  @click="showApiKey = !showApiKey"
                />
              </template>
            </q-input>
          </template>
          <template v-if="authType === 'query_param'">
            <q-input
              v-model="queryParamName"
              label="Parameter Name"
              outlined
              dense
              class="col-3"
              hint="e.g., key, api_key"
            />
            <q-input
              v-model="queryParamValue"
              label="Parameter Value"
              outlined
              dense
              :type="showApiKey ? 'text' : 'password'"
              class="col"
            >
              <template #append>
                <q-icon
                  :name="showApiKey ? 'visibility_off' : 'visibility'"
                  class="cursor-pointer"
                  @click="showApiKey = !showApiKey"
                />
              </template>
            </q-input>
          </template>
          <template v-if="authType === 'multi_header'">
            <div class="col">
              <div
                v-for="(header, index) in multiHeaders"
                :key="index"
                class="row q-gutter-sm q-mb-sm"
              >
                <q-input
                  v-model="header.name"
                  label="Header Name"
                  outlined
                  dense
                  class="col-4"
                  :hint="index === 0 ? 'e.g., Authorization, HTTP-Referer' : ''"
                />
                <q-input
                  v-model="header.value"
                  label="Header Value"
                  outlined
                  dense
                  :type="showApiKey ? 'text' : 'password'"
                  class="col"
                >
                  <template #append>
                    <q-icon
                      v-if="index === multiHeaders.length - 1"
                      :name="showApiKey ? 'visibility_off' : 'visibility'"
                      class="cursor-pointer"
                      @click="showApiKey = !showApiKey"
                    />
                    <q-btn
                      v-if="multiHeaders.length > 1"
                      flat
                      round
                      dense
                      icon="delete"
                      color="negative"
                      @click="removeMultiHeader(index)"
                    />
                  </template>
                </q-input>
              </div>
              <q-btn
                flat
                dense
                icon="add"
                label="Add Header"
                color="primary"
                @click="addMultiHeader"
              />
            </div>
          </template>
        </div>

        <q-banner v-if="authType !== 'none'" class="bg-warning text-dark q-mb-md" rounded>
          <template #avatar>
            <q-icon name="warning" color="dark" />
          </template>
          API keys are stored by the local companion in
          <code>~/.xeditor/models.json</code> (plaintext). Anyone with access to this machine can
          read them. Keep your API keys secure.
        </q-banner>

        <q-separator class="q-my-md" />

        <q-expansion-item
          label="Advanced: Extra Payload (JSON)"
          caption="Raw JSON parameters merged into API requests"
          dense
          header-class="text-grey-7"
        >
          <q-input
            v-model="extraPayloadJson"
            label="Extra Payload (JSON)"
            type="textarea"
            outlined
            dense
            :rows="4"
            :error="extraPayloadError !== null"
            :error-message="extraPayloadError || undefined"
            hint="For advanced use only. Provider Settings above is recommended."
            class="q-pa-md"
            style="font-family: monospace"
            @blur="validateExtraPayload"
          />
        </q-expansion-item>
      </q-card-section>

      <q-separator />

      <!-- Actions -->
      <q-card-actions align="right" class="q-pa-md">
        <q-btn flat label="Cancel" v-close-popup />
        <q-btn
          color="primary"
          :label="isNewModel ? 'Add Model' : 'Save Model'"
          @click="saveModel"
        />
      </q-card-actions>
    </q-card>
  </q-dialog>
</template>

<script setup lang="ts">
import { ref, computed, watch } from 'vue';
import { useQuasar } from 'quasar';
import { useAiConfigStore } from '../../stores/aiConfig';
import { useLocalCompanionStore } from '../../stores/localCompanion';
import type {
  ModelConfig,
  ModelProviderId,
  ModelAuthType,
  LocalCompanionRunner,
  ProviderPreset,
  ProviderPresetsResponse,
  ProviderDefinition,
  ProviderParameterSchemaField,
} from '../../core/types';

const props = defineProps<{
  modelValue: boolean;
  modelToEdit: ModelConfig | null;
}>();

const emit = defineEmits<{
  'update:modelValue': [value: boolean];
  saved: [];
}>();

const $q = useQuasar();
const aiConfig = useAiConfigStore();
const companionStore = useLocalCompanionStore();

const dialogOpen = computed({
  get: () => props.modelValue,
  set: (val) => emit('update:modelValue', val),
});

const isNewModel = computed(() => !props.modelToEdit);

// Form state
const modelData = ref<ModelConfig>(createEmptyModel());
const showApiKey = ref(false);
const apiKeyInput = ref('');
const headerName = ref('');
const headerValue = ref('');
const queryParamName = ref('');
const queryParamValue = ref('');
const multiHeaders = ref<Array<{ name: string; value: string }>>([{ name: '', value: '' }]);
const authType = ref<ModelAuthType>('none');
const currentPreset = ref<ProviderPreset | null>(null);
const extraPayloadJson = ref('');
const extraPayloadError = ref<string | null>(null);
const authOptions = ref<{ label: string; value: ModelAuthType }[]>([
  { label: 'None', value: 'none' },
  { label: 'Bearer Token', value: 'bearer' },
  { label: 'Custom Header', value: 'header' },
]);

const localCompanionRunnerOptions: { label: string; value: LocalCompanionRunner }[] = [
  { label: 'vLLM (route to local server)', value: 'vllm' },
];

const selectedLocalCompanionRunner = computed<LocalCompanionRunner>({
  get() {
    if (modelData.value.provider !== 'local_companion') return 'vllm';
    return modelData.value.localCompanion?.runner ?? 'vllm';
  },
  set(val) {
    if (modelData.value.provider !== 'local_companion') return;
    if (!modelData.value.localCompanion) {
      modelData.value.localCompanion = { runner: val };
      return;
    }
    modelData.value.localCompanion.runner = val;
  },
});


// Server-provided provider list
const serverProviders = ref<ProviderDefinition[]>([]);

// Computed provider options - use server list if available, fallback otherwise
const providerOptions = computed(() => {
  if (serverProviders.value.length > 0) {
    return serverProviders.value.map((p) => ({
      label: p.label,
      value: p.id,
    }));
  }
  return [];
});

// Fetch provider preset when provider/family/baseUrl changes
async function fetchProviderPreset() {
  if (!companionStore.isConnected) {
    currentPreset.value = null;
    return;
  }

  try {
    const response = await companionStore.request<ProviderPresetsResponse>(
      'list_provider_presets',
      {
        provider: modelData.value.provider,
        baseUrl: modelData.value.connection.baseUrl,
        family: modelData.value.family,
      },
    );

    // Update server providers list if provided
    if (response.success && response.providers) {
      serverProviders.value = response.providers;
    }

    if (response.success && response.preset) {
      currentPreset.value = response.preset;
      updateAuthOptionsFromPreset(response.preset);
      applyPresetDefaults(response.preset);
    } else {
      currentPreset.value = null;
      // For openai_compatible (generic), show all auth types
      // For other providers without presets, show common options
      if (modelData.value.provider === 'openai_compatible') {
        authOptions.value = [
          { label: 'None', value: 'none' },
          { label: 'Bearer Token', value: 'bearer' },
          { label: 'Custom Header', value: 'header' },
          { label: 'Query Parameter', value: 'query_param' },
          { label: 'Multiple Headers', value: 'multi_header' },
        ];
      } else {
        // Default options for providers without presets
        authOptions.value = [
          { label: 'None', value: 'none' },
          { label: 'Bearer Token', value: 'bearer' },
          { label: 'Custom Header', value: 'header' },
        ];
      }
    }
  } catch (error) {
    console.warn('Failed to fetch provider preset:', error);
    currentPreset.value = null;
  }
}

function updateAuthOptionsFromPreset(preset: ProviderPreset) {
  if (!preset.supportedAuthTypes) {
    return;
  }

  const options: { label: string; value: ModelAuthType }[] = [];
  const labels: Record<ModelAuthType, string> = {
    none: 'None',
    bearer: 'Bearer Token',
    header: 'Custom Header',
    query_param: 'Query Parameter',
    multi_header: 'Multiple Headers',
  };

  preset.supportedAuthTypes.forEach((type: ModelAuthType) => {
    if (labels[type]) {
      options.push({ label: labels[type], value: type });
    }
  });

  if (options.length > 0) {
    authOptions.value = options;
  }
}

function applyPresetDefaults(preset: ProviderPreset) {
  if (!preset.authDefaults || !preset.defaultAuthType) {
    return;
  }

  const defaultType = preset.defaultAuthType;
  const defaults = preset.authDefaults[defaultType];

  if (defaultType === 'header' && defaults?.headerName) {
    // Apply default header name if not already set
    if (!headerName.value || headerName.value === 'Authorization') {
      headerName.value = defaults.headerName;
    }
  }

  // Set default auth type if current is 'none' or not in supported types
  if (authType.value === 'none' || !preset.supportedAuthTypes?.includes(authType.value)) {
    authType.value = defaultType;
    handleAuthTypeChange(defaultType);
  }

  // Apply provider parameter defaults if not already set
  if (preset.parameterDefaults && !modelData.value.providerParams) {
    modelData.value.providerParams = JSON.parse(JSON.stringify(preset.parameterDefaults));
  }
}

const familyOptions = computed(() => {
  return aiConfig.modelFamilyRegistry.map((family) => ({
    id: family.id,
    name: `${family.name} (${family.id})`,
  }));
});

const versionOptions = computed(() => {
  if (!modelData.value.family) {
    return [];
  }
  const family = aiConfig.modelFamilyRegistry.find((f) => f.id === modelData.value.family);
  if (!family) {
    return [];
  }
  return family.versions.map((version) => ({
    label: version,
    value: version,
  }));
});

function createEmptyModel(): ModelConfig {
  return {
    id: '',
    provider: 'openai_compatible',
    family: '',
    name: '',
    version: '',
    contextWindow: 8192,
    capabilities: {
      jsonMode: false,
      functionCalling: false,
      streaming: true,
    },
    connection: {
      baseUrl: '',
      path: '/v1/chat/completions',
      auth: { type: 'none' },
    },
  };
}

// ─────────────────────────────────────────────────────────────────────────────
// Provider Parameter Helpers
// ─────────────────────────────────────────────────────────────────────────────

/**
 * Get a nested value from an object using dot notation path (e.g., "reasoning.enabled")
 */
function getNestedValue(obj: Record<string, unknown>, path: string): unknown {
  const parts = path.split('.');
  let current: unknown = obj;
  for (const part of parts) {
    if (current === null || current === undefined || typeof current !== 'object') {
      return undefined;
    }
    current = (current as Record<string, unknown>)[part];
  }
  return current;
}

/**
 * Set a nested value in an object using dot notation path (e.g., "reasoning.enabled")
 */
function setNestedValue(obj: Record<string, unknown>, path: string, value: unknown): void {
  const parts = path.split('.');
  let current: Record<string, unknown> = obj;
  for (let i = 0; i < parts.length - 1; i++) {
    const part = parts[i] as string;
    if (!(part in current) || typeof current[part] !== 'object' || current[part] === null) {
      current[part] = {};
    }
    current = current[part] as Record<string, unknown>;
  }
  const lastPart = parts[parts.length - 1] as string;
  current[lastPart] = value;
}

/**
 * Check if a parameter field should be visible based on its dependsOn condition
 */
function isFieldVisible(field: ProviderParameterSchemaField): boolean {
  if (!field.dependsOn) return true;
  const dependsOnValue = getNestedValue(
    modelData.value.providerParams || {},
    field.dependsOn.field,
  );
  return dependsOnValue === field.dependsOn.value;
}

/**
 * Get the current value for a provider parameter field
 */
function getProviderParamValue(field: ProviderParameterSchemaField): unknown {
  const params = modelData.value.providerParams || {};
  const value = getNestedValue(params, field.id);
  return value !== undefined ? value : field.default;
}

/**
 * Set the value for a provider parameter field
 */
function setProviderParamValue(field: ProviderParameterSchemaField, value: unknown): void {
  if (!modelData.value.providerParams) {
    modelData.value.providerParams = {};
  }
  setNestedValue(modelData.value.providerParams, field.id, value);
}

/**
 * Check if we should show the provider parameters section
 */
const hasProviderParameters = computed(() => {
  return currentPreset.value?.parameterSchema && currentPreset.value.parameterSchema.length > 0;
});

// Validate and sync extraPayload JSON
function validateExtraPayload(): boolean {
  if (!extraPayloadJson.value.trim()) {
    extraPayloadError.value = null;
    return true;
  }

  try {
    const parsed = JSON.parse(extraPayloadJson.value);
    if (typeof parsed !== 'object' || parsed === null || Array.isArray(parsed)) {
      extraPayloadError.value = 'Must be a JSON object';
      return false;
    }
    extraPayloadError.value = null;
    return true;
  } catch (err) {
    extraPayloadError.value = 'Invalid JSON: ' + (err instanceof Error ? err.message : String(err));
    return false;
  }
}

function syncExtraPayload() {
  if (modelData.value.extraPayload) {
    extraPayloadJson.value = JSON.stringify(modelData.value.extraPayload, null, 2);
  } else {
    extraPayloadJson.value = '';
  }
  extraPayloadError.value = null;
}

// Reset form when dialog opens
watch(
  () => props.modelValue,
  async (open) => {
    if (open) {
      if (props.modelToEdit) {
        modelData.value = JSON.parse(JSON.stringify(props.modelToEdit)) as ModelConfig;
        if (modelData.value.provider === 'local_companion' && !modelData.value.localCompanion) {
          modelData.value.localCompanion = { runner: 'vllm' };
        }
        syncAuthFields();
        syncExtraPayload();
        await fetchProviderPreset();
      } else {
        modelData.value = createEmptyModel();
        authType.value = 'none';
        apiKeyInput.value = '';
        headerName.value = '';
        headerValue.value = '';
        queryParamName.value = '';
        queryParamValue.value = '';
        multiHeaders.value = [{ name: '', value: '' }];
        extraPayloadJson.value = '';
        extraPayloadError.value = null;
        await fetchProviderPreset();
      }
      showApiKey.value = false;
    }
  },
);

// Watch for provider/family/baseUrl changes to refetch presets
watch(
  () => [modelData.value.provider, modelData.value.family, modelData.value.connection.baseUrl],
  async () => {
    if (props.modelValue) {
      await fetchProviderPreset();
    }
  },
);

function syncAuthFields() {
  const auth = modelData.value.connection.auth;
  authType.value = auth.type;
  if (auth.type === 'bearer') {
    apiKeyInput.value = auth.apiKey || '';
  } else if (auth.type === 'header') {
    headerName.value = auth.headerName;
    headerValue.value = auth.value || '';
  } else if (auth.type === 'query_param') {
    queryParamName.value = auth.paramName || '';
    queryParamValue.value = auth.value || '';
  } else if (auth.type === 'multi_header') {
    multiHeaders.value = auth.headers?.length
      ? auth.headers.map((h: { name: string; value?: string }) => ({
          name: h.name,
          value: h.value || '',
        }))
      : [{ name: '', value: '' }];
  } else {
    apiKeyInput.value = '';
    headerName.value = '';
    headerValue.value = '';
    queryParamName.value = '';
    queryParamValue.value = '';
    multiHeaders.value = [{ name: '', value: '' }];
  }
}

function addMultiHeader() {
  multiHeaders.value.push({ name: '', value: '' });
}

function removeMultiHeader(index: number) {
  if (multiHeaders.value.length > 1) {
    multiHeaders.value.splice(index, 1);
  }
}

function handleFamilyChange(familyId: string) {
  modelData.value.family = familyId;
  modelData.value.version = '';
}

function getBaseUrlHint(provider: ModelProviderId): string {
  const hints: Record<ModelProviderId, string> = {
    openai: 'https://api.openai.com',
    anthropic: 'https://api.anthropic.com',
    ollama: 'http://localhost:11434',
    lmstudio: 'http://localhost:1234',
    vllm: 'http://localhost:8000',
    sglang: 'http://localhost:30000',
    openai_compatible: 'Your server URL',
    local_companion: 'Handled by Companion Store',
  };
  return hints[provider] || '';
}

function getPathHint(provider: ModelProviderId): string {
  const hints: Record<ModelProviderId, string> = {
    openai: '/v1/chat/completions',
    anthropic: '/v1/messages',
    ollama: '/api/chat',
    lmstudio: '/v1/chat/completions',
    vllm: '/v1/chat/completions',
    sglang: '/v1/chat/completions',
    openai_compatible: '/v1/chat/completions',
    local_companion: '/ws',
  };
  return hints[provider] || '';
}

async function handleProviderChange(provider: ModelProviderId) {
  // Clear provider params when switching providers (will be repopulated from preset defaults)
  delete modelData.value.providerParams;

  if (provider === 'local_companion') {
    authType.value = 'none';
    modelData.value.connection.auth = { type: 'none' };
    modelData.value.connection.baseUrl = '';
    modelData.value.connection.path = '';
    if (!modelData.value.localCompanion) {
      modelData.value.localCompanion = { runner: 'vllm' };
    }
    currentPreset.value = null;
    return;
  }

  // Non-companion providers: clear companion-only settings
  if (modelData.value.localCompanion) {
    delete modelData.value.localCompanion;
  }

  modelData.value.connection.baseUrl = getBaseUrlHint(provider);
  modelData.value.connection.path = getPathHint(provider);

  // Fetch preset which will apply defaults (including provider params)
  await fetchProviderPreset();

  // Fallback defaults if no preset found
  if (!currentPreset.value) {
    if (provider === 'openai' || provider === 'anthropic') {
      authType.value = 'bearer';
      modelData.value.connection.auth = { type: 'bearer' };
    } else if (provider === 'ollama' || provider === 'lmstudio') {
      authType.value = 'none';
      modelData.value.connection.auth = { type: 'none' };
    }
  }
}

function handleAuthTypeChange(type: ModelAuthType) {
  if (type === 'none') {
    modelData.value.connection.auth = { type: 'none' };
  } else if (type === 'bearer') {
    modelData.value.connection.auth = { type: 'bearer', apiKey: apiKeyInput.value };
  } else if (type === 'header') {
    modelData.value.connection.auth = {
      type: 'header',
      headerName: headerName.value || 'Authorization',
      value: headerValue.value,
    };
  } else if (type === 'query_param') {
    modelData.value.connection.auth = {
      type: 'query_param',
      paramName: queryParamName.value || 'key',
      value: queryParamValue.value,
    };
  } else if (type === 'multi_header') {
    modelData.value.connection.auth = {
      type: 'multi_header',
      headers: multiHeaders.value
        .filter((h) => h.name) // Only include headers with names
        .map((h) => ({ name: h.name, value: h.value })),
    };
  }
}

async function saveModel() {
  // Validate extraPayload JSON
  if (!validateExtraPayload()) {
    $q.notify({ type: 'negative', message: 'Invalid extra payload JSON' });
    return;
  }

  // Update auth from input fields
  if (authType.value === 'bearer') {
    const auth: { type: 'bearer'; apiKey?: string } = { type: 'bearer' };
    if (apiKeyInput.value) {
      auth.apiKey = apiKeyInput.value;
    }
    modelData.value.connection.auth = auth;
  } else if (authType.value === 'header') {
    const auth: { type: 'header'; headerName: string; value?: string } = {
      type: 'header',
      headerName: headerName.value || 'Authorization',
    };
    if (headerValue.value) {
      auth.value = headerValue.value;
    }
    modelData.value.connection.auth = auth;
  } else if (authType.value === 'query_param') {
    const auth: { type: 'query_param'; paramName: string; value?: string } = {
      type: 'query_param',
      paramName: queryParamName.value || 'key',
    };
    if (queryParamValue.value) {
      auth.value = queryParamValue.value;
    }
    modelData.value.connection.auth = auth;
  } else if (authType.value === 'multi_header') {
    const auth: { type: 'multi_header'; headers: Array<{ name: string; value?: string }> } = {
      type: 'multi_header',
      headers: multiHeaders.value
        .filter((h) => h.name) // Only include headers with names
        .map((h) => ({ name: h.name, value: h.value })),
    };
    modelData.value.connection.auth = auth;
  }

  // Update extraPayload from JSON input
  let extraPayloadValue: Record<string, unknown> | undefined;
  if (extraPayloadJson.value.trim()) {
    try {
      extraPayloadValue = JSON.parse(extraPayloadJson.value) as Record<string, unknown>;
      modelData.value.extraPayload = extraPayloadValue;
    } catch (_e) {
      // Should not happen since we validated above, but just in case
      $q.notify({ type: 'negative', message: 'Failed to parse extra payload JSON' });
      return;
    }
  } else {
    // Clear extraPayload if JSON is empty
    extraPayloadValue = undefined;
    delete modelData.value.extraPayload;
  }

  if (isNewModel.value) {
    if (!modelData.value.id) {
      $q.notify({ type: 'negative', message: 'Model ID is required' });
      return;
    }
    await aiConfig.addModel(modelData.value);
    $q.notify({ type: 'positive', message: 'Model added' });
  } else {
    // For updates, use the original model ID from props.modelToEdit
    // This ensures we can find the original record even if the ID was changed
    const originalModelId = props.modelToEdit?.id;
    if (!originalModelId) {
      $q.notify({ type: 'negative', message: 'Original model ID not found' });
      return;
    }

    // For updates, explicitly include extraPayload and providerParams so they can be cleared if needed
    const updates: Partial<ModelConfig> = {
      ...modelData.value,
    };
    // Explicitly set extraPayload to handle clearing case - use type assertion to allow undefined
    (updates as Record<string, unknown>).extraPayload = extraPayloadValue;
    // Explicitly set providerParams to handle clearing case
    (updates as Record<string, unknown>).providerParams = modelData.value.providerParams;
    await aiConfig.updateModel(originalModelId, updates);
    $q.notify({ type: 'positive', message: 'Model updated' });
  }

  emit('saved');
  dialogOpen.value = false;
}
</script>
