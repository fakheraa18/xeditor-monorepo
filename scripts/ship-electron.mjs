import { spawnSync } from 'node:child_process';
import path from 'node:path';
import process from 'node:process';
import { fileURLToPath } from 'node:url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const repoRoot = path.resolve(__dirname, '..');

/**
 * @param {string} cmd
 * @param {string[]} args
 * @param {{ cwd?: string; env?: NodeJS.ProcessEnv }} [opts]
 */
function run(cmd, args, opts = {}) {
  const res = spawnSync(cmd, args, {
    cwd: opts.cwd ?? repoRoot,
    env: opts.env ?? process.env,
    stdio: 'inherit',
    shell: process.platform === 'win32',
  });
  if (res.status !== 0) {
    throw new Error(`Command failed (${cmd} ${args.join(' ')}), exit=${res.status}`);
  }
}

/**
 * @returns {'linux'|'mac'|'win'}
 */
function detectQuasarTarget() {
  // electron-builder targets in Quasar CLI: linux | mac | win
  if (process.platform === 'darwin') return 'mac';
  if (process.platform === 'win32') return 'win';
  return 'linux';
}

/**
 * @returns {{ target: 'linux'|'mac'|'win'; skipServer: boolean }}
 */
function parseArgs() {
  const args = process.argv.slice(2);
  let target = /** @type {'linux'|'mac'|'win'|undefined} */ (undefined);
  let skipServer = false;

  for (const a of args) {
    if (a.startsWith('--platform=')) {
      const v = a.slice('--platform='.length);
      if (v === 'linux' || v === 'mac' || v === 'win') target = v;
    } else if (a === '--skip-server') {
      skipServer = true;
    }
  }

  return { target: target ?? detectQuasarTarget(), skipServer };
}

function buildServerForShip() {
  if (process.platform === 'win32') {
    run('node', ['scripts/build-server-win.mjs']);
    return;
  }
  run('bash', ['scripts/build-server-protected.sh']);
}

/**
 * @param {'linux'|'mac'|'win'} target
 */
function buildElectronInstallers(target) {
  // Use npm exec for cross-platform quasar invocation.
  run(
    'npm',
    ['-w', 'client', 'exec', '--', 'quasar', 'build', '-m', 'electron', '-T', target],
  );
}

function printOutput() {
  const outDir = path.join(repoRoot, 'client', 'dist', 'electron');
  console.log('\n[xeditor] Ship build complete.');
  console.log(`[xeditor] Electron artifacts are under: ${outDir}`);
}

function main() {
  const { target, skipServer } = parseArgs();
  console.log(`[xeditor] ship-electron: target=${target} skipServer=${skipServer}`);

  if (!skipServer) {
    buildServerForShip();
  } else {
    console.log('[xeditor] skipping server build (expects server/dist/xeditor-server.dist to already exist)');
  }
  buildElectronInstallers(target);
  printOutput();
}

main();

