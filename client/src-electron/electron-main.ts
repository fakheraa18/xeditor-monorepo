import { app, BrowserWindow } from 'electron';
import { spawn } from 'child_process';
import type { ChildProcess } from 'child_process';
import * as path from 'node:path';
import * as os from 'node:os';
import { fileURLToPath } from 'node:url';
import * as http from 'node:http';
import * as fs from 'node:fs';

// Disable sandbox on Linux for development (common issue with Electron on Linux)
if (process.platform === 'linux') {
  app.commandLine.appendSwitch('--no-sandbox');
  app.commandLine.appendSwitch('--disable-setuid-sandbox');
}

// needed in case process is undefined under Linux
const platform = process.platform || os.platform();

const currentDir = fileURLToPath(new URL('.', import.meta.url));

let mainWindow: BrowserWindow | null = null;
let serverProcess: ChildProcess | null = null;
const SERVER_PORT = parseInt(process.env.XEDITOR_PORT || '8081');
const SERVER_HOST = process.env.XEDITOR_HOST || '127.0.0.1';

/**
 * Check if the server is ready by making a request to the root endpoint
 */
async function checkServerReady(host: string, port: number, timeout: number = 5000): Promise<boolean> {
  return new Promise((resolve) => {
    const url = `http://${host}:${port}/`;
    const req = http.get(url, { timeout }, (res) => {
      let data = '';
      res.on('data', (chunk) => {
        data += chunk;
      });
      res.on('end', () => {
        try {
          const json = JSON.parse(data);
          resolve(json.status === 'ok');
        } catch {
          resolve(res.statusCode === 200);
        }
      });
    });

    req.on('error', () => {
      resolve(false);
    });

    req.on('timeout', () => {
      req.destroy();
      resolve(false);
    });
  });
}

/**
 * Poll the server until it's ready, with exponential backoff
 */
async function waitForServerReady(host: string, port: number, maxAttempts: number = 30): Promise<boolean> {
  for (let attempt = 0; attempt < maxAttempts; attempt++) {
    const ready = await checkServerReady(host, port, 2000);
    if (ready) {
      return true;
    }
    // Exponential backoff: 100ms, 200ms, 400ms, 800ms, then 1s max
    const delay = Math.min(100 * Math.pow(2, attempt), 1000);
    await new Promise((resolve) => setTimeout(resolve, delay));
  }
  return false;
}

/**
 * Spawn the backend server process
 */
function spawnServer(): ChildProcess | null {
  const isDev = !!process.env.DEV;
  let serverProcess: ChildProcess | null = null;

  if (isDev) {
    // Development: use uv run python
    // currentDir is client/.quasar/dev-electron/, so go up 3 levels to monorepo root, then to server
    const monorepoRoot = path.resolve(currentDir, '../../../');
    const serverDir = path.join(monorepoRoot, 'server');
    console.log(`[electron] Starting server in dev mode from ${serverDir}`);

    // Try to find uv in PATH or use environment variable
    const uvCommand = process.env.UV_PATH || 'uv';
    serverProcess = spawn(uvCommand, ['run', 'python', 'main.py', '--port', SERVER_PORT.toString(), '--host', SERVER_HOST], {
      cwd: serverDir,
      stdio: 'inherit',
      shell: platform === 'win32',
      env: { ...process.env },
    });
  } else {
    // Production: use bundled binary
    // electron-builder places extraResources in process.resourcesPath
    const resourcesPath = process.resourcesPath || path.join(path.dirname(process.execPath), 'resources');
    const serverDir = path.join(resourcesPath, 'xeditor-server');

    // Binary name varies by platform
    const binaryName = platform === 'win32' ? 'xeditor-server.exe' : 'xeditor-server';
    const serverBin = path.join(serverDir, binaryName);

    if (!fs.existsSync(serverBin)) {
      console.error('[electron] Server binary not found');
      console.error('[electron] Expected location:', serverBin);
      console.error('[electron] Resources path:', resourcesPath);
      console.error('[electron] Server dir exists:', fs.existsSync(serverDir));
      if (fs.existsSync(serverDir)) {
        console.error('[electron] Contents of server dir:', fs.readdirSync(serverDir));
      }
      return null;
    }

    console.log(`[electron] Starting server from ${serverBin}`);
    // Set working directory to server directory so relative paths work
    serverProcess = spawn(serverBin, ['--port', SERVER_PORT.toString(), '--host', SERVER_HOST], {
      cwd: serverDir,
      stdio: 'inherit',
      shell: platform === 'win32',
    });
  }

  if (serverProcess) {
    serverProcess.on('error', (err) => {
      console.error('[electron] Server process error:', err);
    });

    serverProcess.on('exit', (code, signal) => {
      console.log(`[electron] Server process exited with code ${code}, signal ${signal}`);
      if (code !== 0 && code !== null) {
        console.error('[electron] Server process exited unexpectedly');
      }
    });
  }

  return serverProcess;
}

