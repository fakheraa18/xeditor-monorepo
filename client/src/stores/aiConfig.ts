import { defineStore } from 'pinia';
import { ref, computed, toRaw } from 'vue';
import type {
  Mode,
  ModelConfig,
  PromptTemplate,
  AiConfigRecord,
  ModeTooling,
  PromptSetMetadata,
  PromptSetStructure,
} from '../core/types';
import { getAiConfig, putAiConfig } from '../core/persistence/indexedDb';
import { useLocalCompanionStore } from './localCompanion';

/**
 * Fetch models from local companion
 */
async function fetchModelsFromCompanion(): Promise<ModelConfig[]> {
  const companionStore = useLocalCompanionStore();

  if (!companionStore.isConnected) {
    return [];
  }

  try {
    const response = await companionStore.request<{
      success: boolean;
      models?: ModelConfig[];
      error?: string;
    }>('list_models', {});

    if (response.success && response.models && response.models.length > 0) {
      return response.models;
    }
  } catch (error) {
    console.warn('Failed to fetch models from companion:', error);
  }

  return [];
}

/**
 * Fetch prompt templates from local companion
 */
async function fetchPromptsFromCompanion(): Promise<PromptTemplate[]> {
  const companionStore = useLocalCompanionStore();

  if (!companionStore.isConnected) {
    return [];
  }

  try {
    const response = await companionStore.request<{
      success: boolean;
      templates: Array<{
        id: string;
        mode: Mode;
        target: { family?: string; version?: string };
        systemPrompt: string;
        parameters: { temperature: number; maxTokens?: number };
      }>;
    }>('list_prompts', {});

    if (response.success && response.templates.length > 0) {
      return response.templates.map((t) => ({
        id: t.id,
        mode: t.mode,
        target: t.target,
        systemPrompt: t.systemPrompt,
        parameters: {
          temperature: t.parameters.temperature,
          maxTokens: t.parameters.maxTokens,
        },
      }));
    }
  } catch (error) {
    console.warn('Failed to fetch prompts from companion:', error);
  }

  return [];
}

/**
 * Fetch model families from local companion
 */
export interface ModelFamily {
  id: string;
  name: string;
  versions: string[];
}

async function fetchFamiliesFromCompanion(): Promise<ModelFamily[]> {
  const companionStore = useLocalCompanionStore();

  if (!companionStore.isConnected) {
    return [];
  }

  try {
    const response = await companionStore.request<{
      success: boolean;
      families?: ModelFamily[];
      error?: string;
    }>('list_families', {});

    if (response.success && response.families && response.families.length > 0) {
      return response.families;
    }
  } catch (error) {
    console.warn('Failed to fetch families from companion:', error);
  }

  return [];
}

// ─────────────────────────────────────────────────────────────────────────────
// Default Set Metadata
// ─────────────────────────────────────────────────────────────────────────────

const DEFAULT_SET_METADATA: PromptSetMetadata = {
  id: 'default',
  name: 'XEditor Default',
  author: 'XEditor',
  version: '1.0.0',
  description: 'Built-in default prompt set',
  modes: ['plan', 'ask', 'agent', 'debug'],
  family: 'all',
  families: ['gpt', 'claude', 'llama'],
  isBuiltIn: true,
};

// ─────────────────────────────────────────────────────────────────────────────
// Default Mode Tooling
// ─────────────────────────────────────────────────────────────────────────────

const DEFAULT_MODE_TOOLING: Record<Mode, ModeTooling> = {
  plan: { toolIds: [], mcpServerIds: [] },
  ask: { toolIds: [], mcpServerIds: [] },
  agent: { toolIds: ['read_file', 'search_code'], mcpServerIds: [] },
  debug: { toolIds: ['read_file'], mcpServerIds: [] },
};

// ─────────────────────────────────────────────────────────────────────────────
// Store
// ─────────────────────────────────────────────────────────────────────────────

