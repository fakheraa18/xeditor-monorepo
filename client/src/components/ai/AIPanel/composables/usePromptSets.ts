import { ref, computed, watch } from 'vue';
import { useAiConfigStore } from '../../../../stores/aiConfig';
import { useLocalCompanionStore } from '../../../../stores/localCompanion';
import type { Mode } from '../../../../core/types';

export function usePromptSets() {
  const aiConfig = useAiConfigStore();
  const companionStore = useLocalCompanionStore();

  const selectedMode = ref<Mode>('ask');
  const selectedModelId = ref<string>('');
  const selectedSetId = ref<string>('default');

  // Tools map for all sets and modes: { setId: { mode: string[] } }
  const setToolsMap = ref<Record<string, Record<string, string[]>>>({});

  const modeOptions = computed(() => {
    return aiConfig.availableModes.map((mode) => ({
      label: mode.charAt(0).toUpperCase() + mode.slice(1),
      value: mode,
    }));
  });

  const currentModeLabel = computed(() => {
    const option = modeOptions.value.find((opt) => opt.value === selectedMode.value);
    return option ? option.label : 'Mode';
  });

  const modelOptions = computed(() => aiConfig.models);

  const activeModel = computed(() => {
    return aiConfig.models.find((m) => m.id === selectedModelId.value);
  });

  const filteredSetOptions = computed(() => {
    const currentMode = selectedMode.value;
    const modelFamily = activeModel.value?.family;

    return aiConfig.availableSets.map((set) => {
      // Check if set supports the current mode
      const compatible = set.modes.includes(currentMode);

      // Check if set suggests the model's family
      const familyMatch =
        modelFamily &&
        (set.family === modelFamily || set.families.includes(modelFamily) || set.family === 'all');

      return {
        label: set.name,
        value: set.id,
        description: set.description,
        author: set.author,
        compatible,
        familyMatch: !!familyMatch,
        toolCount: 0, // Will be loaded dynamically
        disabled: !compatible,
        families: set.families || (set.family ? [set.family] : []),
      };
    });
  });

  const currentSetStatus = computed(() => {
    return filteredSetOptions.value.find((s) => s.value === selectedSetId.value);
  });

  // Get all tools for a set grouped by mode
  function getSetToolsByMode(setId: string): Record<string, string[]> {
    return setToolsMap.value[setId] || {};
  }

  // Get total unique tool count across all modes for a set
  function getSetTotalToolCount(setId: string): number {
    const toolsByMode = getSetToolsByMode(setId);
    const uniqueTools = new Set<string>();
    Object.values(toolsByMode).forEach((tools) => {
      tools.forEach((tool) => uniqueTools.add(tool));
    });
    return uniqueTools.size;
  }

  // Load tools for ALL sets and ALL modes when model or available sets change
  async function loadAllSetTools() {
    const model = aiConfig.models.find((m) => m.id === selectedModelId.value);
    if (!model) {
      setToolsMap.value = {};
      return;
    }

    try {
      if (
        companionStore.isConnected &&
        aiConfig.availableSets.length > 0 &&
        aiConfig.availableModes.length > 0
      ) {
        // Load tools for each available set and each available mode
        const promises = aiConfig.availableSets.flatMap((set) =>
          aiConfig.availableModes.map(async (mode) => {
            try {
              const response = await companionStore.request<{
                success: boolean;
                tools?: string[];
                error?: string;
              }>('get_mode_tools', {
                mode,
                setId: set.id,
                family: model.family,
                version: model.version,
              });

              return {
                setId: set.id,
                mode,
                tools: response.success && response.tools ? response.tools : [],
              };
            } catch {
              return { setId: set.id, mode, tools: [] };
            }
          }),
        );

        const results = await Promise.all(promises);
        const newMap: Record<string, Record<string, string[]>> = {};
        results.forEach(({ setId, mode, tools }) => {
          if (!newMap[setId]) {
            newMap[setId] = {};
          }
          if (tools.length > 0) {
            const setMap = newMap[setId];
            if (setMap) {
              setMap[mode] = tools;
            }
          }
        });
        setToolsMap.value = newMap;
      }
    } catch (error) {
      console.warn('Failed to load tools:', error);
      setToolsMap.value = {};
    }
  }

  function handleModeChange(mode: Mode) {
    void aiConfig.setActiveMode(mode);
  }

  function handleModelChange(modelId: string) {
    void aiConfig.setActiveModel(modelId);
  }

  function handleSetSelect(setId: string) {
    void aiConfig.setActiveSet(setId);
  }

  // Watch for model and sets changes (tools are loaded for all modes)
  watch(
    [selectedModelId, () => aiConfig.availableSets, () => aiConfig.availableModes],
    loadAllSetTools,
    {
      immediate: true,
      deep: false,
    },
  );

  // Also watch for companion connection
  watch(
    () => companionStore.isConnected,
    (connected) => {
      if (connected && selectedModelId.value) {
        void loadAllSetTools();
      }
    },
  );

  // Sync with store - initialize immediately and watch for changes
  watch(
    () => aiConfig.activeMode,
    (mode) => {
      selectedMode.value = mode;
    },
    { immediate: true },
  );

  watch(
    () => aiConfig.activeModelId,
    (id) => {
      selectedModelId.value = id;
    },
    { immediate: true },
  );

  watch(
    () => aiConfig.activeSetId,
    (id) => {
      selectedSetId.value = id;
    },
    { immediate: true },
  );

  return {
    selectedMode,
    selectedModelId,
    selectedSetId,
    modeOptions,
    currentModeLabel,
    modelOptions,
    activeModel,
    filteredSetOptions,
    currentSetStatus,
    setToolsMap,
    getSetToolsByMode,
    getSetTotalToolCount,
    loadAllSetTools,
    handleModeChange,
    handleModelChange,
    handleSetSelect,
  };
}
