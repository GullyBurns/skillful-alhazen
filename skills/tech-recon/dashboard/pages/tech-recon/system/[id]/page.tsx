'use client';

import { useState, useEffect, use } from 'react';
import Link from 'next/link';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { ArtifactList } from '@/components/tech-recon/artifact-list';
import { NotesList } from '@/components/tech-recon/notes-list';
import {
  ArrowLeft,
  RefreshCw,
  ExternalLink,
  Star,
  Scale,
  Code2,
  ChevronDown,
  ChevronRight,
} from 'lucide-react';
import type { TechReconSystem, TechReconArtifact, TechReconNote } from '@/lib/tech-recon';

const linkClass =
  'text-cyan-400 font-semibold underline underline-offset-2 hover:text-blue-400 transition-colors';

const STATUS_COLORS: Record<string, string> = {
  candidate: 'bg-slate-500/20 text-slate-300 border-slate-500/30',
  confirmed: 'bg-blue-500/20 text-blue-400 border-blue-500/30',
  ingested: 'bg-yellow-500/20 text-yellow-400 border-yellow-500/30',
  analyzed: 'bg-green-500/20 text-green-400 border-green-500/30',
  excluded: 'bg-red-500/20 text-red-400 border-red-500/30',
};

function getStatusColor(status: string | null | undefined): string {
  if (!status) return 'bg-slate-500/20 text-slate-300 border-slate-500/30';
  return STATUS_COLORS[status.toLowerCase()] || 'bg-slate-500/20 text-slate-300 border-slate-500/30';
}

function CollapsibleSection({
  title,
  count,
  children,
  defaultOpen = false,
}: {
  title: string;
  count: number;
  children: React.ReactNode;
  defaultOpen?: boolean;
}) {
  const [open, setOpen] = useState(defaultOpen);
  return (
    <div className="border border-border/50 rounded-lg overflow-hidden">
      <button
        onClick={() => setOpen(!open)}
        className="w-full flex items-center gap-2 px-4 py-3 text-left bg-muted/20 hover:bg-muted/40 transition-colors"
      >
        {open ? (
          <ChevronDown className="w-4 h-4 shrink-0 text-muted-foreground" />
        ) : (
          <ChevronRight className="w-4 h-4 shrink-0 text-muted-foreground" />
        )}
        <span className="text-sm font-medium">{title}</span>
        <Badge variant="secondary" className="ml-auto text-xs">
          {count}
        </Badge>
      </button>
      {open && <div className="p-4 border-t border-border/50">{children}</div>}
    </div>
  );
}

interface PageData {
  system: TechReconSystem;
  artifacts: TechReconArtifact[];
  notes: TechReconNote[];
  investigation?: { id: string; name: string };
}

interface SystemPageProps {
  params: Promise<{ id: string }>;
}

export default function SystemPage({ params }: SystemPageProps) {
  const { id } = use(params);
  const [data, setData] = useState<PageData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchData = async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await fetch(`/api/tech-recon/system/${id}`);
      if (!res.ok) throw new Error(`API error: ${res.status}`);
      const json = await res.json();
      setData(json);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { fetchData(); }, [id]);

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <RefreshCw className="w-8 h-8 animate-spin text-muted-foreground" />
      </div>
    );
  }

  if (error || !data) {
    return (
      <div className="min-h-screen p-8">
        <Link href="/tech-recon" className={`flex items-center gap-2 text-sm mb-4 ${linkClass}`}>
          <ArrowLeft className="w-4 h-4" />
          Back to Tech Recon
        </Link>
        <div className="bg-destructive/10 text-destructive px-4 py-3 rounded-lg">
          <strong>Error:</strong> {error || 'System not found'}
        </div>
      </div>
    );
  }

  const { system, artifacts, notes, investigation } = data;

  return (
    <div className="min-h-screen">
      {/* Header */}
      <header className="border-b border-border/50 bg-card/50 backdrop-blur-sm">
        <div className="container mx-auto px-4 py-4">
          {/* Back link */}
          <div className="flex items-center gap-3 mb-3 text-sm">
            <Link href="/tech-recon" className={`flex items-center gap-1 ${linkClass}`}>
              <ArrowLeft className="w-4 h-4" />
              Tech Recon
            </Link>
            {investigation && (
              <>
                <span className="text-muted-foreground">/</span>
                <Link
                  href={`/tech-recon/investigation/${investigation.id}`}
                  className={linkClass}
                >
                  {investigation.name}
                </Link>
              </>
            )}
          </div>

          <div className="flex items-start justify-between gap-4">
            <div className="flex-1">
              <div className="flex items-center gap-3">
                <h1 className="text-2xl font-bold bg-gradient-to-r from-cyan-400 to-blue-400 bg-clip-text text-transparent">
                  {system.name}
                </h1>
                {system.status && (
                  <Badge className={`${getStatusColor(system.status)} text-xs`}>
                    {system.status}
                  </Badge>
                )}
              </div>

              {/* Metadata row */}
              <div className="flex flex-wrap items-center gap-4 mt-2 text-xs text-muted-foreground">
                {system.url && (
                  <a
                    href={system.url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className={`flex items-center gap-1 ${linkClass} text-xs`}
                  >
                    <ExternalLink className="w-3 h-3" />
                    Website
                  </a>
                )}
                {system.github_url && (
                  <a
                    href={system.github_url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className={`flex items-center gap-1 ${linkClass} text-xs`}
                  >
                    <ExternalLink className="w-3 h-3" />
                    GitHub
                  </a>
                )}
                {system.language && (
                  <span className="flex items-center gap-1">
                    <Code2 className="w-3 h-3" />
                    {system.language}
                  </span>
                )}
                {system.license && (
                  <span className="flex items-center gap-1">
                    <Scale className="w-3 h-3" />
                    {system.license}
                  </span>
                )}
                {system.star_count != null && system.star_count > 0 && (
                  <span className="flex items-center gap-1">
                    <Star className="w-3 h-3 text-amber-400" />
                    {system.star_count.toLocaleString()}
                  </span>
                )}
              </div>
            </div>
            <Button
              variant="outline"
              size="sm"
              onClick={fetchData}
              className="border-border/50 hover:border-primary/50 hover:bg-primary/10 shrink-0"
            >
              <RefreshCw className="w-4 h-4 mr-2" />
              Refresh
            </Button>
          </div>
        </div>
      </header>

      <main className="container mx-auto px-4 py-6 space-y-4">
        {/* Artifacts — collapsible */}
        {artifacts.length > 0 && (
          <ArtifactList artifacts={artifacts} systemId={id} />
        )}

        {/* Notes — collapsible */}
        {notes.length > 0 && (
          <CollapsibleSection title="Notes" count={notes.length}>
            <NotesList notes={notes} />
          </CollapsibleSection>
        )}

        {artifacts.length === 0 && notes.length === 0 && (
          <p className="text-sm text-muted-foreground italic py-8 text-center">
            No artifacts or notes yet. Use{' '}
            <code className="text-xs bg-muted px-1 py-0.5 rounded">tech-recon ingest</code>{' '}
            to start collecting data about this system.
          </p>
        )}
      </main>

      <footer className="border-t border-border/50 mt-8">
        <div className="container mx-auto px-4 py-4">
          <p className="text-xs text-muted-foreground text-center">
            Tech Recon &bull; Powered by TypeDB + Next.js
          </p>
        </div>
      </footer>
    </div>
  );
}
