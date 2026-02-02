<template>
  <q-dialog v-model="isOpen" maximized>
    <q-card class="set-designer-card">
      <q-card-section class="row items-center q-pb-none">
        <div class="text-h6">{{ isEditing ? 'Edit' : 'Create' }} Prompt Set</div>
        <q-space />
        <q-btn icon="close" flat round dense @click="isOpen = false" />
      </q-card-section>

      <q-card-section>
        <q-stepper v-model="step" color="primary" animated class="set-designer-stepper">
          <!-- Step 1: Set Metadata -->
          <q-step :name="1" title="Set Metadata" icon="info" :done="step > 1">
            <div class="row q-gutter-md q-mt-md">
              <q-input
                v-model="setMetadata.id"
                label="Set ID"
                outlined
                dense
                class="col"
                hint="Format: user/set-name (e.g. john/my-custom-set)"
                :disable="isEditing"
              />
              <q-input v-model="setMetadata.name" label="Name" outlined dense class="col" />
            </div>

            <div class="row q-gutter-md q-mt-md">
              <q-input v-model="setMetadata.author" label="Author" outlined dense class="col" />
              <q-input v-model="setMetadata.version" label="Version" outlined dense class="col-3" />
            </div>

            <q-input
              v-model="setMetadata.description"
              label="Description"
              type="textarea"
              outlined
              :rows="3"
              class="q-mt-md"
            />

            <div class="q-mt-md">
              <div class="text-subtitle2 q-mb-sm">Model Family</div>
              <q-select
                v-model="selectedFamily"
                :options="familyOptions"
                option-label="name"
                option-value="id"
                emit-value
                map-options
                outlined
                dense
                hint="Select the model family this set works best with"
                @update:model-value="handleFamilyChange"
              />
            </div>

            <div class="q-mt-md">
              <div class="text-subtitle2 q-mb-sm">Model Version (Optional)</div>
              <q-select
                v-model="setMetadata.modelVersion"
                :options="versionOptions"
                option-label="label"
                option-value="value"
                emit-value
                map-options
                outlined
                dense
                clearable
                :disable="!selectedFamily"
                hint="Optionally select a specific model version this set is optimized for"
              />
            </div>

            <div class="q-mt-md">
              <div class="text-subtitle2 q-mb-sm">Supported Modes</div>
              <q-option-group
                v-model="setMetadata.modes"
                :options="modeCheckboxOptions"
                type="checkbox"
                color="primary"
              />
            </div>

            <!-- Custom Tools Management -->
            <div class="q-mt-lg">
              <div class="row items-center q-mb-md">
                <div class="text-subtitle2">Custom Tools</div>
                <q-space />
                <q-btn
                  color="primary"
                  icon="add"
                  label="Add Tool"
                  @click="addCustomTool"
                  size="sm"
                />
              </div>

              <q-list v-if="customTools.length > 0" bordered separator>
                <q-item
                  v-for="tool in customTools"
                  :key="tool.name"
                  clickable
                  @click="editCustomTool(tool)"
                >
                  <q-item-section>
                    <q-item-label>{{ tool.name }}</q-item-label>
                    <q-item-label caption
                      >Available for {{ selectedFamily || 'selected family' }}</q-item-label
                    >
                  </q-item-section>
                  <q-item-section side>
                    <q-btn
                      flat
                      round
                      dense
                      icon="delete"
                      color="negative"
                      @click.stop="deleteCustomTool(tool.name)"
                    />
                  </q-item-section>
                </q-item>
              </q-list>

              <q-card v-else class="text-center q-pa-md text-grey-6">
                <q-icon name="build" size="32px" />
                <p class="q-mt-sm q-mb-none text-body2">No custom tools yet</p>
                <p class="text-caption">Click "Add Tool" to create a custom Python tool</p>
              </q-card>

              <!-- Tool Editor Dialog -->
              <q-dialog v-model="showToolEditor" maximized>
                <q-card>
                  <q-card-section class="row items-center">
                    <div class="text-h6">Edit Tool: {{ editingTool?.name }}</div>
                    <q-space />
                    <q-btn icon="close" flat round dense @click="showToolEditor = false" />
                  </q-card-section>
                  <q-card-section v-if="editingTool">
                    <div class="row q-gutter-md q-mb-md">
                      <q-input
                        v-model="editingTool.name"
                        label="Tool Name"
                        outlined
                        dense
                        class="col-12"
                        hint="Function name (e.g. my_custom_tool)"
                      />
                      <div class="col-12 text-caption text-grey-7">
                        Tool will be available for family:
                        <strong>{{ selectedFamily || 'Not selected' }}</strong>
                        <br />
                        Tools are shared across all modes. Use the "Attach Tools" step to control
                        which tools are available per mode.
                      </div>
                    </div>
                    <MonacoToolEditor
                      v-model="editingTool.content"
                      :tool-name="editingTool.name"
                      height="500px"
                    />
                  </q-card-section>
                  <q-card-actions align="right">
                    <q-btn flat label="Cancel" @click="showToolEditor = false" />
                    <q-btn color="primary" label="Save Tool" @click="saveCustomTool" />
                  </q-card-actions>
                </q-card>
              </q-dialog>
            </div>

            <q-stepper-navigation>
              <q-btn @click="step = 2" color="primary" label="Next" />
            </q-stepper-navigation>
          </q-step>

          <!-- Step 2: Mode Configuration -->
          <q-step :name="2" title="Mode Configuration" icon="settings" :done="step > 2">
            <div class="q-mt-md">
              <!-- Shared Parser Editor (shown once, shared across all modes) -->
              <div class="q-mb-lg">
                <div class="text-subtitle1 q-mb-md">Response Parser (Shared)</div>
                <div class="text-body2 q-mb-md text-grey-7">
                  The parser is shared across all modes for this family. Changes here apply to all
                  modes.
                </div>
                <MonacoParserEditor
                  v-model="familyParser"
                  :family="selectedFamily || 'default'"
                  :mode="''"
                  height="calc(100vh - 600px)"
                />
              </div>

              <q-separator class="q-my-lg" />

              <q-tabs v-model="activeModeTab" align="left" class="text-primary">
                <q-tab
                  v-for="mode in setMetadata.modes"
                  :key="mode"
                  :name="mode"
                  :label="mode.charAt(0).toUpperCase() + mode.slice(1)"
                />
              </q-tabs>

              <q-tab-panels v-model="activeModeTab" animated>
                <q-tab-panel
                  v-for="mode in setMetadata.modes"
                  :key="mode"
                  :name="mode"
                  class="q-pa-none"
                >
                  <div class="q-mt-md">
                    <!-- Family Selection for this mode (auto-filled from metadata) -->
                    <!-- Prompt Editor -->
                    <div class="q-mb-md">
                      <div class="text-subtitle2 q-mb-md">System Prompt</div>
                      <MonacoPromptEditor
                        v-if="modeConfigs[mode]"
                        v-model="modeConfigs[mode].prompt"
                        height="calc(100vh - 500px)"
                      />

                      <!-- Context Variables Reference -->
                      <q-expansion-item
                        icon="info"
                        label="Context Variables Reference"
                        class="q-mt-md"
                        header-class="bg-grey-2"
                      >
                        <q-card>
                          <q-card-section>
                            <div class="text-body2 q-mb-md">
                              You can use template variables in your prompts using
                              <code>&#123;&#123;variable&#125;&#125;</code> syntax. These variables
                              will be automatically replaced with actual values when the prompt is
                              used.
                            </div>

                            <div class="text-subtitle2 q-mb-sm">Available Variables:</div>

                            <q-list bordered separator>
                              <q-item>
                                <q-item-section>
                                  <q-item-label class="text-weight-medium"
                                    >System Information</q-item-label
                                  >
                                  <q-item-label caption>
                                    <code>&#123;&#123;system_info.os&#125;&#125;</code> - Operating
                                    system (e.g., "Linux", "Windows", "Darwin")
                                    <br />
                                    <code>&#123;&#123;system_info.osVersion&#125;&#125;</code> - OS
                                    version/release
                                    <br />
                                    <code>&#123;&#123;system_info.shell&#125;&#125;</code> - Default
                                    shell path (e.g., "/bin/zsh")
                                    <br />
                                    <code>&#123;&#123;system_info.home&#125;&#125;</code> - Home
                                    directory path
                                    <br />
                                    <code>&#123;&#123;system_info.workspace&#125;&#125;</code> -
                                    Current workspace directory
                                  </q-item-label>
                                </q-item-section>
                              </q-item>

                              <q-item>
                                <q-item-section>
                                  <q-item-label class="text-weight-medium">Tools</q-item-label>
                                  <q-item-label caption>
                                    <code>&#123;&#123;tools&#125;&#125;</code> - Complete formatted
                                    tool definitions section with descriptions and parameters
                                    <br />
                                    <small class="text-grey-7"
                                      >This will be replaced with detailed markdown documentation of
                                      all available tools.</small
                                    >
                                    <br />
                                    <br />
                                    <code>&#123;&#123;tools_json&#125;&#125;</code> - Tool
                                    definitions as JSON array format
                                    <br />
                                    <small class="text-grey-7"
                                      >This will be replaced with a JSON array containing tool
                                      definitions (name, description, parameters). Useful for
                                      GLM-style templates that require JSON format.</small
                                    >
                                  </q-item-label>
                                </q-item-section>
                              </q-item>

                              <q-item>
                                <q-item-section>
                                  <q-item-label class="text-weight-medium"
                                    >Project Information</q-item-label
                                  >
                                  <q-item-label caption>
                                    <code>&#123;&#123;project_info.name&#125;&#125;</code> - Project
                                    name (if available)
                                    <br />
                                    <code>&#123;&#123;project_info.root&#125;&#125;</code> - Primary
                                    project root path (if available)
                                    <br />
                                    <code>&#123;&#123;project_info.structure&#125;&#125;</code>
                                    - Overview of project folder structure (files/folders)
                                    <br />
                                    <small class="text-grey-7"
                                      >Note: Project info is only available when a project is
                                      active.</small
                                    >
                                  </q-item-label>
                                </q-item-section>
                              </q-item>

                              <q-item>
                                <q-item-section>
                                  <q-item-label class="text-weight-medium"
                                    >User Context</q-item-label
                                  >
                                  <q-item-label caption>
                                    <code>&#123;&#123;user_context_summary&#125;&#125;</code> -
                                    Summary of user-provided context items
                                    <br />
                                    <small class="text-grey-7"
                                      >Brief summary of files/code the user has selected or
                                      mentioned.</small
                                    >
                                  </q-item-label>
                                </q-item-section>
                              </q-item>
                            </q-list>

                            <div class="text-subtitle2 q-mt-md q-mb-sm">Example Usage:</div>
                            <q-card flat bordered class="bg-grey-1">
                              <q-card-section class="q-pa-sm">
                                <pre class="q-ma-none text-caption">
