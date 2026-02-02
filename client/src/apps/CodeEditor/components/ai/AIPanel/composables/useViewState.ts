import { ref, computed } from 'vue';

export function useViewState() {
  const showHistoryView = ref(false);
  const showSetsView = ref(false);

  const isChatView = computed(() => !showHistoryView.value && !showSetsView.value);
  const currentView = computed(() => {
    if (showHistoryView.value) return 'history';
    if (showSetsView.value) return 'sets';
    return 'chat';
  });

  function showHistory() {
    showHistoryView.value = true;
    showSetsView.value = false;
  }

  function showSets() {
    showSetsView.value = true;
    showHistoryView.value = false;
  }

  function showChat() {
    showHistoryView.value = false;
    showSetsView.value = false;
  }

  function toggleHistory() {
    if (showHistoryView.value) {
      showChat();
    } else {
      showHistory();
    }
  }

  function toggleSets() {
    if (showSetsView.value) {
      showChat();
    } else {
      showSets();
    }
  }

  return {
    showHistoryView,
    showSetsView,
    isChatView,
    currentView,
    showHistory,
    showSets,
    showChat,
    toggleHistory,
    toggleSets,
  };
}
