'use client';

import { useState, useEffect } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { Badge } from '@/components/ui/badge';
import { ChevronRight, StickyNote } from 'lucide-react';
import type { TechReconNote } from '@/lib/tech-recon';

// Format badge colors
const FORMAT_COLORS: Record<string, string> = {
  md: 'bg-blue-500/20 text-blue-400 border-blue-500/30',
  markdown: 'bg-blue-500/20 text-blue-400 border-blue-500/30',
  yaml: 'bg-green-500/20 text-green-400 border-green-500/30',
  json: 'bg-yellow-500/20 text-yellow-400 border-yellow-500/30',
};

function getFormatColor(format: string | null | undefined): string {
  if (!format) return 'bg-slate-500/20 text-slate-300 border-slate-500/30';
  return FORMAT_COLORS[format.toLowerCase()] || 'bg-slate-500/20 text-slate-300 border-slate-500/30';
}

function extractFirstLine(content: string | undefined): string {
  if (!content) return '';
  const firstLine = content.split('\n').find((l) => l.trim().length > 0) || '';
  // Strip markdown heading markers
  return firstLine.replace(/^#+\s*/, '').trim();
}

function NoteContent({ note }: { note: TechReconNote }) {
  const format = (note.format || 'md').toLowerCase();
  const content = note.content || '';

  if (format === 'md' || format === 'markdown') {
    return (
      <div className="prose prose-sm dark:prose-invert max-w-none">
        <ReactMarkdown remarkPlugins={[remarkGfm]}>{content}</ReactMarkdown>
      </div>
    );
  }

  // YAML / JSON: syntax-highlighted code block
  const lang = format === 'yaml' ? 'yaml' : 'json';
  return (
    <pre className={`text-xs rounded-lg bg-muted/50 border border-border/40 p-3 overflow-x-auto language-${lang}`}>
      <code>{content}</code>
    </pre>
  );
}

function NoteItem({ note }: { note: TechReconNote }) {
  const [open, setOpen] = useState(false);
  const [fullContent, setFullContent] = useState<string | null>(note.content ?? null);

  useEffect(() => {
    if (!open || fullContent) return;
    fetch(`/api/tech-recon/note/${note.id}`)
      .then((r) => r.json())
      .then((d) => { if (d.note?.content) setFullContent(d.note.content); })
      .catch(() => {});
  }, [open, note.id, fullContent]);

  const displayNote = { ...note, content: fullContent ?? note.content_preview ?? '' };
  const firstLine = extractFirstLine(note.content_preview ?? note.content);
  const preview = firstLine || note.topic || 'Note';

  return (
    <div className="border border-border/50 rounded-lg overflow-hidden">
      <button
        onClick={() => setOpen(!open)}
        className="w-full flex items-center gap-2 px-3 py-2.5 text-left hover:bg-accent/30 transition-colors"
      >
        <ChevronRight
          className={`w-4 h-4 shrink-0 text-muted-foreground transition-transform duration-200 ${
            open ? 'rotate-90' : ''
          }`}
        />
        {note.topic && (
          <Badge variant="outline" className="text-xs shrink-0">
            {note.topic}
          </Badge>
        )}
        {note.format && (
          <Badge className={`${getFormatColor(note.format)} text-xs shrink-0`}>
            {note.format}
          </Badge>
        )}
        <span className="text-sm truncate text-muted-foreground">{preview}</span>
      </button>
      {open && (
        <div className="px-4 py-3 border-t border-border/50 bg-card/50">
          <NoteContent note={displayNote} />
        </div>
      )}
    </div>
  );
}

interface NotesListProps {
  notes: TechReconNote[];
  title?: string;
}

export function NotesList({ notes, title }: NotesListProps) {
  if (notes.length === 0) {
    return (
      <div className="flex flex-col items-center gap-2 py-8 text-center">
        <StickyNote className="w-8 h-8 text-muted-foreground/40" />
        <p className="text-sm text-muted-foreground">No notes yet.</p>
      </div>
    );
  }

  // Group by topic
  const groups = notes.reduce<Record<string, TechReconNote[]>>((acc, note) => {
    const key = note.topic || 'general';
    if (!acc[key]) acc[key] = [];
    acc[key].push(note);
    return acc;
  }, {});

  return (
    <div className="space-y-4">
      {title && (
        <h3 className="text-xs font-semibold uppercase tracking-widest text-muted-foreground">
          {title}
        </h3>
      )}
      {Object.entries(groups).map(([topic, topicNotes]) => (
        <div key={topic} className="space-y-1.5">
          <div className="flex items-center gap-2 px-1">
            <span className="text-xs font-medium text-muted-foreground capitalize">
              {topic.replace(/-/g, ' ')}
            </span>
            <Badge variant="secondary" className="text-xs">
              {topicNotes.length}
            </Badge>
          </div>
          <div className="space-y-1">
            {topicNotes.map((note) => (
              <NoteItem key={note.id} note={note} />
            ))}
          </div>
        </div>
      ))}
    </div>
  );
}
