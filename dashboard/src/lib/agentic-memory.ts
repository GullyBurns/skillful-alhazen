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

// ---------------------------------------------------------------------------
// Schema, Query, and Search interfaces
// ---------------------------------------------------------------------------

export interface EntityTypeInfo {
  parent?: string;
  owns?: string[];
  plays?: string[];
  subtypes?: string[];
  instance_count?: number;
}

export interface RelationTypeInfo {
  roles?: string[];
  owns?: string[];
}

export interface EmbeddingInfo {
  entity_type: string;
  indexed_fields: string[];
  id_field: string;
  skill: string;
  point_count?: number | null;
}

export interface SchemaResult {
  source: 'live' | 'files';
  entities: Record<string, EntityTypeInfo>;
  relations: Record<string, RelationTypeInfo>;
  embedding_index: Record<string, EmbeddingInfo>;
}

export interface QueryResult {
  success: boolean;
  count: number;
  results: unknown[];
}

export interface SearchResultItem {
  collection: string;
  entity_type: string;
  skill: string;
  score: number;
  payload: Record<string, unknown>;
}

export interface SearchResult {
  success: boolean;
  count: number;
  results: SearchResultItem[];
}

// ---------------------------------------------------------------------------
// Schema, Query, and Search functions
// ---------------------------------------------------------------------------

export async function describeSchema(skill?: string, full?: boolean): Promise<SchemaResult> {
  const args = ['describe-schema'];
  if (skill) args.push('--skill', skill);
  if (full) args.push('--full');
  return await runAgenticMemory(args) as SchemaResult;
}

export async function queryTypeQL(typeql: string, limit?: number): Promise<QueryResult> {
  const args = ['query', '--typeql', typeql];
  if (limit !== undefined) args.push('--limit', String(limit));
  return await runAgenticMemory(args) as QueryResult;
}

export async function searchSemantic(
  query: string,
  collection?: string,
  limit?: number,
  threshold?: number
): Promise<SearchResult> {
  const args = ['search', '--query', query];
  if (collection) args.push('--collection', collection);
  if (limit !== undefined) args.push('--limit', String(limit));
  if (threshold !== undefined) args.push('--threshold', String(threshold));
  return await runAgenticMemory(args) as SearchResult;
}