SYSTEM_PROMPT = """You are an AI assistant.

Operating System: &#123;&#123;system_info.os&#125;&#125; &#123;&#123;system_info.osVersion&#125;&#125;
Workspace: &#123;&#123;system_info.workspace&#125;&#125;

PROJECT STRUCTURE:
&#123;&#123;project_info.structure&#125;&#125;

# Available Tools

&#123;&#123;tools&#125;&#125;

# Or use JSON format for GLM-style templates:
# &#123;&#123;tools_json&#125;&#125;

Use the workspace path when working with files.
"""</pre
                                >
                              </q-card-section>
                            </q-card>
                          </q-card-section>
                        </q-card>
                      </q-expansion-item>
                    </div>

                    <!-- Tools Selection -->
                    <div class="q-mb-md">
                      <div class="text-subtitle2 q-mb-sm">Attach Tools</div>
                      <q-select
                        v-if="modeConfigs[mode]"
                        v-model="modeConfigs[mode].tools"
                        :options="availableToolOptions"
                        option-value="value"
                        option-label="label"
                        emit-value
                        map-options
                        multiple
                        outlined
                        dense
                        use-chips
                        hint="Select tools available in this mode"
                      />
                    </div>

                    <!-- Tool Settings -->
                    <q-expansion-item
                      v-if="modeConfigs[mode] && modeConfigs[mode].tools.includes('read_file')"
                      icon="settings"
                      label="read_file Settings"
                      class="q-mb-md"
                      header-class="bg-grey-2"
                    >
                      <q-card>
                        <q-card-section>
                          <div class="text-body2 q-mb-md text-grey-7">
                            Configure how read_file handles large files. Files exceeding the
                            threshold will be chunked into head, middle, and tail sections.
                          </div>

                          <div class="row q-gutter-md">
                            <q-input
                              type="number"
                              label="Threshold (chars)"
                              hint="Start chunking above this (default: 50000)"
                              outlined
                              dense
                              class="col"
                              :model-value="getReadFileSetting(mode, 'thresholdChars', 50000)"
                              @update:model-value="
                                (val) => setReadFileSetting(mode, 'thresholdChars', val)
                              "
                            />
                            <q-input
                              type="number"
                              label="Max Chars"
                              hint="Hard cap on total chars (default: 100000)"
                              outlined
                              dense
                              class="col"
                              :model-value="getReadFileSetting(mode, 'maxChars', 100000)"
                              @update:model-value="
                                (val) => setReadFileSetting(mode, 'maxChars', val)
                              "
                            />
                            <q-input
                              type="number"
                              label="Max Lines"
                              hint="Hard cap on total lines (default: 2000)"
                              outlined
                              dense
                              class="col"
                              :model-value="getReadFileSetting(mode, 'maxLines', 2000)"
                              @update:model-value="
                                (val) => setReadFileSetting(mode, 'maxLines', val)
                              "
                            />
                          </div>

                          <div class="row q-gutter-md q-mt-md">
                            <q-input
                              type="number"
                              label="Head Lines"
                              hint="Lines from start (default: 100)"
                              outlined
                              dense
                              class="col"
                              :model-value="getReadFileSetting(mode, 'headLines', 100)"
                              @update:model-value="
                                (val) => setReadFileSetting(mode, 'headLines', val)
                              "
                            />
                            <q-input
                              type="number"
                              label="Middle Lines"
                              hint="Lines from middle (default: 50)"
                              outlined
                              dense
                              class="col"
                              :model-value="getReadFileSetting(mode, 'middleLines', 50)"
                              @update:model-value="
                                (val) => setReadFileSetting(mode, 'middleLines', val)
                              "
                            />
                            <q-input
                              type="number"
                              label="Tail Lines"
                              hint="Lines from end (default: 100)"
                              outlined
                              dense
                              class="col"
                              :model-value="getReadFileSetting(mode, 'tailLines', 100)"
                              @update:model-value="
                                (val) => setReadFileSetting(mode, 'tailLines', val)
                              "
                            />
                          </div>
                        </q-card-section>
                      </q-card>
                    </q-expansion-item>
                  </div>
                </q-tab-panel>
              </q-tab-panels>
            </div>

            <q-stepper-navigation>
              <q-btn flat @click="step = 1" color="primary" label="Back" class="q-mr-sm" />
              <q-btn @click="step = 3" color="primary" label="Next" />
            </q-stepper-navigation>
          </q-step>

          <!-- Step 3: Review & Save -->
          <q-step :name="3" title="Review & Save" icon="check">
            <div class="q-mt-md">
              <div class="text-h6 q-mb-md">Set Summary</div>

              <q-card class="q-mb-md">
                <q-card-section>
                  <div class="text-subtitle1 q-mb-sm">Metadata</div>
                  <div><strong>ID:</strong> {{ setMetadata.id }}</div>
                  <div><strong>Name:</strong> {{ setMetadata.name }}</div>
                  <div><strong>Author:</strong> {{ setMetadata.author }}</div>
                  <div><strong>Version:</strong> {{ setMetadata.version }}</div>
                  <div><strong>Description:</strong> {{ setMetadata.description }}</div>
                  <div><strong>Family:</strong> {{ selectedFamily || 'Not set' }}</div>
                  <div>
                    <strong>Model Version:</strong> {{ setMetadata.modelVersion || 'Any version' }}
                  </div>
                  <div><strong>Modes:</strong> {{ setMetadata.modes.join(', ') }}</div>
                </q-card-section>
              </q-card>

              <q-card class="q-mb-md">
                <q-card-section>
                  <div class="text-subtitle1 q-mb-sm">Mode Configurations</div>
                  <div v-for="mode in setMetadata.modes" :key="mode" class="q-mb-sm">
                    <strong>{{ mode }}:</strong>
                    <div class="q-pl-md" v-if="modeConfigs[mode]">
                      <div>Family: {{ modeConfigs[mode].family || 'Not set' }}</div>
                      <div>Prompt: {{ modeConfigs[mode].prompt ? '✓ Set' : '✗ Missing' }}</div>
                      <div>Tools: {{ modeConfigs[mode].tools.length }} selected</div>
                    </div>
                  </div>
                  <div class="q-mt-md">
                    <strong>Parser (shared):</strong>
                    <div class="q-pl-md">
                      <div>Parser: {{ familyParser ? '✓ Set' : '✗ Missing' }}</div>
                      <div class="text-caption text-grey-7">
                        Shared across all modes for this family
                      </div>
                    </div>
                  </div>
                </q-card-section>
              </q-card>

              <q-card v-if="customTools.length > 0">
                <q-card-section>
                  <div class="text-subtitle1 q-mb-sm">Custom Tools</div>
                  <div v-for="tool in customTools" :key="tool.name">
                    {{ tool.name }} (available for {{ selectedFamily || 'selected family' }})
                  </div>
                </q-card-section>
              </q-card>

              <q-banner v-if="validationErrors.length > 0" class="bg-negative text-white q-mt-md">
                <template #avatar>
                  <q-icon name="error" />
                </template>
                <div class="text-weight-medium">Validation Errors:</div>
                <ul class="q-mt-sm q-ml-md">
                  <li v-for="error in validationErrors" :key="error">{{ error }}</li>
                </ul>
              </q-banner>
            </div>

            <q-stepper-navigation>
              <q-btn flat @click="step = 2" color="primary" label="Back" class="q-mr-sm" />
              <q-btn
                color="primary"
                label="Save Set"
                :disable="validationErrors.length > 0"
                @click="saveSet"
              />
            </q-stepper-navigation>
          </q-step>
        </q-stepper>
      </q-card-section>
    </q-card>
  </q-dialog>
