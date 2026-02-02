import { ref, computed } from 'vue';
import { useChatStore } from '../../../../stores/chat';

export function useChatHistory() {
  const chatStore = useChatStore();
  const historySearch = ref('');
  const isLoadingSession = ref(false);

  const filteredSessions = computed(() => {
    if (!historySearch.value.trim()) {
      return chatStore.sessions;
    }
    const search = historySearch.value.toLowerCase();
    return chatStore.sessions.filter((session) => session.title.toLowerCase().includes(search));
  });

  function formatDate(timestamp: number): string {
    const date = new Date(timestamp);
    const now = new Date();
    const diffMs = now.getTime() - date.getTime();
    const diffDays = Math.floor(diffMs / (1000 * 60 * 60 * 24));

    if (diffDays === 0) {
      return date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
    } else if (diffDays === 1) {
      return 'Yesterday';
    } else if (diffDays < 7) {
      return date.toLocaleDateString([], { weekday: 'short' });
    } else {
      return date.toLocaleDateString([], { month: 'short', day: 'numeric' });
    }
  }

  async function handleLoadSession(sessionId: string) {
    isLoadingSession.value = true;
    try {
      await chatStore.loadSession(sessionId);
      // Scrolling will be handled by ChatMessages watch on session.id
    } finally {
      isLoadingSession.value = false;
    }
  }

  async function handleRenameSession(sessionId: string) {
    const session = chatStore.sessions.find((s) => s.id === sessionId);
    if (!session) return;

    const newTitle = prompt('Enter new title:', session.title);
    if (newTitle && newTitle.trim()) {
      await chatStore.renameSession(sessionId, newTitle.trim());
    }
  }

  async function handleDeleteSession(sessionId: string) {
    if (confirm('Delete this chat session?')) {
      await chatStore.deleteSessionById(sessionId);
    }
  }

  return {
    historySearch,
    filteredSessions,
    formatDate,
    isLoadingSession,
    handleLoadSession,
    handleRenameSession,
    handleDeleteSession,
  };
}
