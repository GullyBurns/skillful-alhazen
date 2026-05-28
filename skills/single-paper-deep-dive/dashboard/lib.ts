import { execFile } from 'child_process';
import { promisify } from 'util';
import path from 'path';

const execFileAsync = promisify(execFile);
const SKILL_ROOT = process.env.SINGLE_PAPER_DEEP_DIVE_ROOT;
const PROJECT_ROOT = process.env.PROJECT_ROOT || path.resolve(process.cwd());

const SCRIPT = SKILL_ROOT
  ? path.join(SKILL_ROOT, 'single_paper_deep_dive.py')
  : path.join(PROJECT_ROOT, '.claude/skills/single-paper-deep-dive/single_paper_deep_dive.py');

const CWD = SKILL_ROOT || PROJECT_ROOT;

async function runSkill(args: string[]): Promise<unknown> {
  const { stdout } = await execFileAsync('uv', ['run', 'python', SCRIPT, ...args], {
    cwd: CWD,
    maxBuffer: 10 * 1024 * 1024,
    env: { ...process.env, TYPEDB_DATABASE: 'alhazen_notebook' },
  });
  return JSON.parse(stdout);
}

export interface DiveEvidence {
  id: string;
  evidence_type: string;
  experimental_design?: string;
  data_summary?: string;
  source_doi?: string;
  source_title?: string;
  source_url?: string;
}

export interface DiveClaim {
  id: string;
  type: 'primary' | 'secondary' | 'peripheral';
  statement: string;
  evidence: DiveEvidence[];
}

export interface DiveCitationImpact {
  id: string;
  impact_type: string;
  impact_summary: string;
  citing_doi?: string;
  citing_title?: string;
}

export interface DiveAnalysis {
  id: string;
  doi?: string;
  title?: string;
  year?: number;
  paper_type?: string;
  status: string;
  source_count?: number;
  scope_note?: string;
  claims: DiveClaim[];
  citation_impacts: DiveCitationImpact[];
}

export interface DiveAnalysisSummary {
  id: string;
  doi?: string;
  title?: string;
  year?: number;
  status: string;
  source_count?: number;
}

export async function listAnalyses(): Promise<{ success: boolean; count: number; analyses: DiveAnalysisSummary[] }> {
  return runSkill(['list-analyses']) as Promise<{ success: boolean; count: number; analyses: DiveAnalysisSummary[] }>;
}

export async function getAnalysis(id: string): Promise<{ success: boolean; analysis: DiveAnalysis }> {
  return runSkill(['get-analysis', '--id', id]) as Promise<{ success: boolean; analysis: DiveAnalysis }>;
}
