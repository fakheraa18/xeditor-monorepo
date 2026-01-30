<template>
  <q-page class="ai-settings-page">
    <div class="ai-settings-layout fit column no-wrap">
      <!-- Header -->
      <div class="ai-settings-header row items-center q-pa-md">
        <q-btn flat icon="arrow_back" to="/" class="q-mr-sm" />
        <h4 class="q-ma-none">AI Settings</h4>
        <q-space />
        <q-btn
          outline
          color="negative"
          label="Reset to Defaults"
          icon="restart_alt"
          @click="confirmResetDefaults"
        />
      </div>

      <!-- Loading State -->
      <div v-if="!aiConfig.isInitialized" class="col column items-center justify-center">
        <q-spinner-dots size="50px" color="primary" />
        <p class="q-mt-md">Loading AI configuration...</p>
      </div>

      <template v-else>
        <!-- Main Content: Two Sections -->
        <div class="ai-settings-content row no-wrap fit">
          <!-- Left Section: Model/LLM Provider Management -->
          <div class="models-section col-4 column no-wrap">
            <div class="section-header q-pa-md bg-primary text-white">
              <div class="text-h6">Models & LLM Providers</div>
              <div class="text-caption">Configure models with providers</div>
            </div>
            <q-scroll-area class="col">
              <div class="q-pa-md">
                <div class="row items-center q-mb-md">
                  <div class="text-subtitle1">Models</div>
                  <q-space />
                  <q-btn round flat icon="add" color="primary" @click="addNewModel" />
                </div>
                <q-list>
                  <q-item
                    v-for="model in aiConfig.models"
                    :key="model.id"
                    clickable
                    @click="editModel(model)"
                  >
                    <q-item-section avatar>
                      <q-icon :name="getProviderIcon(model.provider)" />
                    </q-item-section>
                    <q-item-section>
                      <q-item-label>{{ model.name }}</q-item-label>
                      <q-item-label caption>
                        {{ model.provider }} / {{ model.family
                        }}{{ model.version ? ` ${model.version}` : '' }}
                      </q-item-label>
                    </q-item-section>
                    <q-item-section side>
                      <q-btn
                        flat
                        round
                        dense
                        icon="edit"
                        color="primary"
                        @click.stop="editModel(model)"
                      >
                        <q-tooltip>Edit model</q-tooltip>
                      </q-btn>
                      <q-btn
                        flat
                        round
                        dense
                        icon="delete"
                        color="negative"
                        @click.stop="confirmDeleteModel(model.id)"
                      >
                        <q-tooltip>Delete model</q-tooltip>
                      </q-btn>
                    </q-item-section>
                  </q-item>
                </q-list>

                <div
                  v-if="aiConfig.models.length === 0"
                  class="q-mt-md text-center q-pa-xl text-grey-6"
                >
                  <q-icon name="memory" size="48px" />
                  <p class="q-mt-md">No models configured. Click + to add one.</p>
                </div>
              </div>
            </q-scroll-area>
          </div>

          <!-- Right Section: Set Manager/Designer -->
          <q-separator vertical />
          <div class="sets-section col column no-wrap">
            <div class="section-header q-pa-md bg-secondary text-white">
              <div class="row items-center">
                <div class="col">
                  <div class="text-h6">Prompt Set Manager</div>
                  <div class="text-caption">
                    Create and manage prompt sets with modes, prompts, parsers, and tools
                  </div>
                </div>
                <q-btn
                  color="white"
                  text-color="secondary"
                  icon="add"
                  label="New Set"
                  @click="addNewSet"
                />
                <q-btn
                  color="white"
                  text-color="secondary"
                  icon="file_download"
                  label="Import"
                  @click="handleImportSet"
                  class="q-ml-sm"
                />
              </div>
            </div>
            <q-scroll-area class="col">
              <div class="q-pa-md">
                <!-- Sets List -->
                <div class="q-mb-md">
                  <div class="text-subtitle1 q-mb-sm">Available Sets</div>
                  <q-list bordered separator>
                    <q-item
                      v-for="set in aiConfig.availableSets"
                      :key="set.id"
                      clickable
                      :active="selectedSetEdit?.id === set.id"
                      @click="selectSetForEdit(set)"
                    >
                      <q-item-section avatar>
                        <q-icon
                          :name="set.isBuiltIn ? 'extension' : 'folder'"
                          :color="set.isBuiltIn ? 'primary' : 'secondary'"
                        />
                      </q-item-section>
                      <q-item-section>
                        <q-item-label>
                          {{ set.name }}
                          <q-chip
                            v-if="set.isBuiltIn"
                            size="sm"
                            color="primary"
                            text-color="white"
                            class="q-ml-xs"
                          >
                            Built-in
                          </q-chip>
                        </q-item-label>
                        <q-item-label caption> {{ set.author }} / {{ set.version }} </q-item-label>
                        <q-item-label caption>
                          Modes: {{ set.modes.join(', ') }} • Family:
                          {{
                            set.family === 'all'
                              ? 'All'
                              : set.family || set.families.join(', ') || 'All'
                          }}
                        </q-item-label>
                      </q-item-section>
                      <q-item-section side>
                        <q-btn
                          v-if="set.isBuiltIn"
                          flat
                          round
                          dense
                          icon="content_copy"
                          color="primary"
                          @click.stop="
                            () => {
                              selectSetForEdit(set);
                              cloneSet();
                            }
                          "
                        >
                          <q-tooltip>Clone to edit</q-tooltip>
                        </q-btn>
                        <q-btn
                          v-if="!set.isBuiltIn"
                          flat
                          round
                          dense
                          icon="edit"
                          color="primary"
                          @click.stop="selectSetForEdit(set)"
                        >
                          <q-tooltip>Edit set</q-tooltip>
                        </q-btn>
                        <q-btn
                          flat
                          round
                          dense
                          icon="file_download"
                          color="primary"
                          @click.stop="handleExportSet(set.id)"
                        >
                          <q-tooltip>Export set</q-tooltip>
                        </q-btn>
                        <q-btn
                          v-if="!set.isBuiltIn"
                          flat
                          round
                          dense
                          icon="delete"
                          color="negative"
                          @click.stop="confirmDeleteSet(set.id)"
                        >
                          <q-tooltip>Delete set</q-tooltip>
                        </q-btn>
                      </q-item-section>
                    </q-item>
                  </q-list>
                </div>

                <!-- Set Viewer (for built-in sets) -->
                <q-card v-if="selectedSetEdit && selectedSetEdit.isBuiltIn" class="q-mt-md">
                  <q-card-section>
                    <div class="text-h6">View Prompt Set: {{ selectedSetEdit.name }}</div>
                  </q-card-section>
                  <q-separator />
                  <q-card-section>
                    <div class="row q-gutter-md q-mb-md">
                      <div class="col">
                        <div class="text-subtitle2 q-mb-xs">Author</div>
                        <div>{{ selectedSetEdit.author }}</div>
                      </div>
                      <div class="col-3">
                        <div class="text-subtitle2 q-mb-xs">Version</div>
                        <div>{{ selectedSetEdit.version }}</div>
                      </div>
                    </div>
                    <div class="q-mb-md">
                      <div class="text-subtitle2 q-mb-xs">Description</div>
                      <div>{{ selectedSetEdit.description }}</div>
                    </div>
                    <div class="q-mb-md">
                      <div class="text-subtitle2 q-mb-xs">Supported Modes</div>
                      <q-chip
                        v-for="mode in selectedSetEdit.modes"
                        :key="mode"
                        color="primary"
                        text-color="white"
                        class="q-mr-xs"
                      >
                        {{ mode }}
                      </q-chip>
                    </div>
                    <div class="q-mb-md">
                      <div class="text-subtitle2 q-mb-xs">Primary Family</div>
                      <q-chip v-if="selectedSetEdit.family" color="secondary" text-color="white">
                        {{ selectedSetEdit.family }}
                      </q-chip>
                      <div v-else>Not set</div>
                    </div>
                    <div class="q-mb-md">
                      <div class="text-subtitle2 q-mb-xs">Supported Families</div>
                      <q-chip
                        v-for="family in selectedSetEdit.families"
                        :key="family"
                        color="grey-7"
                        text-color="white"
                        class="q-mr-xs"
                      >
                        {{ family }}
                      </q-chip>
                      <div v-if="!selectedSetEdit.families.length">All families supported</div>
                    </div>
                    <q-btn
                      color="primary"
                      icon="content_copy"
                      label="Clone Set"
                      @click="cloneSet"
                      class="q-mt-md"
                    />
                  </q-card-section>
                </q-card>
              </div>
            </q-scroll-area>
          </div>
        </div>
      </template>
    </div>

    <!-- Model Editor Dialog -->
    <ModelEditorDialog
      v-model="showModelEditor"
      :model-to-edit="modelToEdit"
      @saved="onModelSaved"
    />

    <!-- Set Designer Dialog -->
    <SetDesigner v-model="showSetDesigner" :set-to-edit="setToEdit" />
  </q-page>
