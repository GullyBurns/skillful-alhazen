'use client';

import { useState, useEffect, use } from 'react';
import Link from 'next/link';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { ArrowLeft, RefreshCw, ExternalLink, HardDrive } from 'lucide-react';
import type { TechReconArtifact } from '@/lib/tech-recon';

const linkClass =
  'text-cyan-400 font-semibold underline underline-offset-2 hover:text-blue-400 transition-colors';

const TYPE_COLORS: Record<string, string> = {
  documentation: 'bg-blue-500/20 text-blue-400 border-blue-500/30',
  'source-code': 'bg-green-500/20 text-green-400 border-green-500/30',
  'api-response': 'bg-amber-500/20 text-amber-400 border-amber-500/30',
  screenshot: 'bg-purple-500/20 text-purple-400 border-purple-500/30',
  config: 'bg-cyan-500/20 text-cyan-400 border-cyan-500/30',
  analysis: 'bg-indigo-500/20 text-indigo-400 border-indigo-500/30',
};

const FORMAT_COLORS: Record<string, string> = {
  html: 'bg-orange-500/20 text-orange-400 border-orange-500/30',
  json: 'bg-yellow-500/20 text-yellow-400 border-yellow-500/30',
  yaml: 'bg-green-500/20 text-green-400 border-green-500/30',
  markdown: 'bg-blue-500/20 text-blue-400 border-blue-500/30',
  pdf: 'bg-red-500/20 text-red-400 border-red-500/30',
  text: 'bg-slate-500/20 text-slate-300 border-slate-500/30',
};

function getTypeColor(type: string | null | undefined): string {
  if (!type) return 'bg-slate-500/20 text-slate-300 border-slate-500/30';
  return TYPE_COLORS[type.toLowerCase()] || 'bg-slate-500/20 text-slate-300 border-slate-500/30';
}

function getFormatColor(format: string | null | undefined): string {
  if (!format) return 'bg-slate-500/20 text-slate-300 border-slate-500/30';
  return FORMAT_COLORS[format.toLowerCase()] || 'bg-slate-500/20 text-slate-300 border-slate-500/30';
}

interface ArtifactWithPreview extends TechReconArtifact {
  content_preview?: string;
}

interface ArtifactPageProps {
  params: Promise<{ id: string }>;
}

export default function ArtifactPage({ params }: ArtifactPageProps) {
  const { id } = use(params);
  const [artifact, setArtifact] = useState<ArtifactWithPreview | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchData = async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await fetch(`/api/tech-recon/artifact/${id}`);
      if (!res.ok) throw new Error(`API error: ${res.status}`);
      const json = await res.json();
      setArtifact(json.artifact || json);
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
        <RefreshCw className="w-6 h-6 animate-spin text-muted-foreground" />
      </div>
    );
  }

  if (error || !artifact) {
    return (
      <div className="min-h-screen p-8">
        <Link href="/tech-recon" className={`flex items-center gap-2 text-sm mb-4 ${linkClass}`}>
          <ArrowLeft className="w-4 h-4" />
          Back to Tech Recon
        </Link>
        <div className="bg-destructive/10 text-destructive px-4 py-3 rounded-lg">
          <strong>Error:</strong> {error || 'Artifact not found'}
        </div>
      </div>
    );
  }

  const preview = artifact.content_preview
    ? artifact.content_preview.slice(0, 2000)
    : null;

  return (
    <div className="min-h-screen">
      <header className="border-b border-border/50 bg-card/50 backdrop-blur-sm">
        <div className="container mx-auto px-4 py-4">
          <Link href="/tech-recon" className={`flex items-center gap-2 text-sm mb-3 ${linkClass}`}>
            <ArrowLeft className="w-4 h-4" />
            Tech Recon
          </Link>
          <div className="flex items-start justify-between gap-4">
            <div className="space-y-2">
              <h1 className="text-xl font-bold text-foreground break-all">
                {artifact.url || artifact.id}
              </h1>
              <div className="flex flex-wrap items-center gap-2">
                {artifact.type && (
                  <Badge className={`${getTypeColor(artifact.type)} text-xs`}>
                    {artifact.type}
                  </Badge>
                )}
                {artifact.format && (
                  <Badge className={`${getFormatColor(artifact.format)} text-xs`}>
                    {artifact.format}
                  </Badge>
                )}
                {artifact.cache_path ? (
                  <span className="flex items-center gap-1 text-xs text-green-400">
                    <HardDrive className="w-3.5 h-3.5" />
                    Cached
                  </span>
                ) : (
                  <span className="text-xs text-muted-foreground">Not cached</span>
                )}
              </div>
              {artifact.cache_path && (
                <p className="text-xs text-muted-foreground font-mono">
                  {artifact.cache_path}
                </p>
              )}
            </div>
            <div className="flex items-center gap-2 shrink-0">
              {artifact.url && (
                <a
                  href={artifact.url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className={`flex items-center gap-1.5 text-sm ${linkClass}`}
                >
                  <ExternalLink className="w-4 h-4" />
                  Open URL
                </a>
              )}
              <Button
                variant="outline"
                size="sm"
                onClick={fetchData}
                className="border-border/50 hover:border-primary/50 hover:bg-primary/10"
              >
                <RefreshCw className="w-4 h-4 mr-2" />
                Refresh
              </Button>
            </div>
          </div>
        </div>
      </header>

      <main className="container mx-auto px-4 py-6">
        {preview ? (
          <div>
            <h2 className="text-xs font-semibold uppercase tracking-widest text-muted-foreground mb-3">
              Content Preview (first 2000 chars)
            </h2>
            <pre className="text-xs rounded-lg bg-muted/50 border border-border/40 p-4 overflow-x-auto whitespace-pre-wrap max-h-[70vh]">
              <code>{preview}</code>
            </pre>
          </div>
        ) : (
          <p className="text-sm text-muted-foreground italic">
            No content preview available. The artifact may need to be ingested first.
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