</template>

<script setup lang="ts">
import { ref, computed, watch, nextTick } from 'vue';
import { useQuasar } from 'quasar';
import { useAiConfigStore } from '../../stores/aiConfig';
import { useLocalCompanionStore } from '../../../../stores/localCompanion';
import type { PromptSetMetadata } from 'src/apps/CodeEditor/core/types';
import MonacoPromptEditor from './MonacoPromptEditor.vue';
import MonacoParserEditor from './MonacoParserEditor.vue';
import MonacoToolEditor from './MonacoToolEditor.vue';

interface Props {
  modelValue: boolean;
  setToEdit?: PromptSetMetadata | null;
}

const props = defineProps<Props>();

const emit = defineEmits<{
  'update:modelValue': [value: boolean];
}>();

const $q = useQuasar();
const aiConfig = useAiConfigStore();
const companionStore = useLocalCompanionStore();

const isOpen = computed({
  get: () => props.modelValue,
  set: (val) => emit('update:modelValue', val),
});

const isEditing = computed(() => !!props.setToEdit);

const step = ref(1);
const activeModeTab = ref<string>('');
const activeEditorTab = ref<string>('prompt'); // Tab for prompt/parser editors

// Selected family (single value for UI)
const selectedFamily = ref<string>('');

// Set metadata
const setMetadata = ref<PromptSetMetadata>({
  id: '',
  name: '',
  author: '',
  version: '1.0.0',
  description: '',
  modes: [],
  family: '',
  families: [],
  isBuiltIn: false,
});

