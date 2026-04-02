'use client';

import { useState } from 'react';
import { Badge } from '@/components/ui/badge';
import { ChevronRight, CheckCircle2 } from 'lucide-react';
import { NotesList } from './notes-list';
import type { TechReconNote } from '@/lib/tech-recon';
import type { TechReconSystem } from '@/lib/tech-recon';

// Topics that are internal artifacts and should never be shown to the user
const EXCLUDED_TOPICS = new Set([
  'fragment',
  'synthesis-report',
  'completion-assessment',
  'viz-plan',
]);

function filterNotes(notes: TechReconNote[]): TechReconNote[] {
  return notes.filter((n) => !EXCLUDED_TOPICS.has(n.topic));
}

function collectTopics(notesBySystem: Record<string, TechReconNote[]>): string[] {
  const seen = new Set<string>();
  for (const notes of Object.values(notesBySystem)) {
    for (const note of filterNotes(notes)) {
      if (note.topic) seen.add(note.topic);
    }
  }
  return Array.from(seen).sort();
}

interface SystemSectionProps {
  system: TechReconSystem;
  notes: TechReconNote[];
}

function SystemSection({ system, notes }: SystemSectionProps) {
  const [open, setOpen] = useState(true);
  const hasAssessment = notes.some((n) => n.topic === 'assessment');

  return (
    <div className="border border-border/50 rounded-lg overflow-hidden">
      <button
        onClick={() => setOpen(!open)}
        className="w-full flex items-center gap-2 px-4 py-3 text-left bg-muted/20 hover:bg-muted/40 transition-colors"
      >
        <ChevronRight
          className={`w-4 h-4 shrink-0 text-muted-foreground transition-transform duration-200 ${
            open ? 'rotate-90' : ''
          }`}
        />
        <span className="font-medium text-sm text-foreground flex-1">{system.name}</span>
        {hasAssessment && (
          <CheckCircle2 className="w-4 h-4 text-green-400 shrink-0" aria-label="Has assessment" />
        )}
        <Badge variant="secondary" className="text-xs shrink-0">
          {notes.length}
        </Badge>
      </button>

      {open && (
        <div className="px-4 py-3 border-t border-border/50">
          {notes.length === 0 ? (
            <p className="text-sm text-muted-foreground italic">(no matches)</p>
          ) : (
            <NotesList notes={notes} />
          )}
        </div>
      )}
    </div>
  );
}

interface ResearchSectionProps {
  systems: TechReconSystem[];
  notesBySystem: Record<string, TechReconNote[]>;
}

export function ResearchSection({ systems, notesBySystem }: ResearchSectionProps) {
  const [activeTopic, setActiveTopic] = useState<string | null>(null);

  // All notes excluding fragments/internal topics
  const allTopics = collectTopics(notesBySystem);

  // Total count (fragments excluded)
  const totalCount = systems.reduce((sum, sys) => {
    return sum + filterNotes(notesBySystem[sys.id] ?? []).length;
  }, 0);

  if (totalCount === 0) {
    return (
      <p className="text-sm text-muted-foreground italic py-6">No research notes yet.</p>
    );
  }

  // Per-system filtered notes
  function getFilteredNotes(systemId: string): TechReconNote[] {
    const base = filterNotes(notesBySystem[systemId] ?? []);
    if (!activeTopic) return base;
    return base.filter((n) => n.topic === activeTopic);
  }

  return (
    <div className="space-y-4">
      {/* Header count */}
      <p className="text-sm text-muted-foreground">
        <span className="font-semibold text-foreground">{totalCount}</span> notes across{' '}
        <span className="font-semibold text-foreground">{systems.length}</span> systems
      </p>

      {/* Topic filter bar */}
      {allTopics.length > 0 && (
        <div className="flex flex-wrap gap-2">
          <button
            onClick={() => setActiveTopic(null)}
            className={`px-3 py-1 rounded-full text-xs font-medium border transition-colors ${
              activeTopic === null
                ? 'bg-cyan-500/20 text-cyan-400 border-cyan-500/40'
                : 'bg-muted/30 text-muted-foreground border-border/50 hover:bg-muted/50'
            }`}
          >
            All
          </button>
          {allTopics.map((topic) => (
            <button
              key={topic}
              onClick={() => setActiveTopic(activeTopic === topic ? null : topic)}
              className={`px-3 py-1 rounded-full text-xs font-medium border transition-colors ${
                activeTopic === topic
                  ? 'bg-cyan-500/20 text-cyan-400 border-cyan-500/40'
                  : 'bg-muted/30 text-muted-foreground border-border/50 hover:bg-muted/50'
              }`}
            >
              {topic.replace(/-/g, ' ')}
            </button>
          ))}
        </div>
      )}

      {/* Per-system sections */}
      <div className="space-y-3">
        {systems.map((system) => (
          <SystemSection
            key={system.id}
            system={system}
            notes={getFilteredNotes(system.id)}
          />
        ))}
      </div>
    </div>
  );
}
