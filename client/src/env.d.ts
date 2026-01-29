declare namespace NodeJS {
  interface ProcessEnv {
    NODE_ENV: string;
    VUE_ROUTER_MODE: 'hash' | 'history' | 'abstract' | undefined;
    VUE_ROUTER_BASE: string | undefined;
  }
}

declare module '#q-app/wrappers' {
  import type { App } from 'vue';
  import type { Pinia } from 'pinia';
  export function defineConfig<T>(config: T): T;
  export function defineBoot<T>(boot: (opts: { app: App }) => T | Promise<T>): T;
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  export function defineRouter(router: any): any;
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  export function defineStore(fn: (opts?: { ssrContext?: any }) => Pinia): Pinia;
}

// File System Access API types
interface FileSystemHandle {
  readonly kind: 'file' | 'directory';
  readonly name: string;
  queryPermission(options?: { mode: 'read' | 'readwrite' }): Promise<PermissionState>;
  requestPermission(options?: { mode: 'read' | 'readwrite' }): Promise<PermissionState>;
}

interface FileSystemFileHandle extends FileSystemHandle {
  readonly kind: 'file';
  getFile(): Promise<File>;
  createWritable(): Promise<FileSystemWritableFileStream>;
}

interface FileSystemDirectoryHandle extends FileSystemHandle {
  readonly kind: 'directory';
  entries(): AsyncIterableIterator<[string, FileSystemHandle]>;
  getFileHandle(name: string, options?: { create?: boolean }): Promise<FileSystemFileHandle>;
  getDirectoryHandle(name: string): Promise<FileSystemDirectoryHandle>;
}

interface FileSystemWritableFileStream extends WritableStream {
  write(data: string | BufferSource | Blob): Promise<void>;
  close(): Promise<void>;
}

declare global {
  interface Window {
    MonacoEnvironment?: {
      getWorkerUrl: (moduleId: string, label: string) => string;
    };
    showDirectoryPicker?(): Promise<FileSystemDirectoryHandle>;
    // Electron bridge for companion port
    xeditor?: {
      companionPort: number;
    };
  }
  const MonacoEnvironment: {
    getWorkerUrl: (moduleId: string, label: string) => string;
  } | undefined;
}
