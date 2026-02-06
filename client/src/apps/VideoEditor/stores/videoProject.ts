/**
 * Video Project Store
 *
 * Manages video project state and communication with the local companion.
 * Handles project CRUD, asset management, story, and timeline.
 * Implements debounced autosave for reliable persistence.
 */

import { defineStore } from 'pinia';
import { ref, computed, watch } from 'vue';
import { useVideoCompanionStore } from './videoCompanion';
import type {
  VideoProject,
  ProjectSettings,
  AssetLibrary,
  Story,
  Timeline,
  RecentProject,
  CharacterAsset,
  ProductAsset,
  VoiceAsset,
  StoryScene,
  TimelineClip,
} from '../types';
import {
  createDefaultProjectSettings,
  createDefaultAssetLibrary,
  createDefaultStory,
  createDefaultTimeline,
} from '../types';

// Debounce delay for autosave (ms)
// Set to 5 minutes to reduce server load while still providing regular saves
const AUTOSAVE_DELAY_MS = 5 * 60 * 1000; // 5 minutes

export const useVideoProjectStore = defineStore('videoProject', () => {
  const companion = useVideoCompanionStore();

  // ─────────────────────────────────────────────────────────────────────
  // State
  // ─────────────────────────────────────────────────────────────────────

  const project = ref<VideoProject | null>(null);
  const recentProjects = ref<RecentProject[]>([]);
  const isLoading = ref(false);
  const error = ref<string | null>(null);
  const isDirty = ref(false);

  // Autosave state
  const isSaving = ref(false);
  const lastSaveError = ref<string | null>(null);
  let autosaveTimeoutId: ReturnType<typeof setTimeout> | null = null;
  // Guard to prevent triggering autosave when applying server responses
  let isApplyingServerState = false;

  // ─────────────────────────────────────────────────────────────────────
  // Computed
  // ─────────────────────────────────────────────────────────────────────

  const isOpen = computed(() => project.value !== null);
  const projectId = computed(() => project.value?.id ?? '');
  const projectName = computed(() => project.value?.name ?? 'Untitled');
  const settings = computed(() => project.value?.settings ?? createDefaultProjectSettings());
  const library = computed(() => project.value?.library ?? createDefaultAssetLibrary());
  const story = computed(() => project.value?.story ?? createDefaultStory());
  const timeline = computed(() => project.value?.timeline ?? createDefaultTimeline());

  // ─────────────────────────────────────────────────────────────────────
  // WebSocket Communication
  // ─────────────────────────────────────────────────────────────────────

  /**
   * Send a control message to the video editor WebSocket
   */
  async function sendControlMessage<T>(type: string, payload: Record<string, unknown>): Promise<T> {
    // Use the companion store's request method but with ve_ prefix
    const response = await companion.request(type, payload);
    // Only throw if error exists and is truthy (not null/undefined/empty string)
    if (
      response &&
      typeof response === 'object' &&
      'error' in response &&
      (response as { error?: string | null }).error
    ) {
      throw new Error((response as { error: string }).error);
    }
    return response as T;
  }

  // ─────────────────────────────────────────────────────────────────────
  // Project Operations
  // ─────────────────────────────────────────────────────────────────────

  /**
   * Create a new video project in the specified folder
   */
  async function createProject(
    folderPath: string,
    name: string,
    projectSettings?: Partial<ProjectSettings>,
  ): Promise<void> {
    isLoading.value = true;
    error.value = null;

    try {
      const response = await sendControlMessage<{
        success: boolean;
        project?: VideoProject;
        error?: string;
      }>('ve_create_project', {
        folderPath,
        name,
        settings: projectSettings,
      });

      if (response.success && response.project) {
        project.value = response.project;
        isDirty.value = false;
        await loadRecentProjects();
      } else {
        throw new Error(response.error || 'Failed to create project');
      }
    } catch (e) {
      error.value = (e as Error).message;
      throw e;
    } finally {
      isLoading.value = false;
    }
  }

  /**
   * Open an existing project from a folder
   */
  async function openProject(folderPath: string): Promise<void> {
    isLoading.value = true;
    error.value = null;

    try {
      const response = await sendControlMessage<{
        success: boolean;
        project?: VideoProject;
        error?: string;
      }>('ve_open_project', { folderPath });

      if (response.success && response.project) {
        project.value = response.project;
        isDirty.value = false;
        await loadRecentProjects();
      } else {
        throw new Error(response.error || 'Failed to open project');
      }
    } catch (e) {
      error.value = (e as Error).message;
      throw e;
    } finally {
      isLoading.value = false;
    }
  }

  /**
   * Save the current project state to the backend.
   * Uses ve_put_project_state to send the full project state.
   */
  async function saveProject(): Promise<void> {
    if (!project.value) return;

    // Cancel any pending autosave
    if (autosaveTimeoutId) {
      clearTimeout(autosaveTimeoutId);
      autosaveTimeoutId = null;
    }

    isSaving.value = true;
    lastSaveError.value = null;

    try {
      const response = await sendControlMessage<{
        success: boolean;
        project?: VideoProject;
        error?: string;
      }>('ve_put_project_state', {
        projectId: project.value.id,
        project: project.value,
      });

      if (!response.success) {
        throw new Error(response.error || 'Failed to save project');
      }

      // Apply server response (with updated_at timestamp)
      if (response.project) {
        isApplyingServerState = true;
        project.value = response.project;
        isApplyingServerState = false;
      }

      isDirty.value = false;
    } catch (e) {
      lastSaveError.value = (e as Error).message;
      console.error('Failed to save project:', e);
      throw e;
    } finally {
      isSaving.value = false;
    }
  }

  /**
   * Schedule an autosave after debounce delay.
   * Called automatically when project state changes.
   */
  function scheduleAutosave(): void {
    if (!project.value || isApplyingServerState) return;

    // Mark as dirty
    isDirty.value = true;

    // Cancel existing timeout
    if (autosaveTimeoutId) {
      clearTimeout(autosaveTimeoutId);
    }

    // Schedule new autosave
    autosaveTimeoutId = setTimeout(() => {
      autosaveTimeoutId = null;
      void performAutosave();
    }, AUTOSAVE_DELAY_MS);
  }

  /**
   * Perform the actual autosave.
   * Silent errors - just logs and sets lastSaveError.
   */
  async function performAutosave(): Promise<void> {
    if (!project.value || isSaving.value) return;

    isSaving.value = true;
    lastSaveError.value = null;

    try {
      const response = await sendControlMessage<{
        success: boolean;
        project?: VideoProject;
        error?: string;
      }>('ve_put_project_state', {
        projectId: project.value.id,
        project: project.value,
      });

      if (response.success) {
        // Apply server response
        if (response.project) {
          isApplyingServerState = true;
          project.value = response.project;
          isApplyingServerState = false;
        }
        isDirty.value = false;
      } else {
        lastSaveError.value = response.error || 'Autosave failed';
        console.error('Autosave failed:', response.error);
      }
    } catch (e) {
      lastSaveError.value = (e as Error).message;
      console.error('Autosave error:', e);
    } finally {
      isSaving.value = false;
    }
  }

  /**
   * Mark the project as dirty and trigger autosave.
   * Call this after any local mutation.
   */
  function markDirty(): void {
    scheduleAutosave();
  }

  /**
   * Close the current project
   */
  async function closeProject(): Promise<void> {
    if (!project.value) return;

    try {
      await sendControlMessage<{ success: boolean }>('ve_close_project', {
        projectId: project.value.id,
      });
    } finally {
      project.value = null;
      isDirty.value = false;
    }
  }

  /**
   * Load list of recent projects
   */
  async function loadRecentProjects(): Promise<void> {
    try {
      const response = await sendControlMessage<{
        success: boolean;
        recents?: RecentProject[];
      }>('ve_list_recent_projects', {});

      if (response.success && response.recents) {
        recentProjects.value = response.recents;
      }
    } catch (e) {
      console.error('Failed to load recent projects:', e);
    }
  }

  /**
   * Check if a folder is valid for a new project
   */
  async function checkFolder(folderPath: string): Promise<{
    isEmpty: boolean;
    hasProject: boolean;
  }> {
    const response = await sendControlMessage<{
      success: boolean;
      isEmpty: boolean;
      hasProject: boolean;
    }>('ve_check_folder', { folderPath });

    return {
      isEmpty: response.isEmpty,
      hasProject: response.hasProject,
    };
  }

  // ─────────────────────────────────────────────────────────────────────
  // Settings Updates
  // ─────────────────────────────────────────────────────────────────────

  async function updateSettings(newSettings: ProjectSettings): Promise<void> {
    if (!project.value) return;

    const response = await sendControlMessage<{
      success: boolean;
      project?: VideoProject;
    }>('ve_update_settings', {
      projectId: project.value.id,
      settings: newSettings,
    });

    if (response.success && response.project) {
      project.value = response.project;
      isDirty.value = false;
    }
  }

  // ─────────────────────────────────────────────────────────────────────
  // Library Management
  // ─────────────────────────────────────────────────────────────────────

  async function updateLibrary(newLibrary: AssetLibrary): Promise<void> {
    if (!project.value) return;

    const response = await sendControlMessage<{
      success: boolean;
      project?: VideoProject;
    }>('ve_update_library', {
      projectId: project.value.id,
      library: newLibrary,
    });

    if (response.success && response.project) {
      project.value = response.project;
      isDirty.value = false;
    }
  }

  function addCharacter(character: Omit<CharacterAsset, 'id' | 'created_at' | 'updated_at'>): void {
    if (!project.value) return;

    const now = Date.now() / 1000;
    const newCharacter: CharacterAsset = {
      ...character,
      id: crypto.randomUUID(),
      created_at: now,
      updated_at: now,
    };

    project.value.library.characters.push(newCharacter);
    scheduleAutosave();
  }

  function updateCharacter(id: string, updates: Partial<CharacterAsset>): void {
    if (!project.value) return;

    const index = project.value.library.characters.findIndex((c) => c.id === id);
    if (index >= 0) {
      const existing = project.value.library.characters[index];
      if (!existing) return;

      project.value.library.characters[index] = {
        ...existing,
        ...updates,
        updated_at: Date.now() / 1000,
      };
      scheduleAutosave();
    }
  }

  function removeCharacter(id: string): void {
    if (!project.value) return;

    project.value.library.characters = project.value.library.characters.filter((c) => c.id !== id);
    scheduleAutosave();
  }

  function addProduct(product: Omit<ProductAsset, 'id' | 'created_at' | 'updated_at'>): void {
    if (!project.value) return;

    const now = Date.now() / 1000;
    const newProduct: ProductAsset = {
      ...product,
      id: crypto.randomUUID(),
      created_at: now,
      updated_at: now,
    };

    project.value.library.products.push(newProduct);
    scheduleAutosave();
  }

  function addVoice(voice: Omit<VoiceAsset, 'id' | 'created_at' | 'updated_at'>): void {
    if (!project.value) return;

    const now = Date.now() / 1000;
    const newVoice: VoiceAsset = {
      ...voice,
      id: crypto.randomUUID(),
      created_at: now,
      updated_at: now,
    };

    project.value.library.voices.push(newVoice);
    scheduleAutosave();
  }

  // ─────────────────────────────────────────────────────────────────────
  // Story Management
  // ─────────────────────────────────────────────────────────────────────

  async function updateStory(newStory: Story): Promise<void> {
    if (!project.value) return;

    const response = await sendControlMessage<{
      success: boolean;
      project?: VideoProject;
    }>('ve_update_story', {
      projectId: project.value.id,
      story: newStory,
    });

    if (response.success && response.project) {
      project.value = response.project;
      isDirty.value = false;
    }
  }

  function addScene(scene: Omit<StoryScene, 'id'>): void {
    if (!project.value) return;

    const newScene: StoryScene = {
      ...scene,
      id: crypto.randomUUID(),
    };

    project.value.story.scenes.push(newScene);
    project.value.story.updated_at = Date.now() / 1000;
    scheduleAutosave();
  }

  function updateScene(id: string, updates: Partial<StoryScene>): void {
    if (!project.value) return;

    const index = project.value.story.scenes.findIndex((s) => s.id === id);
    if (index >= 0) {
      const existing = project.value.story.scenes[index];
      if (!existing) return;

      project.value.story.scenes[index] = {
        ...existing,
        ...updates,
      };
      project.value.story.updated_at = Date.now() / 1000;
      scheduleAutosave();
    }
  }

  function removeScene(id: string): void {
    if (!project.value) return;

    project.value.story.scenes = project.value.story.scenes.filter((s) => s.id !== id);
    project.value.story.updated_at = Date.now() / 1000;
    scheduleAutosave();
  }

  function reorderScenes(sceneIds: string[]): void {
    if (!project.value) return;

    const scenesMap = new Map(project.value.story.scenes.map((s) => [s.id, s]));
    project.value.story.scenes = sceneIds
      .map((id, index) => {
        const scene = scenesMap.get(id);
        if (scene) {
          scene.order = index;
          return scene;
        }
        return null;
      })
      .filter((s): s is StoryScene => s !== null);

    project.value.story.updated_at = Date.now() / 1000;
    scheduleAutosave();
  }

  // ─────────────────────────────────────────────────────────────────────
  // Timeline Management
  // ─────────────────────────────────────────────────────────────────────

  async function updateTimeline(newTimeline: Timeline): Promise<void> {
    if (!project.value) return;

    const response = await sendControlMessage<{
      success: boolean;
      project?: VideoProject;
    }>('ve_update_timeline', {
      projectId: project.value.id,
      timeline: newTimeline,
    });

    if (response.success && response.project) {
      project.value = response.project;
      isDirty.value = false;
    }
  }

  function addClip(clip: Omit<TimelineClip, 'id'>): void {
    if (!project.value) return;

    const newClip: TimelineClip = {
      ...clip,
      id: crypto.randomUUID(),
    };

    project.value.timeline.clips.push(newClip);
    recalculateTimelineDuration();
    scheduleAutosave();
  }

  function updateClip(id: string, updates: Partial<TimelineClip>): void {
    if (!project.value) return;

    const index = project.value.timeline.clips.findIndex((c) => c.id === id);
    if (index >= 0) {
      const existing = project.value.timeline.clips[index];
      if (!existing) return;

      project.value.timeline.clips[index] = {
        ...existing,
        ...updates,
      };
      recalculateTimelineDuration();
      scheduleAutosave();
    }
  }

  function removeClip(id: string): void {
    if (!project.value) return;

    project.value.timeline.clips = project.value.timeline.clips.filter((c) => c.id !== id);
    recalculateTimelineDuration();
    scheduleAutosave();
  }

  function recalculateTimelineDuration(): void {
    if (!project.value) return;

    const clips = project.value.timeline.clips;
    if (clips.length === 0) {
      project.value.timeline.total_duration = 0;
    } else {
      project.value.timeline.total_duration = Math.max(
        ...clips.map((c) => c.start_time + c.duration),
      );
    }
  }

  // ─────────────────────────────────────────────────────────────────────
  // Deep Watcher for Autosave
  // ─────────────────────────────────────────────────────────────────────

  // Watch for any deep changes to the project and trigger autosave.
  // This catches direct mutations (e.g., v-model on story.title).
  watch(
    project,
    () => {
      // Don't trigger autosave when:
      // - No project open
      // - Applying server state (after save response)
      // - Already saving
      if (!project.value || isApplyingServerState || isSaving.value) {
        return;
      }
      scheduleAutosave();
    },
    { deep: true },
  );

  // ─────────────────────────────────────────────────────────────────────
  // Initialize
  // ─────────────────────────────────────────────────────────────────────

  // Note: loadRecentProjects() should be called from VideoEditorLayout component
  // after ensuring the WebSocket connection is ready to avoid race conditions

  return {
    // State
    project,
    recentProjects,
    isLoading,
    error,
    isDirty,
    isSaving,
    lastSaveError,

    // Computed
    isOpen,
    projectId,
    projectName,
    settings,
    library,
    story,
    timeline,

    // Project operations
    createProject,
    openProject,
    saveProject,
    closeProject,
    loadRecentProjects,
    checkFolder,

    // Settings
    updateSettings,

    // Library
    updateLibrary,
    addCharacter,
    updateCharacter,
    removeCharacter,
    addProduct,
    addVoice,

    // Story
    updateStory,
    addScene,
    updateScene,
    removeScene,
    reorderScenes,

    // Timeline
    updateTimeline,
    addClip,
    updateClip,
    removeClip,

    // Autosave
    markDirty,
  };
});
