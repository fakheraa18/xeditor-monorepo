/**
 * Video Editor Companion Store
 *
 * Manages WebSocket connections to the video editor endpoints:
 * - /video-editor/ws/ve/control: RPC operations
 * - /video-editor/ws/ve/stream: Streaming operations (jobs)
 *
 * This is separate from the code editor's localCompanion to maintain
 * separation of concerns.
 */

import { defineStore } from 'pinia';
import { ref, computed } from 'vue';
import { useLocalCompanionStore } from '../../../stores/localCompanion';

interface PendingRequest {
  resolve: (val: unknown) => void;
  reject: (err: unknown) => void;
  timeoutId?: ReturnType<typeof setTimeout>;
}

interface JobProgressHandler {
  (event: { projectId: string; event: Record<string, unknown> }): void;
}

export const useVideoCompanionStore = defineStore('videoCompanion', () => {
  // Get port from the main companion store
  const localCompanion = useLocalCompanionStore();

  // Connection state
  const isConnected = ref(false);
  const isConnecting = ref(false);
  const error = ref<string | null>(null);

  // WebSocket connections
  let controlWs: WebSocket | null = null;
  let streamWs: WebSocket | null = null;

  // Request tracking
  const pendingRequests = new Map<string, PendingRequest>();
  let requestCounter = 0;

  // Job progress handlers
  const jobProgressHandlers: JobProgressHandler[] = [];

  // WebSocket URLs
  const controlWsUrl = computed(
    () => `ws://localhost:${localCompanion.port}/video-editor/ws/ve/control`,
  );
  const streamWsUrl = computed(
    () => `ws://localhost:${localCompanion.port}/video-editor/ws/ve/stream`,
  );

  /**
   * Connect to both WebSocket endpoints
   */
  async function connect(): Promise<boolean> {
    if (isConnected.value) return true;
    if (isConnecting.value) return false;

    isConnecting.value = true;
    error.value = null;

    try {
      const [controlOk, streamOk] = await Promise.all([connectControlWs(), connectStreamWs()]);

      isConnected.value = controlOk && streamOk;

      if (!isConnected.value) {
        error.value = 'Failed to connect to Video Editor companion';
      }

      return isConnected.value;
    } catch (e) {
      error.value = (e as Error).message;
      return false;
    } finally {
      isConnecting.value = false;
    }
  }

  /**
   * Connect to the control WebSocket
   */
  async function connectControlWs(): Promise<boolean> {
    if (controlWs?.readyState === WebSocket.OPEN) return true;

    return new Promise((resolve) => {
      try {
        controlWs = new WebSocket(controlWsUrl.value);

        controlWs.onopen = () => {
          console.log('[VideoEditor] Connected to control WebSocket');
          resolve(true);
        };

        controlWs.onmessage = (event) => handleControlMessage(event.data);

        controlWs.onclose = () => {
          console.log('[VideoEditor] Control WebSocket closed');
          handleDisconnect();
        };

        controlWs.onerror = () => {
          resolve(false);
        };

        // Timeout after 5 seconds
        setTimeout(() => {
          if (controlWs?.readyState !== WebSocket.OPEN) {
            controlWs?.close();
            resolve(false);
          }
        }, 5000);
      } catch {
        resolve(false);
      }
    });
  }

  /**
   * Connect to the stream WebSocket
   */
  async function connectStreamWs(): Promise<boolean> {
    if (streamWs?.readyState === WebSocket.OPEN) return true;

    return new Promise((resolve) => {
      try {
        streamWs = new WebSocket(streamWsUrl.value);

        streamWs.onopen = () => {
          console.log('[VideoEditor] Connected to stream WebSocket');
          resolve(true);
        };

        streamWs.onmessage = (event) => handleStreamMessage(event.data);

        streamWs.onclose = () => {
          console.log('[VideoEditor] Stream WebSocket closed');
          handleDisconnect();
        };

        streamWs.onerror = () => {
          resolve(false);
        };

        // Timeout after 5 seconds
        setTimeout(() => {
          if (streamWs?.readyState !== WebSocket.OPEN) {
            streamWs?.close();
            resolve(false);
          }
        }, 5000);
      } catch {
        resolve(false);
      }
    });
  }

  /**
   * Handle control WebSocket messages
   */
  function handleControlMessage(data: string): void {
    try {
      const message = JSON.parse(data);
      const requestId = message.id;

      if (requestId && pendingRequests.has(requestId)) {
        const pending = pendingRequests.get(requestId)!;
        pendingRequests.delete(requestId);

        if (pending.timeoutId) {
          clearTimeout(pending.timeoutId);
        }

        if (message.type === 'error') {
          pending.reject(new Error(message.message || 'Request failed'));
        } else {
          pending.resolve(message.payload);
        }
      }
    } catch (e) {
      console.error('[VideoEditor] Failed to parse control message:', e);
    }
  }

  /**
   * Handle stream WebSocket messages
   */
  function handleStreamMessage(data: string): void {
    try {
      const message = JSON.parse(data);
      const requestId = message.id;

      // Handle job progress events
      if (message.type === 've_job_progress') {
        for (const handler of jobProgressHandlers) {
          handler(message.payload);
        }
        return;
      }

      // Handle response messages
      if (requestId && pendingRequests.has(requestId)) {
        const pending = pendingRequests.get(requestId)!;
        pendingRequests.delete(requestId);

        if (pending.timeoutId) {
          clearTimeout(pending.timeoutId);
        }

        if (message.type === 'error') {
          pending.reject(new Error(message.message || 'Request failed'));
        } else {
          pending.resolve(message.payload);
        }
      }
    } catch (e) {
      console.error('[VideoEditor] Failed to parse stream message:', e);
    }
  }

  /**
   * Handle disconnection
   */
  function handleDisconnect(): void {
    isConnected.value = false;

    // Reject all pending requests
    for (const [id, pending] of pendingRequests) {
      if (pending.timeoutId) {
        clearTimeout(pending.timeoutId);
      }
      pending.reject(new Error('Connection lost'));
      pendingRequests.delete(id);
    }

    // Try to reconnect after a delay
    setTimeout(() => {
      if (!isConnected.value && !isConnecting.value) {
        void connect();
      }
    }, 3000);
  }

  /**
   * Disconnect from both WebSockets
   */
  function disconnect(): void {
    controlWs?.close();
    streamWs?.close();
    controlWs = null;
    streamWs = null;
    isConnected.value = false;
  }

  /**
   * Generate a unique request ID
   */
  function generateRequestId(): string {
    return `ve_${++requestCounter}_${Math.random().toString(36).substring(2, 8)}`;
  }

  /**
   * Send a request to the control WebSocket and wait for response
   */
  async function request<T = unknown>(
    type: string,
    payload: Record<string, unknown> = {},
    timeout: number = 30000,
  ): Promise<T> {
    // Ensure we're connected
    if (!isConnected.value) {
      const connected = await connect();
      if (!connected) {
        throw new Error('Not connected to Video Editor companion');
      }
    }

    if (!controlWs || controlWs.readyState !== WebSocket.OPEN) {
      throw new Error('Control WebSocket not connected');
    }

    const requestId = generateRequestId();

    return new Promise((resolve, reject) => {
      const timeoutId = setTimeout(() => {
        pendingRequests.delete(requestId);
        reject(new Error(`Request ${type} timed out`));
      }, timeout);

      pendingRequests.set(requestId, {
        resolve: resolve as (val: unknown) => void,
        reject,
        timeoutId,
      });

      controlWs!.send(
        JSON.stringify({
          type,
          id: requestId,
          payload,
        }),
      );
    });
  }

  /**
   * Send a request to the stream WebSocket and wait for response
   */
  async function streamRequest<T = unknown>(
    type: string,
    payload: Record<string, unknown> = {},
    timeout: number = 30000,
  ): Promise<T> {
    // Ensure we're connected
    if (!isConnected.value) {
      const connected = await connect();
      if (!connected) {
        throw new Error('Not connected to Video Editor companion');
      }
    }

    if (!streamWs || streamWs.readyState !== WebSocket.OPEN) {
      throw new Error('Stream WebSocket not connected');
    }

    const requestId = generateRequestId();

    return new Promise((resolve, reject) => {
      const timeoutId = setTimeout(() => {
        pendingRequests.delete(requestId);
        reject(new Error(`Request ${type} timed out`));
      }, timeout);

      pendingRequests.set(requestId, {
        resolve: resolve as (val: unknown) => void,
        reject,
        timeoutId,
      });

      streamWs!.send(
        JSON.stringify({
          type,
          id: requestId,
          payload,
        }),
      );
    });
  }

  /**
   * Register a handler for job progress events
   */
  function onJobProgress(handler: JobProgressHandler): () => void {
    jobProgressHandlers.push(handler);
    return () => {
      const index = jobProgressHandlers.indexOf(handler);
      if (index >= 0) {
        jobProgressHandlers.splice(index, 1);
      }
    };
  }

  // ─────────────────────────────────────────────────────────────────────────
  // HTTP Asset helpers
  // ─────────────────────────────────────────────────────────────────────────

  const assetsBaseUrl = computed(
    () => `http://localhost:${localCompanion.port}/video-editor/assets`,
  );

  /**
   * Upload a file as a project asset (via HTTP multipart)
   */
  async function uploadAsset(
    projectId: string,
    file: File,
    options?: {
      assetType?: string;
      subfolder?: string;
      customName?: string;
    },
  ): Promise<{
    success: boolean;
    asset_id?: string;
    path?: string;
    asset_type?: string;
    metadata?: Record<string, unknown>;
    error?: string;
  }> {
    const formData = new FormData();
    formData.append('file', file);
    formData.append('project_id', projectId);
    if (options?.assetType) formData.append('asset_type', options.assetType);
    if (options?.subfolder) formData.append('subfolder', options.subfolder);
    if (options?.customName) formData.append('custom_name', options.customName);

    const response = await fetch(`${assetsBaseUrl.value}/upload`, {
      method: 'POST',
      body: formData,
    });
    return response.json();
  }

  /**
   * Get a URL to serve an asset file
   */
  function getAssetUrl(projectId: string, path: string): string {
    return `${assetsBaseUrl.value}/file?project_id=${encodeURIComponent(projectId)}&path=${encodeURIComponent(path)}`;
  }

  /**
   * Get a URL for an asset thumbnail
   */
  function getAssetThumbUrl(projectId: string, path: string, size = 256): string {
    return `${assetsBaseUrl.value}/thumb?project_id=${encodeURIComponent(projectId)}&path=${encodeURIComponent(path)}&size=${size}`;
  }

  /**
   * Delete an asset
   */
  async function deleteAsset(
    projectId: string,
    assetId: string,
  ): Promise<{ success: boolean; error?: string }> {
    const response = await fetch(
      `${assetsBaseUrl.value}/delete?project_id=${encodeURIComponent(projectId)}&asset_id=${encodeURIComponent(assetId)}`,
      { method: 'DELETE' },
    );
    return response.json();
  }

  // Try to connect on store creation
  void connect();

  return {
    // State
    isConnected,
    isConnecting,
    error,

    // Methods
    connect,
    disconnect,
    request,
    streamRequest,
    onJobProgress,

    // HTTP Asset helpers
    assetsBaseUrl,
    uploadAsset,
    getAssetUrl,
    getAssetThumbUrl,
    deleteAsset,
  };
});