export const useAiConfigStore = defineStore('aiConfig', () => {
  const isInitialized = ref(false);
  const isLoading = ref(false);

  // State
  const activeMode = ref<Mode>('ask');
  const activeModelId = ref<string>('gpt-5.2');
  const activeSetId = ref<string>('default');
  const debugEnabled = ref<boolean>(false);
  const models = ref<ModelConfig[]>([]);
  const promptTemplates = ref<PromptTemplate[]>([]);
  const modeTooling = ref<Record<Mode, ModeTooling>>(DEFAULT_MODE_TOOLING);
  const availableSets = ref<PromptSetMetadata[]>([DEFAULT_SET_METADATA]);
  const availableModes = ref<string[]>(['plan', 'ask', 'agent', 'debug']);
  const modelFamilyRegistry = ref<ModelFamily[]>([]);

  // Computed
  const activeModel = computed(() => {
    return models.value.find((m) => m.id === activeModelId.value) || models.value[0];
  });

  const modelFamilies = computed(() => {
    const families = new Set(models.value.map((m) => m.family));
    return Array.from(families);
  });

  // ─────────────────────────────────────────────────────────────────────────
  // Initialization
  // ─────────────────────────────────────────────────────────────────────────

  async function initialize(): Promise<void> {
    if (isInitialized.value) return;
    isLoading.value = true;

    try {
      const config = await getAiConfig();

      // Load user selections from IndexedDB
      if (config) {
        activeMode.value = config.activeMode;
        activeModelId.value = config.activeModelId;
        activeSetId.value = config.activeSetId || 'default';
        debugEnabled.value = config.debugEnabled ?? false;
        modeTooling.value = config.modeTooling;
      }

      // Always fetch models and prompts from backend
      const companionStore = useLocalCompanionStore();
      if (companionStore.isConnected) {
        // Fetch models from backend
        const backendModels = await fetchModelsFromCompanion();
        if (backendModels.length > 0) {
          models.value = backendModels;
        }

        // Fetch prompts from backend
        const backendPrompts = await fetchPromptsFromCompanion();
        if (backendPrompts.length > 0) {
          promptTemplates.value = backendPrompts;
        }

        // Load sets and modes
        await loadSets();
        await loadModes();

        // Load model families
        const families = await fetchFamiliesFromCompanion();
        if (families.length > 0) {
          modelFamilyRegistry.value = families;
        }

        // Validate active model ID still exists
        if (activeModelId.value && !models.value.some((m) => m.id === activeModelId.value)) {
          const firstModel = models.value[0];
          if (firstModel) {
            activeModelId.value = firstModel.id;
          } else {
            activeModelId.value = '';
          }
        }

        // Persist updated selections
        await persist();
      } else {
        // When disconnected, ensure we have at least empty arrays
        models.value = [];
        promptTemplates.value = [];
        // Keep default set metadata for UI
        const hasDefault = availableSets.value.some((s) => s.id === 'default');
        if (!hasDefault) {
          availableSets.value = [DEFAULT_SET_METADATA];
        }
      }

      isInitialized.value = true;
    } finally {
      isLoading.value = false;
    }
  }

  async function persist(): Promise<void> {
    // Only persist user selections, not full model/template lists
    // Models and templates are now managed by the backend
    const config: AiConfigRecord = {
      id: 'global',
      activeMode: activeMode.value,
      activeModelId: activeModelId.value,
      activeSetId: activeSetId.value,
      debugEnabled: debugEnabled.value,
      modeTooling: JSON.parse(JSON.stringify(toRaw(modeTooling.value))),
      updatedAt: Date.now(),
    };
    await putAiConfig(config);
  }

  async function resetToDefaults(): Promise<void> {
    activeMode.value = 'ask';
    activeSetId.value = 'default';
    modeTooling.value = { ...DEFAULT_MODE_TOOLING };

    // Call backend reset endpoint
    const companionStore = useLocalCompanionStore();
    if (companionStore.isConnected) {
      try {
        // Reset both models and prompts on backend
        const response = await companionStore.request<{
          success: boolean;
          models?: { success: boolean; error?: string };
          prompts?: { success: boolean; error?: string };
          error?: string;
        }>('reset_all_to_defaults', {});

        if (!response.success) {
          throw new Error(response.error || 'Failed to reset to defaults');
        }

        // Reload models and prompts from backend after reset
        const backendModels = await fetchModelsFromCompanion();
        if (backendModels.length > 0) {
          models.value = backendModels;
          const firstModel = backendModels[0];
          if (firstModel) {
            activeModelId.value = firstModel.id;
          } else {
            activeModelId.value = '';
          }
        } else {
          activeModelId.value = '';
        }

        const backendPrompts = await fetchPromptsFromCompanion();
        if (backendPrompts.length > 0) {
          promptTemplates.value = backendPrompts;
        }

        await loadSets();
        await loadModes();
      } catch (error) {
        console.error('Failed to reset to defaults:', error);
        throw error;
      }
    } else {
      models.value = [];
      promptTemplates.value = [];
      activeModelId.value = '';
    }

    await persist();
  }

  // ─────────────────────────────────────────────────────────────────────────
  // Mode & Model Selection
  // ─────────────────────────────────────────────────────────────────────────

  async function setActiveMode(mode: Mode): Promise<void> {
    activeMode.value = mode;
    await persist();
  }

  async function setActiveModel(modelId: string): Promise<void> {
    if (models.value.some((m) => m.id === modelId)) {
      activeModelId.value = modelId;
      await persist();
    }
  }

  async function setDebugEnabled(enabled: boolean): Promise<void> {
    debugEnabled.value = enabled;
    await persist();
  }

  // ─────────────────────────────────────────────────────────────────────────
  // Prompt Resolution (cascade: version > family > mode default)
  // ─────────────────────────────────────────────────────────────────────────

  async function resolvePrompt(mode: Mode, model: ModelConfig): Promise<PromptTemplate> {
    // Try to resolve from companion first (with set support)
    const companionStore = useLocalCompanionStore();

    if (companionStore.isConnected) {
      try {
        const response = await companionStore.request<{
          success: boolean;
          template?: PromptTemplate;
          error?: string;
        }>('resolve_prompt', {
          mode,
          family: model.family,
          version: model.version,
          setId: activeSetId.value,
        });

        if (response.success && response.template) {
          return response.template;
        }
      } catch (error) {
        console.warn('Failed to resolve prompt from companion:', error);
      }
    }

    // Fallback to local templates
    const candidates = [
      // 1. Version-specific
      promptTemplates.value.find(
        (t) =>
          t.mode === mode && t.target.family === model.family && t.target.version === model.version,
      ),
      // 2. Family-specific
      promptTemplates.value.find(
        (t) => t.mode === mode && t.target.family === model.family && !t.target.version,
      ),
      // 3. Mode default
      promptTemplates.value.find((t) => t.mode === mode && !t.target.family),
      // 4. Fallback to ask-default
      promptTemplates.value.find((t) => t.mode === 'ask' && !t.target.family),
    ];

    const resolved = candidates.find((t) => t !== undefined);
    if (!resolved) {
      throw new Error(`No prompt template found for mode: ${mode}, model: ${model.id}`);
    }

    return resolved;
  }

  // ─────────────────────────────────────────────────────────────────────────
  // Model CRUD
  // ─────────────────────────────────────────────────────────────────────────

  async function addModel(model: ModelConfig): Promise<void> {
    const companionStore = useLocalCompanionStore();

    if (!companionStore.isConnected) {
      throw new Error('Local companion not connected');
    }

    const response = await companionStore.request<{
      success: boolean;
      model?: ModelConfig;
      error?: string;
    }>('save_model', model);

    if (!response.success) {
      throw new Error(response.error || 'Failed to save model');
    }

    // Refresh models from backend
    const backendModels = await fetchModelsFromCompanion();
    if (backendModels.length > 0) {
      models.value = backendModels;
    }
  }

  async function updateModel(modelId: string, updates: Partial<ModelConfig>): Promise<void> {
    const companionStore = useLocalCompanionStore();

    if (!companionStore.isConnected) {
      throw new Error('Local companion not connected');
    }

    const existing = models.value.find((m) => m.id === modelId);
    if (!existing) {
      throw new Error(`Model not found: ${modelId}`);
    }

    const updated: ModelConfig = {
      id: updates.id ?? existing.id,
      provider: updates.provider ?? existing.provider,
      family: updates.family ?? existing.family,
      name: updates.name ?? existing.name,
      contextWindow: updates.contextWindow ?? existing.contextWindow,
      capabilities: updates.capabilities ?? existing.capabilities,
      connection: updates.connection ?? existing.connection,
    };

    // Handle optional version property correctly
    if (updates.version !== undefined) {
      updated.version = updates.version;
    } else if (existing.version !== undefined) {
      updated.version = existing.version;
    }

    // Preserve optional local companion settings
    if (updates.localCompanion !== undefined) {
      updated.localCompanion = updates.localCompanion;
    } else if (existing.localCompanion !== undefined) {
      updated.localCompanion = existing.localCompanion;
    }

    // Preserve optional provider params
    // Check if key exists in updates (even if value is undefined, meaning it should be cleared)
    if ('providerParams' in updates) {
      updated.providerParams = updates.providerParams;
    } else if (existing.providerParams !== undefined) {
      updated.providerParams = existing.providerParams;
    }

    // Preserve optional extra payload parameters
    // Check if key exists in updates (even if value is undefined, meaning it should be cleared)
    if ('extraPayload' in updates) {
      updated.extraPayload = updates.extraPayload;
    } else if (existing.extraPayload !== undefined) {
      updated.extraPayload = existing.extraPayload;
    }

    // Detect if model ID has changed and attach originalId for rename logic
    const payload: ModelConfig & { originalId?: string } = updated;
    if (updates.id && updates.id !== modelId) {
      payload.originalId = modelId;
    }

    const response = await companionStore.request<{
      success: boolean;
      model?: ModelConfig;
      error?: string;
    }>('save_model', payload);

    if (!response.success) {
      throw new Error(response.error || 'Failed to update model');
    }

    // Refresh models from backend
    const backendModels = await fetchModelsFromCompanion();
    if (backendModels.length > 0) {
      models.value = backendModels;
    }
  }

  async function removeModel(modelId: string): Promise<void> {
    const companionStore = useLocalCompanionStore();

    if (!companionStore.isConnected) {
      throw new Error('Local companion not connected');
    }

    const response = await companionStore.request<{
      success: boolean;
      error?: string;
    }>('delete_model', { id: modelId });

    if (!response.success) {
      throw new Error(response.error || 'Failed to delete model');
    }

    // Refresh models from backend
    const backendModels = await fetchModelsFromCompanion();
    if (backendModels.length > 0) {
      models.value = backendModels;
      // Update active model if it was deleted
      if (activeModelId.value === modelId) {
        const firstModel = backendModels[0];
        if (firstModel) {
          activeModelId.value = firstModel.id;
        } else {
          activeModelId.value = '';
        }
        await persist();
      }
    } else {
      models.value = [];
      activeModelId.value = '';
      await persist();
    }
  }

  // ─────────────────────────────────────────────────────────────────────────
  // Prompt Template CRUD
  // ─────────────────────────────────────────────────────────────────────────

  async function upsertTemplate(template: PromptTemplate): Promise<void> {
    const companionStore = useLocalCompanionStore();

    if (!companionStore.isConnected) {
      throw new Error('Local companion not connected');
    }

    const response = await companionStore.request<{
      success: boolean;
      template?: PromptTemplate;
      error?: string;
    }>('save_prompt', template);

    if (!response.success) {
      throw new Error(response.error || 'Failed to save template');
    }

    // Refresh prompts from backend
    const backendPrompts = await fetchPromptsFromCompanion();
    if (backendPrompts.length > 0) {
      promptTemplates.value = backendPrompts;
    }
  }

  async function removeTemplate(templateId: string): Promise<void> {
    const companionStore = useLocalCompanionStore();

    if (!companionStore.isConnected) {
      throw new Error('Local companion not connected');
    }

    const response = await companionStore.request<{
      success: boolean;
      error?: string;
    }>('delete_prompt', { id: templateId });

    if (!response.success) {
      throw new Error(response.error || 'Failed to delete template');
    }

    // Refresh prompts from backend
    const backendPrompts = await fetchPromptsFromCompanion();
    if (backendPrompts.length > 0) {
      promptTemplates.value = backendPrompts;
    } else {
      promptTemplates.value = [];
    }
  }

  // ─────────────────────────────────────────────────────────────────────────
  // Mode Tooling
  // ─────────────────────────────────────────────────────────────────────────

  async function setModeTooling(mode: Mode, tooling: ModeTooling): Promise<void> {
    modeTooling.value[mode] = tooling;
    await persist();
  }

  // ─────────────────────────────────────────────────────────────────────────
  // Set Management
  // ─────────────────────────────────────────────────────────────────────────

  async function loadSets(): Promise<void> {
    const companionStore = useLocalCompanionStore();

    if (!companionStore.isConnected) {
      // Ensure default set is present when disconnected
      const hasDefault = availableSets.value.some((s) => s.id === 'default');
      if (!hasDefault) {
        availableSets.value = [DEFAULT_SET_METADATA];
      }
      return;
    }

    try {
      const response = await companionStore.request<{
        success: boolean;
        sets?: PromptSetMetadata[];
      }>('list_sets', {});

      if (response.success && response.sets && response.sets.length > 0) {
        // Merge companion sets with default set, ensuring default is always present
        const companionSets = response.sets;
        const hasDefault = companionSets.some((s) => s.id === 'default');
        if (hasDefault) {
          availableSets.value = companionSets;
        } else {
          // Prepend default set if companion doesn't provide it
          availableSets.value = [DEFAULT_SET_METADATA, ...companionSets];
        }
      } else {
        // If companion returns empty or fails, ensure default set is present
        const hasDefault = availableSets.value.some((s) => s.id === 'default');
        if (!hasDefault) {
          availableSets.value = [DEFAULT_SET_METADATA];
        }
      }
    } catch (error) {
      console.warn('Failed to load sets:', error);
      // On error, ensure default set is present
      const hasDefault = availableSets.value.some((s) => s.id === 'default');
      if (!hasDefault) {
        availableSets.value = [DEFAULT_SET_METADATA];
      }
    }
  }

  async function loadModes(): Promise<void> {
    const companionStore = useLocalCompanionStore();

    if (!companionStore.isConnected) {
      return;
    }

    try {
      const response = await companionStore.request<{
        success: boolean;
        modes?: string[];
      }>('list_modes', {});

      if (response.success && response.modes) {
        availableModes.value = response.modes;
      }
    } catch (error) {
      console.warn('Failed to load modes:', error);
    }
  }

  async function setActiveSet(setId: string): Promise<void> {
    activeSetId.value = setId;
    await loadModes(); // Reload modes for the new set
    await persist();
  }

  async function createSet(metadata: Partial<PromptSetMetadata>): Promise<void> {
    const companionStore = useLocalCompanionStore();

    if (!companionStore.isConnected) {
      throw new Error('Local companion not connected');
    }

    const response = await companionStore.request<{
      success: boolean;
      metadata?: PromptSetMetadata;
      error?: string;
    }>('create_set', metadata);

    if (!response.success) {
      throw new Error(response.error || 'Failed to create set');
    }

    await loadSets();
  }

  async function updateSet(setId: string, updates: Partial<PromptSetMetadata>): Promise<void> {
    const companionStore = useLocalCompanionStore();

    if (!companionStore.isConnected) {
      throw new Error('Local companion not connected');
    }

    const response = await companionStore.request<{
      success: boolean;
      metadata?: PromptSetMetadata;
      error?: string;
    }>('update_set', { id: setId, updates });

    if (!response.success) {
      throw new Error(response.error || 'Failed to update set');
    }

    await loadSets();
  }

  async function deleteSet(setId: string): Promise<void> {
    const companionStore = useLocalCompanionStore();

    if (!companionStore.isConnected) {
      throw new Error('Local companion not connected');
    }

    const response = await companionStore.request<{
      success: boolean;
      error?: string;
    }>('delete_set', { id: setId });

    if (!response.success) {
      throw new Error(response.error || 'Failed to delete set');
    }

    if (activeSetId.value === setId) {
      activeSetId.value = 'default';
    }

    await loadSets();
  }

  async function exportSet(setId: string): Promise<Blob> {
    const companionStore = useLocalCompanionStore();

    if (!companionStore.isConnected) {
      throw new Error('Local companion not connected');
    }

    const response = await companionStore.request<{
      success: boolean;
      archive?: string; // base64 encoded
      error?: string;
    }>('export_set', { id: setId });

    if (!response.success || !response.archive) {
      throw new Error(response.error || 'Failed to export set');
    }

    // Decode base64 to blob
    const binaryString = atob(response.archive);
    const bytes = new Uint8Array(binaryString.length);
    for (let i = 0; i < binaryString.length; i++) {
      bytes[i] = binaryString.charCodeAt(i);
    }

    return new Blob([bytes], { type: 'application/zip' });
  }

  async function importSet(file: File): Promise<void> {
    const companionStore = useLocalCompanionStore();

    if (!companionStore.isConnected) {
      throw new Error('Local companion not connected');
    }

    // Read file as base64
    const arrayBuffer = await file.arrayBuffer();
    const bytes = new Uint8Array(arrayBuffer);
    const binaryString = Array.from(bytes, (byte) => String.fromCharCode(byte)).join('');
    const archive = btoa(binaryString);

    const response = await companionStore.request<{
      success: boolean;
      metadata?: PromptSetMetadata;
      error?: string;
    }>('import_set', { archive });

    if (!response.success) {
      throw new Error(response.error || 'Failed to import set');
    }

    await loadSets();
  }

  async function getSetStructure(setId: string): Promise<PromptSetStructure | null> {
    const companionStore = useLocalCompanionStore();

    if (!companionStore.isConnected) {
      return null;
    }

    try {
      const response = await companionStore.request<{
        success: boolean;
        metadata?: PromptSetMetadata;
        structure?: PromptSetStructure['families'];
        error?: string;
      }>('get_set', { id: setId });

      if (response.success && response.metadata && response.structure) {
        return {
          metadata: response.metadata,
          families: response.structure,
        };
      }
    } catch (error) {
      console.warn('Failed to get set structure:', error);
    }

    return null;
  }

  return {
    // State
    isInitialized,
    isLoading,
    activeMode,
    activeModelId,
    activeSetId,
    debugEnabled,
    models,
    promptTemplates,
    modeTooling,
    availableSets,
    availableModes,

    // Computed
    activeModel,
    modelFamilies, // Computed property - unique families from models

    // State
    modelFamilyRegistry, // Registry from backend - families with versions

    // Actions
    initialize,
    persist,
    resetToDefaults,
    setActiveMode,
    setActiveModel,
    setDebugEnabled,
    resolvePrompt,
    addModel,
    updateModel,
    removeModel,
    upsertTemplate,
    removeTemplate,
    setModeTooling,
    loadSets,
    loadModes,
    setActiveSet,
    createSet,
    updateSet,
    deleteSet,
    exportSet,
    importSet,
    getSetStructure,
  };
});
