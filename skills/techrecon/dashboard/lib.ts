import { execFile } from 'child_process';
import { promisify } from 'util';
import path from 'path';

const execFileAsync = promisify(execFile);

// TECHRECON_SKILL_ROOT: absolute path to the techrecon skill directory (used in standalone demo)
// PROJECT_ROOT: absolute path to skillful-alhazen root (used when installed)
const SKILL_ROOT = process.env.TECHRECON_SKILL_ROOT;
const PROJECT_ROOT = process.env.PROJECT_ROOT || path.resolve(process.cwd());

const TECHRECON_SCRIPT = SKILL_ROOT
  ? path.join(SKILL_ROOT, 'techrecon.py')
  : path.join(PROJECT_ROOT, '.claude/skills/techrecon/techrecon.py');

const CWD = SKILL_ROOT || PROJECT_ROOT;

async function runTechrecon(args: string[]): Promise<unknown> {
  const { stdout } = await execFileAsync(
    'uv',
    ['run', 'python', TECHRECON_SCRIPT, ...args],
    {
      cwd: CWD,
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

export async function getInvestigation(id: string) {
  return runTechrecon(['show-investigation', '--id', id]);
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

export async function getBenchmarks(systemId: string) {
  return runTechrecon(['show-benchmarks', '--system', systemId]);
}

export async function getSystemDecisions(systemId: string) {
  return runTechrecon(['show-decisions', '--system', systemId]);
}

export async function listComparisons(investigationId?: string) {
  const args = ['list-comparisons'];
  if (investigationId) args.push('--investigation', investigationId);
  return runTechrecon(args);
}

export async function listWorkflows(systemId?: string) {
  const args = ['list-workflows'];
  if (systemId) args.push('--system', systemId);
  return runTechrecon(args);
}

export async function getWorkflow(id: string) {
  return runTechrecon(['show-workflow', '--id', id]);
}

export async function listPapers(systemId: string) {
  return runTechrecon(['list-papers', '--system', systemId]);
}
