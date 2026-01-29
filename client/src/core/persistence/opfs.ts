import type { ProjectId } from '../types';

async function getOpfsRoot(): Promise<FileSystemDirectoryHandle> {
  if (!('storage' in navigator) || typeof navigator.storage.getDirectory !== 'function') {
    throw new Error('OPFS (Origin Private File System) is not supported in this browser');
  }
  return await navigator.storage.getDirectory();
}

async function ensureDir(
  parent: FileSystemDirectoryHandle,
  name: string,
): Promise<FileSystemDirectoryHandle> {
  return await parent.getDirectoryHandle(name, { create: true });
}

export async function getProjectCacheDirectory(
  projectId: ProjectId,
): Promise<FileSystemDirectoryHandle> {
  const root = await getOpfsRoot();
  const projects = await ensureDir(root, 'projects');
  return await ensureDir(projects, projectId);
}

export async function deleteProjectCacheDirectory(projectId: ProjectId): Promise<void> {
  const maxRetries = 3;
  const retryDelayMs = 200;
  
  for (let attempt = 0; attempt < maxRetries; attempt++) {
    try {
      const root = await getOpfsRoot();
      const projects = await root.getDirectoryHandle('projects', { create: false });
      await projects.removeEntry(projectId, { recursive: true });
      return; // Success, exit retry loop
    } catch (error) {
      // Project cache might not exist, ignore NotFoundError
      if (error instanceof DOMException && error.name === 'NotFoundError') {
        return; // Already deleted or doesn't exist, success
      }
      
      // If it's a NoModificationAllowedError and we have retries left, wait and retry
      if (
        error instanceof DOMException &&
        error.name === 'NoModificationAllowedError' &&
        attempt < maxRetries - 1
      ) {
        // Wait a bit before retrying to allow handles to be released
        await new Promise((resolve) => setTimeout(resolve, retryDelayMs * (attempt + 1)));
        continue;
      }
      
      // For other errors or final attempt, throw
      throw error;
    }
  }
}

export async function writeJsonFile(
  dir: FileSystemDirectoryHandle,
  filename: string,
  data: unknown,
): Promise<void> {
  const fileHandle = await dir.getFileHandle(filename, { create: true });
  const writable = await fileHandle.createWritable();
  try {
    const text = JSON.stringify(data, null, 2);
    await writable.write(text);
  } finally {
    await writable.close();
  }
}

export async function readJsonFile<T>(
  dir: FileSystemDirectoryHandle,
  filename: string,
): Promise<T | null> {
  try {
    const fileHandle = await dir.getFileHandle(filename);
    const file = await fileHandle.getFile();
    const text = await file.text();
    return JSON.parse(text) as T;
  } catch (error) {
    if (error instanceof DOMException && error.name === 'NotFoundError') {
      return null;
    }
    throw error;
  }
}
