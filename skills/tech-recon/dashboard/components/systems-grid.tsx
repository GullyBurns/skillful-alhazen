'use client';

import Link from 'next/link';
import { Badge } from '@/components/ui/badge';
import { ExternalLink, Star, Code2 } from 'lucide-react';
import type { TechReconSystem } from '@/lib/tech-recon';

const linkClass =
  'text-cyan-400 font-semibold underline underline-offset-2 hover:text-blue-400 transition-colors';

const STATUS_COLORS: Record<string, string> = {
  candidate: 'bg-slate-500/20 text-slate-300 border-slate-500/30',
  confirmed: 'bg-blue-500/20 text-blue-400 border-blue-500/30',
  ingested: 'bg-yellow-500/20 text-yellow-400 border-yellow-500/30',
  analyzed: 'bg-green-500/20 text-green-400 border-green-500/30',
  excluded: 'bg-red-500/20 text-red-400 border-red-500/30',
};

const LANGUAGE_COLORS: Record<string, string> = {
  python: 'bg-blue-500/20 text-blue-300 border-blue-500/30',
  typescript: 'bg-cyan-500/20 text-cyan-300 border-cyan-500/30',
  javascript: 'bg-yellow-500/20 text-yellow-300 border-yellow-500/30',
  rust: 'bg-orange-500/20 text-orange-300 border-orange-500/30',
  go: 'bg-sky-500/20 text-sky-300 border-sky-500/30',
  java: 'bg-red-500/20 text-red-300 border-red-500/30',
};

function getStatusColor(status: string | null | undefined): string {
  if (!status) return 'bg-slate-500/20 text-slate-300 border-slate-500/30';
  return STATUS_COLORS[status.toLowerCase()] || 'bg-slate-500/20 text-slate-300 border-slate-500/30';
}

function getLanguageColor(language: string | null | undefined): string {
  if (!language) return 'bg-slate-500/20 text-slate-300 border-slate-500/30';
  return LANGUAGE_COLORS[language.toLowerCase()] || 'bg-slate-500/20 text-slate-300 border-slate-500/30';
}

interface SystemsGridProps {
  systems: TechReconSystem[];
  investigationId?: string;
}

export function SystemsGrid({ systems }: SystemsGridProps) {
  if (systems.length === 0) {
    return (
      <p className="text-sm text-muted-foreground italic">No systems added yet.</p>
    );
  }

  return (
    <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
      {systems.map((system) => (
        <div
          key={system.id}
          className="border border-border/50 rounded-lg bg-card/30 hover:border-primary/30 hover:bg-card/60 transition-all p-3 space-y-2"
        >
          <div className="flex items-start justify-between gap-2">
            <Link
              href={`/tech-recon/system/${system.id}`}
              className={`text-sm font-medium ${linkClass}`}
            >
              {system.name}
            </Link>
            <Badge className={`${getStatusColor(system.status)} text-xs shrink-0`}>
              {system.status || 'unknown'}
            </Badge>
          </div>

          <div className="flex flex-wrap items-center gap-2 text-xs text-muted-foreground">
            {system.url && (
              <a
                href={system.url}
                target="_blank"
                rel="noopener noreferrer"
                className={`flex items-center gap-1 text-xs ${linkClass}`}
              >
                <ExternalLink className="w-3 h-3" />
                Link
              </a>
            )}
            {system.star_count != null && system.star_count > 0 && (
              <span className="flex items-center gap-1">
                <Star className="w-3 h-3 text-amber-400" />
                {system.star_count.toLocaleString()}
              </span>
            )}
          </div>

          <div className="flex flex-wrap items-center gap-2">
            <span className="text-xs text-muted-foreground">
              {system.artifacts_count ?? 0} sources &middot; {system.notes_count ?? 0} notes
            </span>
            {(system.artifacts_count ?? 0) < 3 && (
              <Badge className="bg-amber-500/20 text-amber-400 border-amber-500/30 text-xs">
                &#9888; shallow
              </Badge>
            )}
          </div>

          {system.language && (
            <div className="flex items-center gap-1.5">
              <Code2 className="w-3 h-3 text-muted-foreground/60" />
              <Badge className={`${getLanguageColor(system.language)} text-xs`}>
                {system.language}
              </Badge>
            </div>
          )}
        </div>
      ))}
    </div>
  );
}