</template>

<script setup lang="ts">
import { ref, onMounted, watch } from 'vue';
import { useQuasar } from 'quasar';
import { useAiConfigStore } from '../stores/aiConfig';
import { useLocalCompanionStore } from '../stores/localCompanion';
import SetDesigner from '../components/ai/SetDesigner.vue';
import ModelEditorDialog from '../components/ai/ModelEditorDialog.vue';
import type { ModelConfig, ModelProviderId, PromptSetMetadata } from '../core/types';

const $q = useQuasar();
const aiConfig = useAiConfigStore();
const companionStore = useLocalCompanionStore();

// ─────────────────────────────────────────────────────────────────────────────
// Models CRUD
// ─────────────────────────────────────────────────────────────────────────────

const showModelEditor = ref(false);
const modelToEdit = ref<ModelConfig | null>(null);

function getProviderIcon(provider: ModelProviderId): string {
  const icons: Record<ModelProviderId, string> = {
    openai: 'smart_toy',
    anthropic: 'psychology',
    ollama: 'hub',
    lmstudio: 'computer',
    vllm: 'speed',
    sglang: 'developer_board',
    openai_compatible: 'api',
    kimi: 'auto_awesome',
    local_companion: 'terminal',
  };
  return icons[provider] || 'memory';
}