// Tool settings interface (matches server-side ToolSettings)
interface ReadFileSettings {
  thresholdChars?: number;
  maxChars?: number;
  maxLines?: number;
  headLines?: number;
  middleLines?: number;
  tailLines?: number;
}

interface ToolSettings {
  read_file?: ReadFileSettings;
}

// Mode configurations
interface ModeConfig {
  family: string;
  prompt: string;
  tools: string[];
  settings: ToolSettings;
}

const modeConfigs = ref<Record<string, ModeConfig>>({});

// Shared parser for the family (shared across all modes)
const familyParser = ref<string>('');

// Custom tools (stored at family level, shared across modes)
interface CustomTool {
  name: string;
  content: string;
}

const customTools = ref<CustomTool[]>([]);
const showToolEditor = ref(false);
const editingTool = ref<CustomTool | null>(null);

// Helper functions for read_file settings
function getReadFileSetting(
  mode: string,
  key: keyof ReadFileSettings,
  defaultValue: number,
): number {
  const config = modeConfigs.value[mode];
  if (!config || !config.settings || !config.settings.read_file) {
    return defaultValue;
  }
  const value = config.settings.read_file[key];
  return value !== undefined ? value : defaultValue;
}

function setReadFileSetting(
  mode: string,
  key: keyof ReadFileSettings,
  value: number | string | null,
): void {
  const config = modeConfigs.value[mode];
  if (!config) return;

  // Ensure settings structure exists
  if (!config.settings) {
    config.settings = {};
  }
  if (!config.settings.read_file) {
    config.settings.read_file = {};
  }

  // Convert to number and set
  const numValue = typeof value === 'string' ? parseInt(value, 10) : value;
  if (numValue !== null && typeof numValue === 'number' && !isNaN(numValue)) {
    config.settings.read_file[key] = numValue;
  } else {
    delete config.settings.read_file[key];
  }
}

