import { execFile } from 'child_process';
import { promisify } from 'util';
import path from 'path';

const execFileAsync = promisify(execFile);

const PROJECT_ROOT = process.env.PROJECT_ROOT || path.resolve(__dirname, '../../..');
const JOBHUNT_SCRIPT = path.join(PROJECT_ROOT, '.claude/skills/jobhunt/jobhunt.py');

async function runJobhunt(args: string[]): Promise<unknown> {
  const { stdout } = await execFileAsync(
    'uv',
    ['run', 'python', JOBHUNT_SCRIPT, ...args],
    { cwd: PROJECT_ROOT, maxBuffer: 10 * 1024 * 1024 }
  );
  return JSON.parse(stdout);
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

export async function getSkillGaps(priority?: string) {
  const args = ['show-gaps'];
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
