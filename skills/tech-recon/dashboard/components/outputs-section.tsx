'use client';

import { useState } from 'react';
import { FileText, ClipboardCheck, StickyNote } from 'lucide-react';
import { ReportContent } from './report-content';
import { NotesList } from './notes-list';
import type { TechReconNote } from '@/lib/tech-recon';

const SPECIAL_TOPICS = new Set(['viz-plan', 'synthesis-report', 'completion-assessment']);

interface OutputsSectionProps {
  synthesisNote: TechReconNote | null;
  completionNote: TechReconNote | null;
  investigationId: string;
  notes?: TechReconNote[];
}

type OutputCard = 'synthesis' | 'completion' | null;

export function OutputsSection({ synthesisNote, completionNote, investigationId, notes = [] }: OutputsSectionProps) {
  const investigationNotes = notes.filter(n => !SPECIAL_TOPICS.has(n.topic ?? ''));
  const [activeCard, setActiveCard] = useState<OutputCard>(
    synthesisNote ? 'synthesis' : completionNote ? 'completion' : null
  );

  const toggle = (key: OutputCard) => setActiveCard(prev => prev === key ? null : key);

  return (
    <div className="space-y-4">
      {/* Output buttons */}
      <div className="flex flex-wrap gap-2">
        <button
          onClick={() => synthesisNote && toggle('synthesis')}
          className={[
            'px-3 py-1.5 rounded-md border text-sm transition-all flex items-center gap-2',
            synthesisNote ? '' : 'opacity-50 cursor-default',
            activeCard === 'synthesis'
              ? 'border-cyan-500/50 bg-cyan-500/10 text-cyan-300 font-semibold'
              : 'border-border/50 bg-card/40 text-foreground hover:border-border hover:bg-card/70',
          ].join(' ')}
        >
          <FileText className="w-3.5 h-3.5 shrink-0" />
          Synthesis Report
          {synthesisNote?.created_at && (
            <span className="text-xs text-muted-foreground/60 font-normal ml-1">
              · {new Date(synthesisNote.created_at).toLocaleDateString('en-US', { month: 'short', day: 'numeric' })}
            </span>
          )}
          {!synthesisNote && <span className="text-xs text-muted-foreground/50 font-normal">— missing</span>}
        </button>

        <button
          onClick={() => completionNote && toggle('completion')}
          className={[
            'px-3 py-1.5 rounded-md border text-sm transition-all flex items-center gap-2',
            completionNote ? '' : 'opacity-50 cursor-default',
            activeCard === 'completion'
              ? 'border-green-500/50 bg-green-500/10 text-green-300 font-semibold'
              : 'border-border/50 bg-card/40 text-foreground hover:border-border hover:bg-card/70',
          ].join(' ')}
        >
          <ClipboardCheck className="w-3.5 h-3.5 shrink-0" />
          Completion Assessment
          {completionNote?.created_at && (
            <span className="text-xs text-muted-foreground/60 font-normal ml-1">
              · {new Date(completionNote.created_at).toLocaleDateString('en-US', { month: 'short', day: 'numeric' })}
            </span>
          )}
          {!completionNote && <span className="text-xs text-muted-foreground/50 font-normal">— missing</span>}
        </button>
      </div>

      {/* Content panel */}
      {activeCard === 'synthesis' && synthesisNote && (
        <div className="rounded-lg border border-cyan-500/30 bg-card/30 p-5">
          <h3 className="text-sm font-semibold text-cyan-400 mb-4">Synthesis Report</h3>
          <ReportContent noteId={synthesisNote.id} preview={synthesisNote.content_preview} />
        </div>
      )}

      {activeCard === 'completion' && completionNote && (
        <div className="rounded-lg border border-green-500/30 bg-card/30 p-5">
          <h3 className="text-sm font-semibold text-green-400 mb-4">Completion Assessment</h3>
          <ReportContent noteId={completionNote.id} preview={completionNote.content_preview} />
        </div>
      )}

      {investigationNotes.length > 0 && (
        <div className="mt-2 pt-4 border-t border-border/40">
          <div className="flex items-center gap-2 mb-3">
            <StickyNote className="w-4 h-4 text-violet-400 shrink-0" />
            <span className="text-xs font-semibold uppercase tracking-wide text-violet-400">Investigation Notes</span>
          </div>
          <NotesList notes={investigationNotes} />
        </div>
      )}
    </div>
  );
}