// Options
const familyOptions = computed(() => {
  return aiConfig.modelFamilyRegistry.map((family) => ({
    id: family.id,
    name: `${family.name} (${family.id})`,
  }));
});

const versionOptions = computed(() => {
  if (!selectedFamily.value) {
    return [];
  }
  const family = aiConfig.modelFamilyRegistry.find((f) => f.id === selectedFamily.value);
  if (!family) {
    return [];
  }
  return family.versions.map((version) => ({
    label: version,
    value: version,
  }));
});

const modeCheckboxOptions = computed(() => {
  return ['plan', 'ask', 'agent'].map((mode) => ({
    label: mode.charAt(0).toUpperCase() + mode.slice(1),
    value: mode,
  }));
});

// System tools fetched from backend
const systemTools = ref<string[]>([]);

// Fetch system tools from backend
async function loadSystemTools() {
  try {
    const response = await companionStore.request<{
      success: boolean;
      tools?: string[];
      error?: string;
    }>('get_system_tools', {});

    if (response.success && response.tools) {
      systemTools.value = response.tools;
    } else {
      console.warn('Failed to load system tools:', response.error);
      // Fallback to empty array if fetch fails
      systemTools.value = [];
    }
  } catch (error) {
    console.warn('Failed to load system tools:', error);
    // Fallback to empty array if fetch fails
    systemTools.value = [];
  }
}

const availableToolOptions = computed(() => {
  // Combine system tools with custom tools created in this set
  const systemOptions = systemTools.value.map((tool) => ({
    label: `${tool} (system)`,
    value: tool,
  }));

  const customOptions = customTools.value.map((tool) => ({
    label: `${tool.name} (custom)`,
    value: tool.name,
  }));

  return [...systemOptions, ...customOptions];
});

