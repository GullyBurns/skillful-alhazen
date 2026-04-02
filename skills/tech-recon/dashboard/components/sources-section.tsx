'use client';

import { useState } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { Badge } from '@/components/ui/badge';
import { ChevronRight, StickyNote, ExternalLink, Globe, FileText, Package, FileJson, FolderGit2 } from 'lucide-react';
import type { TechReconSystem, TechReconArtifact, TechReconNote, SystemData } from '@/lib/tech-recon';

const ARTIFACT_ICONS: Record<string, React.ReactNode> = {
  webpage: <Globe className="w-3.5 h-3.5 shrink-0" />,
  'source-file': <FileText className="w-3.5 h-3.5 shrink-0" />,
  'repo-clone': <Package className="w-3.5 h-3.5 shrink-0" />,
  'file-tree': <FileJson className="w-3.5 h-3.5 shrink-0" />,
  directory: <FolderGit2 className="w-3.5 h-3.5 shrink-0" />,
};

const FORMAT_COLORS: Record<string, string> = {
  html: 'bg-orange-500/20 text-orange-400 border-orange-500/30',
  json: 'bg-yellow-500/20 text-yellow-400 border-yellow-500/30',
  text: 'bg-slate-500/20 text-slate-300 border-slate-500/30',
  pdf: 'bg-red-500/20 text-red-400 border-red-500/30',
  directory: 'bg-blue-500/20 text-blue-300 border-blue-500/30',
};

const NOTE_FORMAT_COLORS: Record<string, string> = {
  md: 'bg-blue-500/20 text-blue-400 border-blue-500/30',
  markdown: 'bg-blue-500/20 text-blue-400 border-blue-500/30',
  yaml: 'bg-green-500/20 text-green-400 border-green-500/30',
  json: 'bg-yellow-500/20 text-yellow-400 border-yellow-500/30',
};