function addNewModel() {
  modelToEdit.value = null;
  showModelEditor.value = true;
}

function editModel(model: ModelConfig) {
  modelToEdit.value = model;
  showModelEditor.value = true;
}

function onModelSaved() {
  modelToEdit.value = null;
}

function confirmDeleteModel(modelId: string) {
  $q.dialog({
    title: 'Delete Model',
    message: `Are you sure you want to delete model "${modelId}"?`,
    cancel: true,
    persistent: true,
  }).onOk(() => {
    void aiConfig.removeModel(modelId);
    $q.notify({ type: 'positive', message: 'Model deleted' });
  });
}

// ─────────────────────────────────────────────────────────────────────────────
// Prompt Templates CRUD (removed - templates are now part of prompt sets)
// ─────────────────────────────────────────────────────────────────────────────

// ─────────────────────────────────────────────────────────────────────────────
// Prompt Sets CRUD
// ─────────────────────────────────────────────────────────────────────────────

const selectedSetEdit = ref<PromptSetMetadata | null>(null);
const showSetDesigner = ref(false);
const setToEdit = ref<PromptSetMetadata | null>(null);

function selectSetForEdit(set: PromptSetMetadata) {
  if (set.isBuiltIn) {
    // For built-in sets, show read-only view
    selectedSetEdit.value = JSON.parse(JSON.stringify(set)) as PromptSetMetadata;
  } else {
    // For user sets, open designer
    setToEdit.value = set;
    showSetDesigner.value = true;
  }
}

