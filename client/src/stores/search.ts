import { defineStore } from 'pinia';
import { ref } from 'vue';

export const useSearchStore = defineStore('search', () => {
  const includePattern = ref('');
  const excludePattern = ref('**/node_modules/**, **/.git/**');
  const isSearchModalOpen = ref(false);

  function setIncludePattern(pattern: string) {
    includePattern.value = pattern;
  }

  function setExcludePattern(pattern: string) {
    excludePattern.value = pattern;
  }

  function toggleSearchModal(open?: boolean) {
    if (open !== undefined) {
      isSearchModalOpen.value = open;
    } else {
      isSearchModalOpen.value = !isSearchModalOpen.value;
    }
  }

  return {
    includePattern,
    excludePattern,
    isSearchModalOpen,
    setIncludePattern,
    setExcludePattern,
    toggleSearchModal,
  };
});

