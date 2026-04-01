import { execFile } from 'child_process';
import { promisify } from 'util';
import path from 'path';

const execFileAsync = promisify(execFile);

// TECH_RECON_SKILL_ROOT: absolute path to the tech-recon skill directory (used in standalone demo)
// PROJECT_ROOT: absolute path to skillful-alhazen root (used when installed)
const SKILL_ROOT = process.env.TECH_RECON_SKILL_ROOT;
const PROJECT_ROOT = process.env.PROJECT_ROOT || path.resolve(process.cwd());

const TECH_RECON_SCRIPT = SKILL_ROOT
  ? path.join(SKILL_ROOT, 'tech_recon.py')
  : path.join(PROJECT_ROOT, '.claude/skills/tech-recon/tech_recon.py');

const CWD = SKILL_ROOT || PROJECT_ROOT;

async function runTechRecon(args: string[]): Promise<unknown> {
  const { stdout } = await execFileAsync(
    'uv',
    ['run', 'python', TECH_RECON_SCRIPT, ...args],
    {
      cwd: CWD,
      maxBuffer: 10 * 1024 * 1024,
      env: { ...process.env, TYPEDB_DATABASE: 'alhazen_notebook' },
    }
  );
  return JSON.parse(stdout);
}

// Typed interfaces for all API responses

export interface Investigation {
  id: string;
  name: string;
  status: string;
  goal: string;
  criteria: string;
}

export interface TechReconSystem {
  id: string;
  name: string;
  url: string;
  status: string;
  github_url?: string;
  language?: string;
  license?: string;
  star_count?: number;
  artifacts_count?: number;
  notes_count?: number;
}

export interface TechReconArtifact {
  id: string;
  type: string;
  url: string;
  format: string;
  cache_path?: string;
}

export interface TechReconNote {
  id: string;
  topic: string;
  format: string;
  tags: string[];
  content?: string;
  content_preview?: string;
}

export interface TechReconAnalysis {
  id: string;
  title: string;
  type: string;
  plot_code?: string;
  query?: string;
  description?: string;
}

// Exported API functions

export async function listInvestigations(status?: string): Promise<{ investigations: Investigation[] }> {
  const args = ['list-investigations'];
  if (status) args.push('--status', status);
  return runTechRecon(args) as any;
}

export async function getInvestigation(id: string): Promise<{ investigation: Investigation }> {
  return runTechRecon(['show-investigation', '--id', id]) as any;
}

export async function listSystems(investigationId: string, status = 'all'): Promise<{ systems: TechReconSystem[] }> {
  const args = ['list-systems', '--investigation', investigationId];
  if (status && status !== 'all') args.push('--status', status);
  return runTechRecon(args) as any;
}

export async function getSystem(id: string): Promise<{ system: TechReconSystem }> {
  return runTechRecon(['show-system', '--id', id]) as any;
}

export async function listArtifacts(systemId: string, type?: string): Promise<{ artifacts: TechReconArtifact[] }> {
  const args = ['list-artifacts', '--system', systemId];
  if (type) args.push('--type', type);
  return runTechRecon(args) as any;
}

export async function getArtifact(id: string): Promise<{ artifact: TechReconArtifact & { content_preview?: string } }> {
  return runTechRecon(['show-artifact', '--id', id]) as any;
}

export async function listNotes(subjectId: string, topic?: string, format?: string): Promise<{ notes: TechReconNote[] }> {
  const args = ['list-notes', '--subject-id', subjectId];
  if (topic) args.push('--topic', topic);
  if (format) args.push('--format', format);
  return runTechRecon(args) as any;
}

export async function getNote(id: string): Promise<{ note: TechReconNote }> {
  return runTechRecon(['show-note', '--id', id]) as any;
}

export async function listAnalyses(investigationId: string): Promise<{ analyses: TechReconAnalysis[] }> {
  return runTechRecon(['list-analyses', '--investigation', investigationId]) as any;
}

export async function getAnalysis(id: string): Promise<{ analysis: TechReconAnalysis }> {
  return runTechRecon(['show-analysis', '--id', id]) as any;
}

export async function runAnalysis(id: string): Promise<{ plot_code: string; data: unknown[] }> {
  return runTechRecon(['run-analysis', '--id', id]) as any;
}

export async function planAnalyses(investigationId: string): Promise<unknown> {
  return runTechRecon(['plan-analyses', '--investigation', investigationId]) as any;
}