function addNewSet() {
  setToEdit.value = null;
  showSetDesigner.value = true;
}

watch(showSetDesigner, (open) => {
  if (!open) {
    // Reload sets when designer closes
    void aiConfig.loadSets();
    setToEdit.value = null;
  }
});

function cloneSet() {
  if (!selectedSetEdit.value) return;

  // Get available families from set metadata
  const availableFamilies =
    selectedSetEdit.value.families && selectedSetEdit.value.families.length > 0
      ? selectedSetEdit.value.families
      : selectedSetEdit.value.family && selectedSetEdit.value.family !== 'all'
        ? [selectedSetEdit.value.family]
        : [];

  if (availableFamilies.length === 0) {
    $q.notify({
      type: 'negative',
      message: 'No families found in source set',
    });
    return;
  }

  // Generate default target ID and name
  const defaultId = `user/${selectedSetEdit.value.name.toLowerCase().replace(/\s+/g, '-')}-clone`;
  const defaultName = `${selectedSetEdit.value.name} (Clone)`;

  // Show dialog for set ID
  $q.dialog({
    title: 'Clone Prompt Set',
    message: 'Enter the Set ID for the cloned set (format: user/set-name)',
    prompt: {
      model: defaultId,
      type: 'text',
    },
    cancel: true,
    persistent: true,
  }).onOk((targetId: string) => {
    if (!targetId || !targetId.includes('/')) {
      $q.notify({
        type: 'negative',
        message: 'Set ID must be in format "user/set-name"',
      });
      return;
    }

    // Show dialog for set name
    $q.dialog({
      title: 'Set Name',
      message: 'Enter a display name for the cloned set',
      prompt: {
        model: defaultName,
        type: 'text',
      },
      cancel: true,
      persistent: true,
    }).onOk((targetName: string) => {
      if (!targetName) {
        $q.notify({
          type: 'negative',
          message: 'Set name is required',
        });
        return;
      }

      // Show dialog for family selection
      const defaultFamily = availableFamilies[0];
      if (!defaultFamily) {
        $q.notify({
          type: 'negative',
          message: 'No families available',
        });
        return;
      }

      $q.dialog({
        title: 'Select Model Family',
        message:
          'Which model family should be cloned? (The default set supports multiple families, but custom sets are limited to one.)',
        options: {
          type: 'radio',
          model: defaultFamily,
          items: availableFamilies.map((family) => ({
            label: family.charAt(0).toUpperCase() + family.slice(1),
            value: family,
          })),
        },
        cancel: true,
        persistent: true,
      }).onOk((family: string) => {
        void (async () => {
          try {
            // Call clone_set API
            const response = await companionStore.request<{
              success: boolean;
              metadata?: PromptSetMetadata;
              error?: string;
            }>('clone_set', {
              sourceSetId: selectedSetEdit.value!.id,
              targetId: targetId,
              targetName: targetName,
              targetAuthor: 'User',
              family: family,
            });

            if (!response.success) {
              $q.notify({
                type: 'negative',
                message: `Failed to clone set: ${response.error || 'Unknown error'}`,
              });
              return;
            }

            // Reload sets
            await aiConfig.loadSets();

            // Find the newly created set and open it in designer
            const newSet = aiConfig.availableSets.find((s) => s.id === targetId);
            if (newSet) {
              setToEdit.value = newSet;
              showSetDesigner.value = true;
              $q.notify({
                type: 'positive',
                message: 'Set cloned successfully',
              });
            } else {
              $q.notify({
                type: 'positive',
                message: 'Set cloned successfully. Please select it from the list to edit.',
              });
            }
          } catch (error) {
            $q.notify({
              type: 'negative',
              message: `Failed to clone set: ${error instanceof Error ? error.message : 'Unknown error'}`,
            });
          }
        })();
      });
    });
  });
}

