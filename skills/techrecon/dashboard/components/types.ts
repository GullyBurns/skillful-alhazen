// Shared types used across TechRecon dashboard components and view models

export type Stage = 'discovery' | 'analysis' | 'synthesis' | 'done';

export interface StageCounts {
  discovery: { systems: number; artifacts: number };
  analysis: { components: number; concepts: number };
  synthesis: { archNotes: number; assessNotes: number };
  done: { complete: boolean };
}

export interface Paper {
  id: string;
  citation: string;
  doi?: string;
}
