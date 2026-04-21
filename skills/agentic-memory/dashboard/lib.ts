import { execFile } from 'child_process';
import { promisify } from 'util';
import path from 'path';

const execFileAsync = promisify(execFile);

const PROJECT_ROOT = process.env.PROJECT_ROOT || path.resolve(process.cwd());

const AGENTIC_MEMORY_SCRIPT = path.join(
  PROJECT_ROOT,
  '.claude/skills/agentic-memory/agentic_memory.py'
);

async function runAgenticMemory(args: string[]): Promise<unknown> {
  const { stdout } = await execFileAsync(
    'uv',
    ['run', 'python', AGENTIC_MEMORY_SCRIPT, ...args],
    {
      cwd: PROJECT_ROOT,
      maxBuffer: 5 * 1024 * 1024,
      env: { ...process.env, TYPEDB_DATABASE: 'alhazen_notebook' },
    }
  );
  return JSON.parse(stdout);
}

// ---------------------------------------------------------------------------
// Typed interfaces
// ---------------------------------------------------------------------------

export interface Person {
  id: string;
  name?: string;
  'given-name'?: string;
  'family-name'?: string;
  'identity-summary'?: string;
  'role-description'?: string;
  'communication-style'?: string;
  'goals-summary'?: string;
  'preferences-summary'?: string;
  'domain-expertise'?: string;
}

export interface PersonContext {
  success: boolean;
  context: Person;
  projects: Array<{ id: string; name: string }>;
  tools: Array<{ id: string; name: string }>;
}

export interface MemoryClaimNote {
  id: string;
  content: string;
  'fact-type'?: string;
  confidence?: number;
  'created-at'?: string;
  'valid-until'?: string;
}

export interface Episode {
  id: string;
  content: string;
  'source-skill'?: string;
  'session-id'?: string;
  'created-at'?: string;
}

// ---------------------------------------------------------------------------
// API functions
// ---------------------------------------------------------------------------

export async function listPersons(): Promise<Person[]> {
  const result = await runAgenticMemory(['list-persons']) as { success: boolean; persons: Person[] };
  return result.persons || [];
}

export async function getContext(personId: string): Promise<PersonContext> {
  return await runAgenticMemory(['get-context', '--person', personId]) as PersonContext;
}

export async function recallPerson(personId: string): Promise<MemoryClaimNote[]> {
  const result = await runAgenticMemory(['recall-person', '--person', personId]) as {
    success: boolean;
    claims: MemoryClaimNote[];
  };
  return result.claims || [];
}

export async function listClaims(factType?: string, limit = 50): Promise<MemoryClaimNote[]> {
  const args = ['list-claims', '--limit', String(limit)];
  if (factType) args.push('--fact-type', factType);
  const result = await runAgenticMemory(args) as { success: boolean; claims: MemoryClaimNote[] };
  return result.claims || [];
}

export async function listEpisodes(skill?: string, limit = 20): Promise<Episode[]> {
  const args = ['list-episodes', '--limit', String(limit)];
  if (skill) args.push('--skill', skill);
  const result = await runAgenticMemory(args) as { success: boolean; episodes: Episode[] };
  return result.episodes || [];
}

export async function showEpisode(episodeId: string): Promise<{
  episode: Episode;
  entities: Array<{ id: string; name: string }>;
}> {
  const result = await runAgenticMemory(['show-episode', episodeId]) as {
    success: boolean;
    episode: Episode;
    entities: Array<{ id: string; name: string }>;
  };
  return { episode: result.episode, entities: result.entities || [] };
}