function NoteViewer({ note }: { note: TechReconNote }) {
  const [fullContent, setFullContent] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [fetched, setFetched] = useState(false);

  const load = () => {
    if (fetched) return;
    setFetched(true);
    setLoading(true);
    fetch(`/api/tech-recon/note/${note.id}`)
      .then(r => r.json())
      .then(d => { if (d.note?.content) setFullContent(d.note.content); })
      .catch(() => setFullContent(note.content_preview ?? null))
      .finally(() => setLoading(false));
  };

  const [open, setOpen] = useState(false);
  const preview = note.content_preview ?? note.content ?? '';
  const firstLine = preview.split('\n').find(l => l.trim().length > 0)?.replace(/^#+\s*/, '').trim() ?? note.topic;
  const fmt = (note.format || 'md').toLowerCase();
  const fmtColor = NOTE_FORMAT_COLORS[fmt] ?? 'bg-slate-500/20 text-slate-300 border-slate-500/30';

  const toggle = () => {
    if (!open) load();
    setOpen(!open);
  };

  const content = fullContent ?? preview;

  return (
    <div className="border-b last:border-b-0 border-border/40">
      <button onClick={toggle} className="w-full flex items-center gap-2 px-3 py-2 text-left hover:bg-accent/20 transition-colors">
        <ChevronRight className={`w-3.5 h-3.5 shrink-0 text-muted-foreground/70 transition-transform duration-200 ${open ? 'rotate-90' : ''}`} />
        <StickyNote className="w-3.5 h-3.5 shrink-0 text-cyan-400/70" />
        {note.topic && <Badge variant="outline" className="text-xs shrink-0">{note.topic}</Badge>}
        <Badge className={`${fmtColor} text-xs shrink-0`}>{note.format}</Badge>
        <span className="text-xs truncate text-muted-foreground flex-1">{firstLine}</span>
      </button>
      {open && (
        <div className="px-4 py-3 border-t border-border/40 bg-card/50">
          {loading ? (
            <p className="text-xs text-muted-foreground">Loading...</p>
          ) : fmt === 'md' || fmt === 'markdown' ? (
            <div className="prose prose-sm dark:prose-invert max-w-none">
              <ReactMarkdown remarkPlugins={[remarkGfm]}>{content}</ReactMarkdown>
            </div>
          ) : (
            <pre className="text-xs rounded-lg bg-muted/50 border border-border/40 p-3 overflow-x-auto"><code>{content}</code></pre>
          )}
        </div>
      )}
    </div>
  );
}

function SystemDetail({ system, data }: { system: TechReconSystem; data: SystemData }) {
  return (
    <div className="space-y-4 pt-2">
      {/* Artifacts */}
      {data.artifacts.length > 0 && (
        <div className="space-y-1">
          <p className="text-xs font-semibold uppercase tracking-wide text-muted-foreground px-1">
            Artifacts ({data.artifacts.length})
          </p>
          <div className="rounded-lg border border-border/50 divide-y divide-border/40">
            {data.artifacts.map(art => (
              <div key={art.id} className="flex items-center gap-2 px-3 py-2">
                <span className="text-muted-foreground shrink-0">
                  {ARTIFACT_ICONS[art.type] ?? <FileText className="w-3.5 h-3.5 shrink-0" />}
                </span>
                <span className="flex-1 text-xs truncate text-foreground">{art.url || art.id}</span>
                <Badge className={`${FORMAT_COLORS[art.format?.toLowerCase()] ?? 'bg-slate-500/20 text-slate-300 border-slate-500/30'} text-xs shrink-0`}>
                  {art.format}
                </Badge>
                {art.cache_path && (
                  <Badge className="bg-green-500/20 text-green-400 border-green-500/30 text-xs shrink-0">cached</Badge>
                )}
                {art.url && (
                  <a href={art.url} target="_blank" rel="noopener noreferrer"
                    className="text-cyan-400 hover:text-blue-400 transition-colors shrink-0">
                    <ExternalLink className="w-3.5 h-3.5" />
                  </a>
                )}
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Notes */}
      {data.notes.length > 0 && (
        <div className="space-y-1">
          <p className="text-xs font-semibold uppercase tracking-wide text-muted-foreground px-1">
            Sensemaking Notes ({data.notes.length})
          </p>
          <div className="rounded-lg border border-border/50 overflow-hidden">
            {data.notes.map(note => <NoteViewer key={note.id} note={note} />)}
          </div>
        </div>
      )}

      {data.artifacts.length === 0 && data.notes.length === 0 && (
        <p className="text-sm text-muted-foreground italic">No artifacts or notes ingested yet.</p>
      )}
    </div>
  );
}

interface SensemakingSectionProps {
  systems: TechReconSystem[];
  systemDataMap: Record<string, SystemData>;
}

export function SensemakingSection({ systems, systemDataMap }: SensemakingSectionProps) {
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const selected = systems.find(s => s.id === selectedId);
  const selectedData = selectedId ? (systemDataMap[selectedId] ?? { artifacts: [], notes: [] }) : null;

  return (
    <div className="space-y-4">
      <h2 className="text-sm font-semibold text-muted-foreground uppercase tracking-wide">
        Ingestion &amp; Sensemaking &mdash; {systems.length} systems
      </h2>

      {/* System buttons */}
      <div className="flex flex-wrap gap-2">
        {systems.map(s => {
          const isActive = s.id === selectedId;
          const artCount = s.artifacts_count ?? 0;
          const noteCount = s.notes_count ?? 0;
          return (
            <button
              key={s.id}
              onClick={() => setSelectedId(isActive ? null : s.id)}
              className={[
                'px-3 py-1.5 rounded-md border text-sm transition-all',
                isActive
                  ? 'border-cyan-500/50 bg-cyan-500/10 text-cyan-300 font-semibold'
                  : 'border-border/50 bg-card/40 text-foreground hover:border-border hover:bg-card/70',
              ].join(' ')}
            >
              {s.name} <span className="text-xs text-muted-foreground font-normal ml-1">— {artCount}a/{noteCount}n</span>
            </button>
          );
        })}
      </div>

      {/* Detail panel for selected system */}
      {selected && selectedData && (
        <div className="rounded-lg border border-cyan-500/30 bg-card/30 p-4">
          <div className="flex items-center justify-between mb-3">
            <h3 className="text-sm font-semibold text-foreground">{selected.name}</h3>
            <button onClick={() => setSelectedId(null)} className="text-xs text-muted-foreground hover:text-foreground">x close</button>
          </div>
          <SystemDetail system={selected} data={selectedData} />
        </div>
      )}
    </div>
  );
}
