import { execFile } from 'child_process';
import { promisify } from 'util';
import path from 'path';

const execFileAsync = promisify(execFile);

// JOBHUNT_SKILL_ROOT: absolute path to the jobhunt skill directory (used in standalone demo)
// PROJECT_ROOT: absolute path to skillful-alhazen root (used when installed)
// NOTEBOOK_SCRIPT_PATH: override for typedb_notebook.py location
const SKILL_ROOT = process.env.JOBHUNT_SKILL_ROOT;
const PROJECT_ROOT = process.env.PROJECT_ROOT || path.resolve(process.cwd());

const JOBHUNT_SCRIPT = SKILL_ROOT
  ? path.join(SKILL_ROOT, 'jobhunt.py')
  : path.join(PROJECT_ROOT, '.claude/skills/jobhunt/jobhunt.py');

const FORAGER_SCRIPT = SKILL_ROOT
  ? path.join(SKILL_ROOT, 'job_forager.py')
  : path.join(PROJECT_ROOT, '.claude/skills/jobhunt/job_forager.py');

const EMBEDDING_SCRIPT = SKILL_ROOT
  ? path.join(SKILL_ROOT, 'embedding_map.py')
  : path.join(PROJECT_ROOT, '.claude/skills/jobhunt/embedding_map.py');

const NOTEBOOK_SCRIPT = process.env.NOTEBOOK_SCRIPT_PATH
  || path.join(PROJECT_ROOT, '.claude/skills/typedb-notebook/typedb_notebook.py');

// Working directory for uv run: the skill dir (standalone) or project root (installed)
const CWD = SKILL_ROOT || PROJECT_ROOT;

async function runJobhunt(args: string[]): Promise<unknown> {
  const { stdout } = await execFileAsync(
    'uv',
    ['run', 'python', JOBHUNT_SCRIPT, ...args],
    { cwd: CWD, maxBuffer: 10 * 1024 * 1024 }
  );
  return JSON.parse(stdout);
}

async function runNotebook(args: string[]): Promise<unknown> {
  const { stdout } = await execFileAsync(
    'uv',
    ['run', 'python', NOTEBOOK_SCRIPT, ...args],
    {
      cwd: CWD,
      maxBuffer: 10 * 1024 * 1024,
      env: { ...process.env, TYPEDB_DATABASE: 'alhazen_notebook' },
    }
  );
  return JSON.parse(stdout);
}

async function runForager(args: string[]): Promise<unknown> {
  const { stdout } = await execFileAsync(
    'uv',
    ['run', 'python', FORAGER_SCRIPT, ...args],
    { cwd: CWD, maxBuffer: 10 * 1024 * 1024 }
  );
  return JSON.parse(stdout);
}

export async function listSources() {
  return runForager(['list-sources']);
}

export async function listSkills() {
  return runJobhunt(['list-skills']);
}

export async function searchSource(source: string) {
  return runForager(['search-source', '--source', source]);
}

export async function listCandidates(status?: string, limit?: number, offset?: number) {
  const args = ['list-candidates'];
  if (status) args.push('--status', status);
  if (limit !== undefined) args.push('--limit', String(limit));
  if (offset !== undefined) args.push('--offset', String(offset));
  return runForager(args);
}

export async function triageCandidate(id: string, action: 'dismissed') {
  return runForager(['triage', '--id', id, '--action', action]);
}

export async function promoteCandidate(id: string) {
  return runForager(['promote', '--id', id]);
}

export async function listPipeline(filters?: {
  status?: string;
  priority?: string;
  tag?: string;
}) {
  const args = ['list-pipeline'];
  if (filters?.status) args.push('--status', filters.status);
  if (filters?.priority) args.push('--priority', filters.priority);
  if (filters?.tag) args.push('--tag', filters.tag);
  return runJobhunt(args);
}

export async function getSkillGaps(priority?: string, all?: boolean) {
  const args = ['show-gaps'];
  if (all) args.push('--all');
  if (priority) args.push('--priority', priority);
  return runJobhunt(args);
}

export async function getLearningPlan() {
  return runJobhunt(['learning-plan']);
}

export async function updateStatus(
  positionId: string,
  status: string,
  date?: string
) {
  const args = ['update-status', '--position', positionId, '--status', status];
  if (date) args.push('--date', date);
  return runJobhunt(args);
}

export async function getPosition(id: string) {
  return runJobhunt(['show-position', '--id', id]);
}

export async function getCollection(id: string) {
  return runNotebook(['query-collection', '--id', id]);
}

export async function getNotes(subjectId: string) {
  return runNotebook(['query-notes', '--subject', subjectId]);
}

export async function listOpportunities(filters?: {
  type?: string;
  status?: string;
  priority?: string;
}) {
  const args = ['list-opportunities'];
  if (filters?.type) args.push('--type', filters.type);
  if (filters?.status) args.push('--status', filters.status);
  if (filters?.priority) args.push('--priority', filters.priority);
  return runJobhunt(args);
}

export async function getOpportunity(id: string) {
  return runJobhunt(['show-opportunity', '--id', id]);
}

export async function updateOpportunity(
  id: string,
  updates: { status?: string; stage?: string; priority?: string }
) {
  const args = ['update-opportunity', '--id', id];
  if (updates.status) args.push('--status', updates.status);
  if (updates.stage) args.push('--stage', updates.stage);
  if (updates.priority) args.push('--priority', updates.priority);
  return runJobhunt(args);
}

export async function getEmbeddingMap(excludeIds?: string[]) {
  const args = ['map'];
  if (excludeIds && excludeIds.length > 0) {
    args.push('--exclude', ...excludeIds);
  }
  // Use PROJECT_ROOT as cwd (not SKILL_ROOT) because embedding_map.py
  // needs pymde/qdrant/voyageai which are in the main project's deps
  const { stdout } = await execFileAsync(
    'uv',
    ['run', 'python', EMBEDDING_SCRIPT, ...args],
    { cwd: PROJECT_ROOT, maxBuffer: 10 * 1024 * 1024 }
  );
  return JSON.parse(stdout);
}
