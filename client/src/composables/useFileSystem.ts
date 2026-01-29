import { computed } from 'vue';
import { useProjectStore } from '../stores/project';
import { useLocalCompanionStore } from '../stores/localCompanion';

export function useFileSystem() {
  const projectStore = useProjectStore();
  const companionStore = useLocalCompanionStore();

  // With backend-only, support depends on companion connection
  const isSupported = computed(() => companionStore.isConnected);

  /**
   * Add a folder to the project.
   * @param systemPath System path from local companion (required)
   */
  async function addFolder(systemPath: string) {
    try {
      await projectStore.addFolder(systemPath);
      return true;
    } catch (error) {
      console.error('Failed to add folder:', error);
      return false;
    }
  }

  return {
    isSupported,
    addFolder,
    hasActiveProject: projectStore.hasActiveProject,
    hasFolders: projectStore.hasFolders,
    fileTree: projectStore.fileTree,
    isLoading: projectStore.isLoading,
  };
}