function confirmDeleteSet(setId: string) {
  $q.dialog({
    title: 'Delete Set',
    message: `Are you sure you want to delete this prompt set?`,
    cancel: true,
    persistent: true,
  }).onOk(() => {
    void (async () => {
      try {
        await aiConfig.deleteSet(setId);
        if (selectedSetEdit.value?.id === setId) {
          selectedSetEdit.value = null;
        }
        $q.notify({ type: 'positive', message: 'Set deleted' });
      } catch (error) {
        $q.notify({
          type: 'negative',
          message: `Failed to delete set: ${error instanceof Error ? error.message : 'Unknown error'}`,
        });
      }
    })();
  });
}

async function handleExportSet(setId: string) {
  try {
    const blob = await aiConfig.exportSet(setId);
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `${setId.replace('/', '_')}.zip`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
    $q.notify({ type: 'positive', message: 'Set exported' });
  } catch (error) {
    $q.notify({
      type: 'negative',
      message: `Failed to export set: ${error instanceof Error ? error.message : 'Unknown error'}`,
    });
  }
}

function handleImportSet() {
  const input = document.createElement('input');
  input.type = 'file';
  input.accept = '.zip';
  input.onchange = async (e) => {
    const file = (e.target as HTMLInputElement).files?.[0];
    if (!file) return;

    try {
      await aiConfig.importSet(file);
      $q.notify({ type: 'positive', message: 'Set imported successfully' });
    } catch (error) {
      $q.notify({
        type: 'negative',
        message: `Failed to import set: ${error instanceof Error ? error.message : 'Unknown error'}`,
      });
    }
  };
  input.click();
}

// ─────────────────────────────────────────────────────────────────────────────
// Tools & MCP (removed - tools are now managed within prompt sets)
// ─────────────────────────────────────────────────────────────────────────────

// ─────────────────────────────────────────────────────────────────────────────
// Reset to Defaults
// ─────────────────────────────────────────────────────────────────────────────

function confirmResetDefaults() {
  $q.dialog({
    title: 'Reset to Defaults',
    message:
      'This will reset all user-modified models and prompt templates to their system defaults. ' +
      'Custom models and templates you created will be preserved. ' +
      'This action cannot be undone. Continue?',
    cancel: true,
    persistent: true,
    ok: {
      label: 'Reset',
      color: 'negative',
    },
  }).onOk(() => {
    void (async () => {
      try {
        await aiConfig.resetToDefaults();
        $q.notify({
          type: 'positive',
          message: 'Reset to defaults complete. User overrides removed, custom items preserved.',
          timeout: 3000,
        });
      } catch (error) {
        $q.notify({
          type: 'negative',
          message: `Failed to reset: ${error instanceof Error ? error.message : 'Unknown error'}`,
          timeout: 5000,
        });
      }
    })();
  });
}

// ─────────────────────────────────────────────────────────────────────────────
// Lifecycle
// ─────────────────────────────────────────────────────────────────────────────

onMounted(async () => {
  await aiConfig.initialize();
});
</script>

<style scoped>
.ai-settings-page {
  height: 100%;
  width: 100%;
}

.ai-settings-layout {
  height: 100%;
}

.ai-settings-header {
  flex-shrink: 0;
  border-bottom: 1px solid rgba(0, 0, 0, 0.12);
}

.ai-settings-content {
  min-height: 0;
}

.models-section,
.sets-section {
  min-width: 0;
  overflow: hidden;
}

.section-header {
  flex-shrink: 0;
}

.models-section .q-scroll-area,
.sets-section .q-scroll-area {
  height: 100%;
}
</style>