const validationErrors = computed(() => {
  const errors: string[] = [];

  if (!setMetadata.value.id) {
    errors.push('Set ID is required');
  } else if (!setMetadata.value.id.includes('/')) {
    errors.push('Set ID must be in format "user/set-name"');
  }

  if (!setMetadata.value.name) {
    errors.push('Set name is required');
  }

  if (setMetadata.value.modes.length === 0) {
    errors.push('At least one mode must be selected');
  }

  if (!selectedFamily.value) {
    errors.push('A model family must be selected');
  }

  // Get all valid tool names (system tools + custom tools)
  const validToolNames = new Set<string>(systemTools.value);
  customTools.value.forEach((tool) => {
    validToolNames.add(tool.name);
  });

  // Validate mode configurations
  for (const mode of setMetadata.value.modes) {
    const config = modeConfigs.value[mode];
    if (!config) {
      errors.push(`Mode "${mode}" configuration is missing`);
      continue;
    }

    if (!config.family) {
      errors.push(`Mode "${mode}" must have a family selected`);
    }

    if (!config.prompt) {
      errors.push(`Mode "${mode}" must have a prompt`);
    }
  }

  // Validate shared parser (once per family, not per mode)
  if (!familyParser.value) {
    errors.push('Parser is required (shared across all modes for this family)');
  }

  // Validate tools exist in system
  for (const mode of setMetadata.value.modes) {
    const config = modeConfigs.value[mode];
    if (!config) continue;

    if (config.tools && config.tools.length > 0) {
      for (const tool of config.tools) {
        // Extract tool name (handle both strings and objects for backward compatibility)
        let toolName: string;
        if (typeof tool === 'string') {
          toolName = tool;
        } else {
          // Handle objects (shouldn't happen with emit-value, but defensive)
          const obj = tool as unknown as { value?: string; name?: string };
          toolName = obj?.value || obj?.name || '';
        }

        if (toolName && !validToolNames.has(toolName)) {
          errors.push(
            `Mode "${mode}" references unknown tool: "${toolName}". This tool does not exist in the system.`,
          );
        }
      }
    }
  }

  return errors;
});

// Initialize mode configs when modes change
watch(
  () => setMetadata.value.modes,
  (newModes) => {
    const currentConfigs = { ...modeConfigs.value };
    modeConfigs.value = {};

    for (const mode of newModes) {
      if (currentConfigs[mode]) {
        modeConfigs.value[mode] = {
          ...currentConfigs[mode],
          // Ensure family is set from selectedFamily
          family: selectedFamily.value || currentConfigs[mode].family,
          // Ensure settings exists
          settings: currentConfigs[mode].settings || {},
        };
      } else {
        modeConfigs.value[mode] = {
          family: selectedFamily.value || '',
          prompt: '',
          tools: [],
          settings: {},
        };
      }
    }

    if (newModes.length > 0 && !activeModeTab.value) {
      activeModeTab.value = newModes[0] as string;
    }
  },
  { immediate: true },
);

function handleFamilyChange(familyId: string) {
  if (familyId) {
    // Update all existing mode configs with the new family
    for (const mode of setMetadata.value.modes) {
      if (modeConfigs.value[mode]) {
        modeConfigs.value[mode].family = familyId;
      }
    }
    // Update families array for metadata (for compatibility)
    setMetadata.value.family = familyId;
    setMetadata.value.families = familyId ? [familyId] : [];
    // Clear modelVersion when family changes (user needs to reselect)
    delete setMetadata.value.modelVersion;
  }
}

// Update all mode configs when selectedFamily changes
watch(
  () => selectedFamily.value,
  (newFamily) => {
    if (newFamily) {
      handleFamilyChange(newFamily);
    }
  },
);

// Initialize from set to edit
watch(
  () => props.setToEdit,
  async (set) => {
    if (set) {
      setMetadata.value = JSON.parse(JSON.stringify(set));
      // Set selectedFamily from family or families array (use first one as fallback)
      selectedFamily.value =
        set.family || (set.families && set.families.length > 0 ? (set.families[0] ?? '') : '');
      // Load mode configs from backend
      await loadSetConfigs(set.id);
    } else {
      // Reset to defaults
      setMetadata.value = {
        id: '',
        name: '',
        author: '',
        version: '1.0.0',
        description: '',
        modes: [],
        family: '',
        families: [],
        isBuiltIn: false,
      };
      selectedFamily.value = '';
      modeConfigs.value = {};
      customTools.value = [];
      step.value = 1;
    }
  },
  { immediate: true },
);

watch(
  () => isOpen.value,
  (open) => {
    if (open) {
      // Load system tools when dialog opens
      void loadSystemTools();
    } else {
      // Reset when closed
      setMetadata.value = {
        id: '',
        name: '',
        author: '',
        version: '1.0.0',
        description: '',
        modes: [],
        family: '',
        families: [],
        isBuiltIn: false,
      };
      selectedFamily.value = '';
      modeConfigs.value = {};
      customTools.value = [];
      step.value = 1;
      activeModeTab.value = '';
      activeEditorTab.value = 'prompt';
    }
  },
);

