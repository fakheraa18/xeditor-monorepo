import { defineStore } from 'pinia';
import { ref, computed } from 'vue';

// Types for streaming state with sequence tracking
interface StreamState {
  id: string;
  lastSeq: number;
  onChunk: (chunk: unknown) => void;
  resolve: (val: unknown) => void;
  reject: (err: unknown) => void;
  timeoutId?: ReturnType<typeof setTimeout>;
  payload: unknown; // Store original payload for resume
  type: string; // Store original type for resume
}

export const useLocalCompanionStore = defineStore('localCompanion', () => {
  // Get port from Electron bridge if available (single source of truth), otherwise fall back to localStorage/default
  const getInitialPort = (): number => {
    if (typeof window !== 'undefined') {
      // Type assertion for Electron bridge (only available in Electron context)
      const electronBridge = (window as unknown as { xeditor?: { companionPort: number } }).xeditor;
      if (electronBridge?.companionPort) {
        return electronBridge.companionPort;
      }
    }
    return parseInt(localStorage.getItem('xeditor.companion.port') || '8000');
  };

  const port = ref(getInitialPort());
  const huggingFaceToken = ref<string>(localStorage.getItem('xeditor.companion.hfToken') || '');
  const isConnected = ref(false);
  const isConnecting = ref(false);
  const error = ref<string | null>(null);

  // Dual WebSocket connections
  // Stream: handles chat_message, llm_stream_request_v2, cancel, stream_resume
  // Control: handles all other RPC operations and receives file_changed events
  let streamWs: WebSocket | null = null;
  let controlWs: WebSocket | null = null;
  let streamConnectPromise: Promise<boolean> | null = null;
  let controlConnectPromise: Promise<boolean> | null = null;

  // Request tracking
  const pendingRequests = new Map<
    string,
    { resolve: (val: unknown) => void; reject: (err: unknown) => void }
  >();
  const streamingRequests = new Map<string, StreamState>();
  const indexProgressCallbacks = new Map<string, (progress: unknown) => void>();

  // URL computed properties
  const streamWsUrl = computed(() => `ws://localhost:${port.value}/ws/stream`);
  const controlWsUrl = computed(() => `ws://localhost:${port.value}/ws/control`);

  // For backward compatibility - expose url as the control endpoint
  const url = computed(() => controlWsUrl.value);

  // Try to connect on startup
  void connect();

  function setPort(newPort: number | string | null) {
    if (newPort === null) return;
    const portNum = typeof newPort === 'string' ? parseInt(newPort) : newPort;
    if (isNaN(portNum)) return;

    port.value = portNum;
    localStorage.setItem('xeditor.companion.port', portNum.toString());
    if (isConnected.value) {
      disconnect();
      void connect();
    }
  }

  function setHuggingFaceToken(token: string | number | null) {
    const normalized = token === null ? '' : String(token);
    huggingFaceToken.value = normalized;
    localStorage.setItem('xeditor.companion.hfToken', normalized);
  }

  /**
   * Main connect function - connects to both stream and control WebSockets
   */
  async function connect(): Promise<boolean> {
    // If already connected, return immediately
    if (isConnected.value) {
      return true;
    }

    isConnecting.value = true;
    error.value = null;

    try {
      // Connect to both WebSockets in parallel
      console.log('Connecting to /ws/stream and /ws/control');
      const [streamOk, controlOk] = await Promise.all([connectStreamWs(), connectControlWs()]);
      isConnected.value = streamOk && controlOk;

      if (!isConnected.value) {
        error.value = 'Failed to connect to Local Companion. Make sure the server is running.';
      }

      isConnecting.value = false;
      return isConnected.value;
    } catch (e) {
      error.value = (e as Error).message;
      isConnecting.value = false;
      isConnected.value = false;
      return false;
    }
  }

  /**
   * Connect to the stream WebSocket (/ws/stream)
   */
  async function connectStreamWs(): Promise<boolean> {
    if (streamWs?.readyState === WebSocket.OPEN) {
      return true;
    }

    if (streamWs?.readyState === WebSocket.CONNECTING && streamConnectPromise) {
      return await streamConnectPromise;
    }

    if (
      streamWs &&
      (streamWs.readyState === WebSocket.CLOSING || streamWs.readyState === WebSocket.CLOSED)
    ) {
      streamWs = null;
      streamConnectPromise = null;
    }

    streamConnectPromise = new Promise<boolean>((resolve) => {
      try {
        streamWs = new WebSocket(streamWsUrl.value);

        streamWs.onopen = () => {
          console.log('Connected to Local Companion (stream)');
          // Attempt to resume any interrupted streams
          void resumeInterruptedStreams();
          resolve(true);
        };

        streamWs.onmessage = (event) => handleMessage(event.data, 'stream');

        streamWs.onclose = () => {
          console.log('Disconnected from Local Companion (stream)');
          handleWebSocketClose('stream');
          // Attempt to reconnect stream WebSocket
          scheduleReconnect('stream');
        };

        streamWs.onerror = () => {
          error.value = 'Failed to connect to stream WebSocket';
          resolve(false);
        };
      } catch (e) {
        error.value = (e as Error).message;
        resolve(false);
      }
    });

    return streamConnectPromise;
  }

  /**
   * Connect to the control WebSocket (/ws/control)
   */
  async function connectControlWs(): Promise<boolean> {
    if (controlWs?.readyState === WebSocket.OPEN) {
      return true;
    }

    if (controlWs?.readyState === WebSocket.CONNECTING && controlConnectPromise) {
      return await controlConnectPromise;
    }

    if (
      controlWs &&
      (controlWs.readyState === WebSocket.CLOSING || controlWs.readyState === WebSocket.CLOSED)
    ) {
      controlWs = null;
      controlConnectPromise = null;
    }

    controlConnectPromise = new Promise<boolean>((resolve) => {
      try {
        controlWs = new WebSocket(controlWsUrl.value);

        controlWs.onopen = () => {
          console.log('Connected to Local Companion (control)');
          resolve(true);
        };

        controlWs.onmessage = (event) => handleMessage(event.data, 'control');

        controlWs.onclose = () => {
          console.log('Disconnected from Local Companion (control)');
          handleWebSocketClose('control');
          // Attempt to reconnect control WebSocket
          scheduleReconnect('control');
        };

        controlWs.onerror = () => {
          error.value = 'Failed to connect to control WebSocket';
          resolve(false);
        };
      } catch (e) {
        error.value = (e as Error).message;
        resolve(false);
      }
    });

    return controlConnectPromise;
  }

  /**
   * Handle incoming WebSocket messages
   */
  function handleMessage(data: string, source: 'stream' | 'control') {
    try {
      const message = JSON.parse(data);
      const { type, id, payload, seq } = message;

      // Handle keepalive ping messages
      if (type === 'keepalive_ping') {
        resetStreamTimeouts();
        return;
      }

      // Handle chat streaming events (with sequence tracking)
      if (type === 'chat_event' && streamingRequests.has(id)) {
        const req = streamingRequests.get(id)!;
        // Track sequence number for resumption
        if (typeof seq === 'number') {
          req.lastSeq = seq;
        }
        resetStreamTimeout(id);
        if (payload) {
          req.onChunk(payload);
        }
        return;
      }

      // Handle LLM streaming chunks (with sequence tracking)
      if (type === 'llm_stream_chunk' && streamingRequests.has(id)) {
        const req = streamingRequests.get(id)!;
        if (typeof seq === 'number') {
          req.lastSeq = seq;
        }
        resetStreamTimeout(id);
        if (payload) {
          req.onChunk(payload);
        }
        return;
      }

      // Handle streaming end
      if (type === 'llm_stream_end' && streamingRequests.has(id)) {
        const req = streamingRequests.get(id)!;
        if (req.timeoutId) clearTimeout(req.timeoutId);
        streamingRequests.delete(id);
        req.resolve(payload);
        return;
      }

      // Handle cancellation acknowledgment
      if (type === 'cancel_ack' && streamingRequests.has(id)) {
        const req = streamingRequests.get(id)!;
        if (req.timeoutId) clearTimeout(req.timeoutId);
        streamingRequests.delete(id);
        req.resolve({ ...payload, cancelled: true });
        return;
      }

      // Handle stream resume response
      if (type === 'stream_resume_response') {
        console.log(`Stream resume result for ${id}:`, payload);
        return;
      }

      // Handle index progress updates
      if (type === 'index_progress' && indexProgressCallbacks.has(id)) {
        const callback = indexProgressCallbacks.get(id)!;
        callback(payload);
        return;
      }

      // Handle index build completion
      if (type === 'index_build_response' && pendingRequests.has(id)) {
        const { resolve: reqResolve } = pendingRequests.get(id)!;
        pendingRequests.delete(id);
        indexProgressCallbacks.delete(id);
        reqResolve(payload);
        return;
      }

      // Handle index folders completion
      if (type === 'index_folders_response' && pendingRequests.has(id)) {
        const { resolve: reqResolve } = pendingRequests.get(id)!;
        pendingRequests.delete(id);
        indexProgressCallbacks.delete(id);
        reqResolve(payload);
        return;
      }

      // Handle file_changed push events (control only - never from stream)
      if (type === 'file_changed' && payload && source === 'control') {
        const filePath = payload.path as string;
        const changeType = payload.changeType as 'created' | 'modified' | 'deleted';
        const projectId = payload.projectId as string;
        const isAbsolute = (payload.isAbsolute as boolean) ?? false;

        // Always notify editor store to refresh open tabs (for both project and absolute paths)
        void import('../apps/CodeEditor/stores/editor').then(({ useEditorStore }) => {
          const editorStore = useEditorStore();
          void editorStore.handleExternalFileChanged(filePath, changeType, isAbsolute);
        });

        // Only refresh file tree and index for project files (when projectId matches active project)
        if (projectId && !isAbsolute) {
          void import('../apps/CodeEditor/stores/project').then(({ useProjectStore }) => {
            const projectStore = useProjectStore();
            if (projectStore.activeProjectId === projectId) {
              void projectStore.refreshFileTree();
              void import('../apps/CodeEditor/stores/indexing').then(({ useIndexingStore }) => {
                const indexingStore = useIndexingStore();
                void indexingStore.incrementalIndex(projectId, filePath, changeType);
              });
            }
          });
        }
        return;
      }

      // Handle regular requests
      if (pendingRequests.has(id)) {
        const { resolve: reqResolve, reject: reqReject } = pendingRequests.get(id)!;
        pendingRequests.delete(id);

        if (type === 'error') {
          reqReject(new Error(message.message || 'Unknown companion error'));
        } else {
          reqResolve(payload);
        }
        return;
      }

      // Handle streaming errors
      if (type === 'error' && streamingRequests.has(id)) {
        const req = streamingRequests.get(id)!;
        if (req.timeoutId) clearTimeout(req.timeoutId);
        streamingRequests.delete(id);
        req.reject(new Error(message.message || 'Unknown companion error'));
        return;
      }
    } catch (e) {
      console.error('Failed to parse companion message:', e);
    }
  }

  /**
   * Reset timeout for a specific stream
   */
  function resetStreamTimeout(id: string) {
    const req = streamingRequests.get(id);
    if (!req) return;

    if (req.timeoutId) {
      clearTimeout(req.timeoutId);
    }
    req.timeoutId = setTimeout(() => {
      if (streamingRequests.has(id)) {
        streamingRequests.delete(id);
        req.reject(new Error('Companion stream request timeout after 15 minutes of inactivity.'));
      }
    }, 900000); // 15 minutes
  }

  /**
   * Reset timeouts for all active streams
   */
  function resetStreamTimeouts() {
    streamingRequests.forEach((_, id) => resetStreamTimeout(id));
  }

  /**
   * Handle WebSocket close event
   */
  function handleWebSocketClose(source: 'stream' | 'control') {
    if (source === 'stream') {
      streamWs = null;
      streamConnectPromise = null;
      // Don't reject streaming requests immediately - they can be resumed
      console.log(
        `Stream WebSocket closed. ${streamingRequests.size} active streams pending resume.`,
      );
    } else if (source === 'control') {
      controlWs = null;
      controlConnectPromise = null;
      // Reject pending control requests
      pendingRequests.forEach(({ reject }) => reject(new Error('Control connection closed')));
      pendingRequests.clear();
      indexProgressCallbacks.clear();
    }

    // Update overall connection state
    isConnected.value =
      streamWs?.readyState === WebSocket.OPEN && controlWs?.readyState === WebSocket.OPEN;
  }

  /**
   * Schedule reconnection for a WebSocket
   */
  function scheduleReconnect(target: 'stream' | 'control') {
    setTimeout(() => {
      console.log(`Attempting to reconnect ${target} WebSocket...`);
      if (target === 'stream') {
        void connectStreamWs();
      } else {
        void connectControlWs();
      }
    }, 3000);
  }

  /**
   * Resume interrupted streams after reconnection
   */
  function resumeInterruptedStreams() {
    if (streamingRequests.size === 0) return;
    if (!streamWs || streamWs.readyState !== WebSocket.OPEN) return;

    console.log(`Attempting to resume ${streamingRequests.size} interrupted streams`);

    for (const [id, state] of streamingRequests) {
      try {
        streamWs.send(
          JSON.stringify({
            type: 'stream_resume',
            id,
            payload: {
              streamId: id,
              fromSeq: state.lastSeq,
            },
          }),
        );
        console.log(`Sent resume request for stream ${id} from seq ${state.lastSeq}`);
      } catch (e) {
        console.error(`Failed to resume stream ${id}:`, e);
      }
    }
  }

  function disconnect() {
    if (streamWs) {
      streamWs.close();
      streamWs = null;
    }
    if (controlWs) {
      controlWs.close();
      controlWs = null;
    }
    isConnected.value = false;
  }

  /**
   * Send a regular RPC request (uses control WebSocket)
   */
  async function request<T = unknown>(
    type: string,
    payload: unknown,
    onProgress?: (progress: unknown) => void,
  ): Promise<T> {
    // Ensure connection is open before sending
    if (!controlWs || controlWs.readyState !== WebSocket.OPEN) {
      const ok = await connect();
      if (!ok) throw new Error('Not connected to Local Companion');
    }

    if (!controlWs || controlWs.readyState !== WebSocket.OPEN) {
      throw new Error('Control WebSocket is not open');
    }

    const id = Math.random().toString(36).substring(7);

    // Register progress callback if provided (for indexing)
    if (onProgress && (type === 'index_build' || type === 'index_folders')) {
      indexProgressCallbacks.set(id, onProgress);
    }

    return new Promise((resolve, reject) => {
      pendingRequests.set(id, {
        resolve: resolve as (val: unknown) => void,
        reject,
      });

      try {
        controlWs!.send(JSON.stringify({ type, id, payload }));
      } catch (err) {
        pendingRequests.delete(id);
        indexProgressCallbacks.delete(id);
        reject(
          new Error(`Failed to send request: ${err instanceof Error ? err.message : String(err)}`),
        );
        return;
      }

      // Timeout after 60 seconds (or 5 minutes for indexing)
      const timeout = type === 'index_build' || type === 'index_folders' ? 300000 : 60000;
      setTimeout(() => {
        if (pendingRequests.has(id)) {
          pendingRequests.delete(id);
          indexProgressCallbacks.delete(id);
          reject(new Error('Companion request timeout'));
        }
      }, timeout);
    });
  }

  /**
   * Send a streaming request (uses stream WebSocket)
   */
  async function streamRequest<T = unknown>(
    type: string,
    payload: unknown,
    onChunk: (chunk: T) => void,
    signal?: AbortSignal,
  ): Promise<T> {
    // Ensure connection is open before sending
    if (!streamWs || streamWs.readyState !== WebSocket.OPEN) {
      const ok = await connect();
      if (!ok) throw new Error('Not connected to Local Companion');
    }

    if (!streamWs || streamWs.readyState !== WebSocket.OPEN) {
      throw new Error('Stream WebSocket is not open');
    }

    const id = Math.random().toString(36).substring(7);

    return new Promise((resolve, reject) => {
      // Timeout after 15 minutes of inactivity
      const timeoutId = setTimeout(() => {
        if (streamingRequests.has(id)) {
          streamingRequests.delete(id);
          reject(new Error('Companion stream request timeout after 15 minutes of inactivity.'));
        }
      }, 900000);

      const streamState: StreamState = {
        id,
        lastSeq: 0,
        onChunk: onChunk as (chunk: unknown) => void,
        resolve: (val: unknown) => {
          clearTimeout(timeoutId);
          resolve(val as T | PromiseLike<T>);
        },
        reject: (err: unknown) => {
          clearTimeout(timeoutId);
          reject(err instanceof Error ? err : new Error(String(err)));
        },
        timeoutId,
        payload,
        type,
      };

      streamingRequests.set(id, streamState);

      // Handle abort signal
      if (signal) {
        signal.addEventListener('abort', () => {
          if (streamWs && streamWs.readyState === WebSocket.OPEN) {
            try {
              streamWs.send(JSON.stringify({ type: 'cancel', id }));
            } catch (err) {
              console.warn('Failed to send cancel message:', err);
            }
          }
          if (streamingRequests.has(id)) {
            clearTimeout(timeoutId);
            streamingRequests.delete(id);
            resolve({ cancelled: true } as T);
          }
        });
      }

      try {
        streamWs!.send(JSON.stringify({ type, id, payload }));
      } catch (err) {
        clearTimeout(timeoutId);
        streamingRequests.delete(id);
        reject(
          new Error(
            `Failed to send stream request: ${err instanceof Error ? err.message : String(err)}`,
          ),
        );
        return;
      }
    });
  }

  return {
    port,
    huggingFaceToken,
    isConnected,
    isConnecting,
    error,
    url,
    setPort,
    setHuggingFaceToken,
    connect,
    disconnect,
    request,
    streamRequest,
  };
});
