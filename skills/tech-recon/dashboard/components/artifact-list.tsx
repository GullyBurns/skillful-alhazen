'use client';

import { useState } from 'react';
import Link from 'next/link';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { ChevronDown, ChevronRight, ExternalLink, HardDrive, AlertCircle } from 'lucide-react';
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

function getTypeColor(type: string | null | undefined): string {
  if (!type) return 'bg-slate-500/20 text-slate-300 border-slate-500/30';
  return TYPE_COLORS[type.toLowerCase()] || 'bg-slate-500/20 text-slate-300 border-slate-500/30';
}

function ArtifactItem({ artifact, systemId }: { artifact: TechReconArtifact; systemId: string }) {
  return (
    <div className="flex items-center gap-2 py-1.5 text-sm">
      <Link
        href={`/tech-recon/artifact/${artifact.id}`}
        className={`flex-1 truncate ${linkClass}`}
      >
        {artifact.url || artifact.id}
      </Link>
      <div className="flex items-center gap-1.5 shrink-0">
        {artifact.type && (
          <Badge className={`${getTypeColor(artifact.type)} text-xs`}>
            {artifact.type}
          </Badge>
        )}
        {artifact.cache_path ? (
          <span title="Cached" className="flex items-center text-green-400">
            <HardDrive className="w-3.5 h-3.5" />
          </span>
        ) : (
          <span title="Not cached" className="flex items-center text-muted-foreground/40">
            <AlertCircle className="w-3.5 h-3.5" />
          </span>
        )}
        {artifact.url && (
          <a
            href={artifact.url}
            target="_blank"
            rel="noopener noreferrer"
            className="text-muted-foreground hover:text-foreground"
            title="Open URL"
          >
            <ExternalLink className="w-3.5 h-3.5" />
          </a>
        )}
      </div>
    </div>
  );
}

interface ArtifactListProps {
  artifacts: TechReconArtifact[];
  systemId: string;
}

export function ArtifactList({ artifacts, systemId }: ArtifactListProps) {
  const [open, setOpen] = useState(false);

  if (artifacts.length === 0) {
    return (
      <p className="text-sm text-muted-foreground italic">No artifacts yet.</p>
    );
  }

  // Group by artifact type
  const groups = artifacts.reduce<Record<string, TechReconArtifact[]>>((acc, artifact) => {
    const key = artifact.type || 'other';
    if (!acc[key]) acc[key] = [];
    acc[key].push(artifact);
    return acc;
  }, {});

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
        <span className="text-sm font-medium">Artifacts</span>
        <Badge variant="secondary" className="ml-auto text-xs">
          {artifacts.length}
        </Badge>
      </button>
      {open && (
        <div className="p-4 border-t border-border/50 space-y-4">
          {Object.entries(groups).map(([type, typeArtifacts]) => (
            <div key={type}>
              <div className="flex items-center gap-2 mb-2">
                <Badge className={`${getTypeColor(type)} text-xs`}>{type}</Badge>
                <span className="text-xs text-muted-foreground">{typeArtifacts.length}</span>
              </div>
              <div className="space-y-0.5 divide-y divide-border/30">
                {typeArtifacts.map((artifact) => (
                  <ArtifactItem key={artifact.id} artifact={artifact} systemId={systemId} />
                ))}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