async function loadSetConfigs(setId: string) {
  // Load prompts and parsers for each mode with the selected family
  const family =
    selectedFamily.value || (setMetadata.value.families && setMetadata.value.families[0]);
  if (!family) return;

  // Track loaded custom tools to avoid duplicates (tools are family-level, shared across modes)
  const loadedCustomTools = new Map<string, CustomTool>();

  // Load custom tools once at family level (outside mode loop)
  try {
    const toolsResponse = await companionStore.request<{
      success: boolean;
      tools?: Array<{ name: string; path: string }>;
      error?: string;
    }>('list_tools', {
      setId: setId,
      family: family,
    });

    if (toolsResponse.success && toolsResponse.tools) {
      for (const tool of toolsResponse.tools) {
        if (!loadedCustomTools.has(tool.name)) {
          try {
            const toolContentResponse = await companionStore.request<{
              success: boolean;
              content?: string;
              error?: string;
            }>('read_tool_file', {
              setId: setId,
              family: family,
              toolName: tool.name,
            });

            if (toolContentResponse.success && toolContentResponse.content) {
              loadedCustomTools.set(tool.name, {
                name: tool.name,
                content: toolContentResponse.content,
              });
            }
          } catch (error) {
            console.warn(`Failed to load tool content for ${tool.name}:`, error);
          }
        }
      }
    }
  } catch (error) {
    console.warn(`Failed to load tools for ${family}:`, error);
  }

  // Load mode-specific configs (prompts, parsers, tools.json allowlists)
  for (const mode of setMetadata.value.modes) {
    try {
      // Try to load prompt
      const promptResponse = await companionStore.request<{
        success: boolean;
        content?: string;
        error?: string;
      }>('read_prompt_file', {
        setId: setId,
        family: family,
        mode: mode,
      });
      if (promptResponse.success && promptResponse.content) {
        if (!modeConfigs.value[mode]) {
          modeConfigs.value[mode] = {
            family: family,
            prompt: '',
            tools: [],
            settings: {},
          };
        }
        modeConfigs.value[mode].prompt = promptResponse.content;
      }

      // Parser is loaded once per family (shared across modes)
      // Load it only for the first mode to avoid duplicate requests
      if (mode === setMetadata.value.modes[0]) {
        try {
          const parserResponse = await companionStore.request<{
            success: boolean;
            content?: string;
            error?: string;
          }>('read_parser_file', {
            setId: setId,
            family: family,
          });
          if (parserResponse.success && parserResponse.content) {
            familyParser.value = parserResponse.content;
          }
        } catch (error) {
          console.warn(`Failed to load parser for ${family}:`, error);
        }
      }

      // Load tools config (allowlist and settings from tools.json)
      const toolsConfigResponse = await companionStore.request<{
        success: boolean;
        tools?: string[] | null;
        settings?: ToolSettings;
        hasConfig?: boolean;
        error?: string;
      }>('read_tools_config', {
        setId: setId,
        family: family,
        mode: mode,
      });

      if (!modeConfigs.value[mode]) {
        modeConfigs.value[mode] = {
          family: family,
          prompt: '',
          tools: [],
          settings: {},
        };
      }

      // If tools.json exists, use it; otherwise use empty list for new sets
      if (
        toolsConfigResponse.success &&
        toolsConfigResponse.hasConfig &&
        toolsConfigResponse.tools
      ) {
        modeConfigs.value[mode].tools = toolsConfigResponse.tools;
      } else {
        // No tools.json yet - start with empty allowlist
        modeConfigs.value[mode].tools = [];
      }

      // Load settings from response
      if (toolsConfigResponse.success && toolsConfigResponse.settings) {
        modeConfigs.value[mode].settings = toolsConfigResponse.settings;
      } else {
        modeConfigs.value[mode].settings = {};
      }
    } catch (error) {
      console.warn(`Failed to load config for ${family}/${mode}:`, error);
    }
  }

  // Update customTools with loaded tools
  customTools.value = Array.from(loadedCustomTools.values());
}

function addCustomTool() {
  const defaultToolName = 'my_tool';
  // Initialize with default template to avoid Monaco editor issues with empty content
  const defaultTemplate = `"""Custom tool: ${defaultToolName}"""

from typing import Dict, Any
from tools.context import ToolContext


# TOOL_DESCRIPTOR is required for the LLM to understand this tool.
# It defines the tool's description and parameters that will be injected into the prompt.
TOOL_DESCRIPTOR = {
    "description": "TODO: Describe what this tool does",
    "parameters": {
        "input": {
            "type": "string",
            "required": True,
            "description": "TODO: Describe this parameter",
        },
        # Add more parameters as needed
    },
}


async def ${defaultToolName}(
    args: Dict[str, Any],
    context: ToolContext
) -> Dict[str, Any]:
    """
    Tool implementation.

    Args:
        args: Tool arguments from LLM (matches TOOL_DESCRIPTOR parameters)
        context: Framework context (project_root, llm_config, etc.)

    Returns:
        Dict with 'success', 'result', and optional 'error'
    """
    try:
        # Access parameters from args
        input_value = args.get("input", "")

        # TODO: Implement tool logic
        # Example: Access project root
        # project_root = context.project_root

        # Example: Call LLM (sub-agent)
        # result = await context.call_llm([...])

        # Example: Execute another tool
        # result = await context.execute_tool("read_file", {...})

        # Example: Vector search
        # results = await context.vector_search("query", limit=10)

        # Example: Stream output to UI
        # await context.emit_tool_chunk("Processing...")

        return {
            "success": True,
            "result": {
                "message": f"Tool executed with input: {input_value}",
            },
        }
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
        }
`;

  // Set the editing tool first
  editingTool.value = {
    name: defaultToolName,
    content: defaultTemplate,
  };

  // Use nextTick to ensure Vue has updated the reactive values before opening dialog
  void nextTick(() => {
    showToolEditor.value = true;
  });
}

