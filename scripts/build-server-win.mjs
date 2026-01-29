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
 * @param {{ cwd?: string }} [opts]
 */
function run(cmd, args, opts = {}) {
  const res = spawnSync(cmd, args, {
    cwd: opts.cwd ?? repoRoot,
    env: process.env,
    stdio: 'inherit',
    shell: true, // windows-friendly
  });
  if (res.status !== 0) {
    throw new Error(`Command failed (${cmd} ${args.join(' ')}), exit=${res.status}`);
  }
}

function main() {
  const serverDir = path.join(repoRoot, 'server');
  console.log('[xeditor] building protected server (nuitka) on Windows...');

  // Ensure build deps installed
  run('uv', ['sync', '--extra', 'build'], { cwd: serverDir });

  // Build (outputs to server/dist/)
  run('uv', ['run', 'python', 'build.py', '--clean', '--name', 'xeditor-server'], { cwd: serverDir });

  console.log('[xeditor] server build complete.');
}

main();

