import { contextBridge } from 'electron';

/**
 * Expose protected methods that allow the renderer process to use
 * the port that Electron spawned the server on
 */
contextBridge.exposeInMainWorld('xeditor', {
  /**
   * Get the port that the companion server is running on
   * This is set by electron-main.ts when spawning the server
   */
  companionPort: parseInt(process.env.XEDITOR_PORT || '8000'),
});