function editCustomTool(tool: CustomTool) {
  editingTool.value = JSON.parse(JSON.stringify(tool));
  showToolEditor.value = true;
}

function saveCustomTool() {
  if (!editingTool.value || !editingTool.value.name) {
    $q.notify({ type: 'negative', message: 'Tool name is required' });
    return;
  }

  const existingIndex = customTools.value.findIndex((t) => t.name === editingTool.value!.name);
  if (existingIndex >= 0) {
    customTools.value[existingIndex] = editingTool.value;
  } else {
    customTools.value.push(editingTool.value);
  }

  showToolEditor.value = false;
  editingTool.value = null;
}

function deleteCustomTool(toolName: string) {
  $q.dialog({
    title: 'Delete Tool',
    message: `Are you sure you want to delete tool "${toolName}"?`,
    cancel: true,
    persistent: true,
  }).onOk(() => {
    customTools.value = customTools.value.filter((t) => t.name !== toolName);
  });
}

async function saveSet() {
  if (validationErrors.value.length > 0) {
    return;
  }

  try {
    // Update family and families array from selectedFamily before saving
    setMetadata.value.family = selectedFamily.value || '';
    setMetadata.value.families = selectedFamily.value ? [selectedFamily.value] : [];

    // Create/update set metadata
    if (isEditing.value) {
      const updates: Partial<PromptSetMetadata> = {
        name: setMetadata.value.name,
        author: setMetadata.value.author,
        version: setMetadata.value.version,
        description: setMetadata.value.description,
        modes: setMetadata.value.modes,
        family: setMetadata.value.family,
        families: setMetadata.value.families,
      };
      if (setMetadata.value.modelVersion !== undefined) {
        updates.modelVersion = setMetadata.value.modelVersion;
      }
      await aiConfig.updateSet(setMetadata.value.id, updates);
    } else {
      await aiConfig.createSet(setMetadata.value);
    }

    // Save shared parser (once per family, shared across modes)
    if (selectedFamily.value && familyParser.value) {
      await companionStore.request('write_parser_file', {
        setId: setMetadata.value.id,
        family: selectedFamily.value,
        content: familyParser.value,
      });
    }

    // Save mode configurations (prompts, tools config)
    for (const mode of setMetadata.value.modes) {
      const config = modeConfigs.value[mode];
      if (!config || !config.family) continue;

      // Save prompt
      if (config.prompt) {
        await companionStore.request('write_prompt_file', {
          setId: setMetadata.value.id,
          family: config.family,
          mode: mode,
          content: config.prompt,
        });
      }

      // Save tools allowlist (tools.json)
      // Ensure tools are strings (extract from objects if needed for backward compatibility)
      const toolNames: string[] = (config.tools || [])
        .map((tool) => {
          if (typeof tool === 'string') {
            return tool;
          }
          // Handle objects (shouldn't happen with emit-value, but defensive)
          const obj = tool as unknown as { value?: string; name?: string };
          return obj?.value || obj?.name || '';
        })
        .filter(Boolean); // Remove any empty strings

      await companionStore.request('write_tools_config', {
        setId: setMetadata.value.id,
        family: config.family,
        mode: mode,
        tools: toolNames,
        settings: config.settings || {},
      });
    }

    // Save custom tools (at family level, shared across modes)
    if (selectedFamily.value) {
      for (const tool of customTools.value) {
        await companionStore.request('write_tool_file', {
          setId: setMetadata.value.id,
          family: selectedFamily.value,
          toolName: tool.name,
          content: tool.content,
        });
      }
    }

    $q.notify({ type: 'positive', message: 'Set saved successfully' });
    isOpen.value = false;
  } catch (error) {
    $q.notify({
      type: 'negative',
      message: `Failed to save set: ${error instanceof Error ? error.message : 'Unknown error'}`,
    });
  }
}
</script>

<style scoped>
.set-designer-card {
  width: 100%;
  height: 100%;
}
</style>
