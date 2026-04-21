import { execFile } from 'child_process';
import { promisify } from 'util';
import path from 'path';

const execFileAsync = promisify(execFile);

const PROJECT_ROOT = process.env.PROJECT_ROOT || path.resolve(process.cwd());
const BSI_SCRIPT = path.join(PROJECT_ROOT, '.claude/skills/bioskills-index/bioskills_index.py');
const CWD = PROJECT_ROOT;

async function runBsi(args: string[]): Promise<unknown> {
  const { stdout } = await execFileAsync(
    'uv',
    ['run', 'python', BSI_SCRIPT, ...args],
    { cwd: CWD, maxBuffer: 20 * 1024 * 1024 }
  );
  return JSON.parse(stdout);
}

export async function listIndices() {
  return runBsi(['list-indices']);
}

export async function showIndex(indexId: string) {
  const data = await listIndices() as { success: boolean; indices: Array<{ id: string; [key: string]: unknown }> };
  const index = (data.indices ?? []).find((idx) => idx.id === indexId) ?? null;
  return { success: !!index, index };
}

export async function listSkills(indexId: string, opts: {
  op?: string; topic?: string; cluster?: number; limit?: number
} = {}) {
  const args = ['list-skills', '--index', indexId, '--limit', String(opts.limit ?? 300)];
  if (opts.op) args.push('--op', opts.op);
  if (opts.topic) args.push('--topic', opts.topic);
  if (opts.cluster !== undefined) args.push('--cluster', String(opts.cluster));
  return runBsi(args);
}

export async function showSkill(skillId: string) {
  return runBsi(['show-skill', '--id', skillId]);
}

export async function listOperations(opts: { parent?: string; source?: string; limit?: number } = {}) {
  const args = ['list-operations', '--limit', String(opts.limit ?? 100)];
  if (opts.parent) args.push('--parent', opts.parent);
  if (opts.source) args.push('--source', opts.source);
  return runBsi(args);
}

export async function showOperation(edamId: string) {
  return runBsi(['show-operation', '--edam-id', edamId]);
}

export async function search(indexId: string, query: string, topK = 10) {
  return runBsi(['search', '--index', indexId, '--query', query, '--top-k', String(topK)]);
}

export async function compose(indexId: string, task: string, maxSkills = 8, minClusters = 2) {
  return runBsi([
    'compose', '--index', indexId,
    '--task', task,
    '--max-skills', String(maxSkills),
    '--min-clusters', String(minClusters),
  ]);
}