/**
 * Create the main application window
 */
async function createWindow(): Promise<void> {
  /**
   * Initial window options
   */
  // Icon path - Quasar expects icons/icon.png in src-electron
  const iconPath = path.resolve(currentDir, 'icons/icon.png');
  const icon = fs.existsSync(iconPath) ? iconPath : undefined;

  mainWindow = new BrowserWindow({
    width: 1400,
    height: 900,
    minWidth: 800,
    minHeight: 600,
    useContentSize: true,
    show: false, // Don't show until server is ready
    ...(icon && { icon }), // Only set icon if it exists
    webPreferences: {
      contextIsolation: true,
      nodeIntegration: false,
      // More info: https://v2.quasar.dev/quasar-cli-vite/developing-electron-apps/electron-preload-script
      preload: path.resolve(
        currentDir,
        path.join(process.env.QUASAR_ELECTRON_PRELOAD_FOLDER || '.', 'electron-preload' + (process.env.QUASAR_ELECTRON_PRELOAD_EXTENSION || '.js'))
      ),
    },
  });

  // Show window when ready to prevent visual flash
  mainWindow.once('ready-to-show', () => {
    if (mainWindow) {
      mainWindow.show();
    }
  });

  if (process.env.DEV) {
    // Development: load from dev server
    const devUrl = process.env.APP_URL || 'http://localhost:9000';
    console.log(`[electron] Loading dev URL: ${devUrl}`);
    await mainWindow.loadURL(devUrl);
  } else {
    // Production: load from file system
    // In production, index.html is in the app's directory (or asar)
    const appPath = app.getAppPath();
    const indexPath = path.join(appPath, 'index.html');
    console.log(`[electron] Loading index.html from ${indexPath}`);
    await mainWindow.loadFile(indexPath);
  }

  // Only open DevTools if explicitly requested via environment variable
  // Quasar sets DEBUGGING in dev mode, but we don't want DevTools open by default
  // Users can still manually open DevTools via menu or keyboard shortcut
  if (process.env.OPEN_DEVTOOLS === 'true') {
    mainWindow.webContents.openDevTools();
  }
  // Note: We don't prevent manual opening - users can use View menu or Ctrl+Shift+I

  mainWindow.on('closed', () => {
    mainWindow = null;
  });
}

/**
 * Start the server and wait for it to be ready, then create the window
 */
async function startApp(): Promise<void> {
  console.log('[electron] Starting XEditor...');

  // Spawn the server process
  serverProcess = spawnServer();
  if (!serverProcess) {
    console.error('[electron] Failed to spawn server process');
    app.quit();
    return;
  }

  // Wait for server to be ready
  console.log(`[electron] Waiting for server to be ready at ${SERVER_HOST}:${SERVER_PORT}...`);
  const serverReady = await waitForServerReady(SERVER_HOST, SERVER_PORT);

  if (!serverReady) {
    console.error('[electron] Server failed to become ready within timeout');
    if (serverProcess) {
      serverProcess.kill();
    }
    app.quit();
    return;
  }

  console.log('[electron] Server is ready, creating window...');
  await createWindow();
}

// App lifecycle handlers
void app.whenReady().then(startApp);

app.on('window-all-closed', () => {
  // Kill server process when all windows are closed
  if (serverProcess) {
    console.log('[electron] Killing server process...');
    serverProcess.kill();
    serverProcess = null;
  }

  if (platform !== 'darwin') {
    app.quit();
  }
});

app.on('activate', () => {
  if (mainWindow === null) {
    void startApp();
  }
});

app.on('before-quit', () => {
  // Ensure server is killed on quit
  if (serverProcess) {
    console.log('[electron] Killing server process before quit...');
    serverProcess.kill();
    serverProcess = null;
  }
});
