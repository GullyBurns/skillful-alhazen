import { execFile } from 'child_process';
import { promisify } from 'util';
import path from 'path';

const execFileAsync = promisify(execFile);

const PROJECT_ROOT = process.env.PROJECT_ROOT || path.resolve(__dirname, '../../..');
const TECHRECON_SCRIPT = path.join(PROJECT_ROOT, '.claude/skills/techrecon/techrecon.py');

async function runTechrecon(args: string[]): Promise<unknown> {
  const { stdout } = await execFileAsync(
    'uv',
    ['run', 'python', TECHRECON_SCRIPT, ...args],
    {
      cwd: PROJECT_ROOT,
      maxBuffer: 10 * 1024 * 1024,
      env: { ...process.env, TYPEDB_DATABASE: 'alhazen_notebook' },
    }
  );
  return JSON.parse(stdout);
}

export async function listInvestigations(status?: string) {
  const args = ['list-investigations'];
  if (status) args.push('--status', status);
  return runTechrecon(args);
}

export async function listSystems() {
  return runTechrecon(['list-systems']);
}

export async function getSystem(id: string) {
  return runTechrecon(['show-system', '--id', id]);
}

export async function getArchitecture(id: string) {
  return runTechrecon(['show-architecture', '--id', id]);
}

export async function listArtifacts(system?: string, type?: string) {
  const args = ['list-artifacts'];
  if (system) args.push('--system', system);
  if (type) args.push('--type', type);
  return runTechrecon(args);
}

export async function getArtifact(id: string) {
  return runTechrecon(['show-artifact', '--id', id]);
}

export async function getComponent(id: string) {
  return runTechrecon(['show-component', '--id', id]);
}

export async function getConcept(id: string) {
  return runTechrecon(['show-concept', '--id', id]);
}

export async function getDataModel(id: string) {
  return runTechrecon(['show-data-model', '--id', id]);
}

export async function searchTag(tag: string) {
  return runTechrecon(['search-tag', '--tag', tag]);
}
