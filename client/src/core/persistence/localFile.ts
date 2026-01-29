/**
 * Utilities for interacting with the local file system (via File System Access API)
 * specifically for storing application-specific data in a .xeditor/ directory
 * in the project root.
 */

export async function ensureDir(
  parent: FileSystemDirectoryHandle,
  name: string,
): Promise<FileSystemDirectoryHandle> {
  return await parent.getDirectoryHandle(name, { create: true });
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

export async function deleteFile(
  dir: FileSystemDirectoryHandle,
  filename: string,
): Promise<void> {
  try {
    await dir.removeEntry(filename);
  } catch (error) {
    if (error instanceof DOMException && error.name === 'NotFoundError') {
      return;
    }
    throw error;
  }
}

export async function deleteDirectory(
  parent: FileSystemDirectoryHandle,
  name: string,
): Promise<void> {
  try {
    await parent.removeEntry(name, { recursive: true });
  } catch (error) {
    if (error instanceof DOMException && error.name === 'NotFoundError') {
      return;
    }
    throw error;
  }
}

