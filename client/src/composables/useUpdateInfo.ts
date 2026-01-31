import { ref, onMounted } from 'vue';
import axios from 'axios';
import packageJson from '../../package.json';

export interface UpdateInfoResponse {
  text?: string;
  link?: string;
  version?: string;
  message?: string;
  [key: string]: unknown; // For extensibility
}

const API_ENDPOINT = 'https://xavoc.com/xeditor/api/update-info';
const REQUEST_TIMEOUT = 5000; // 5 seconds

/**
 * Composable for fetching and managing update information
 */
export function useUpdateInfo() {
  const updateInfo = ref<UpdateInfoResponse | null>(null);
  const isLoading = ref(false);

  async function fetchUpdateInfo(): Promise<void> {
    isLoading.value = true;
    try {
      const response = await axios.post<UpdateInfoResponse>(
        API_ENDPOINT,
        { version: packageJson.version },
        {
          timeout: REQUEST_TIMEOUT,
          headers: {
            'Content-Type': 'application/json',
          },
        },
      );

      // Only set updateInfo if response has meaningful data
      if (
        response.data &&
        (response.data.text || response.data.message || response.data.version || response.data.link)
      ) {
        updateInfo.value = response.data;
      } else {
        updateInfo.value = null;
      }
    } catch (_error) {
      // Gracefully handle all errors - silently fail
      // No error messages shown to user
      updateInfo.value = null;
    } finally {
      isLoading.value = false;
    }
  }

  // Fetch on mount
  onMounted(() => {
    void fetchUpdateInfo();
  });

  function handleLinkClick(link: string): void {
    if (link) {
      window.open(link, '_blank', 'noopener,noreferrer');
    }
  }

  return {
    updateInfo,
    isLoading,
    fetchUpdateInfo,
    handleLinkClick,
  };
}
