'use client';

import Link from 'next/link';
import { Database, AlertTriangle, GitCommit, FlaskConical } from 'lucide-react';

interface GapCounts {
  critical: number;
  moderate: number;
  minor: number;
  total: number;
}

export interface DomainSummary {
  id: string;
  name: string;
  description?: string | null;
  skill?: string | null;
  created: string;
  open_gap_counts_by_phase?: Record<string, number>;
  decision_count?: number;
  version_count?: number;
  experiment_count?: number;
}

function countGapsBySeverity(gapCountsByPhase?: Record<string, number>): GapCounts {
  // open_gap_counts_by_phase is phase -> count; we don't have severity here
  const total = Object.values(gapCountsByPhase ?? {}).reduce((a, b) => a + b, 0);
  return { critical: 0, moderate: 0, minor: 0, total };
}

function formatDate(iso: string) {
  return new Date(iso.replace('.000000000', '')).toLocaleDateString('en-US', {
    month: 'short', day: 'numeric', year: 'numeric',
  });
}

export function DomainCard({ domain }: { domain: DomainSummary }) {
  const totalGaps = Object.values(domain.open_gap_counts_by_phase ?? {}).reduce((a, b) => a + b, 0);

  return (
    <Link
      href={`/skill-builder/domain/${domain.id}`}
      className="block group rounded-xl border border-border/50 bg-card/50 hover:bg-card hover:border-violet-500/40 hover:shadow-lg hover:shadow-violet-500/5 transition-all duration-200 p-5"
    >
      <div className="flex items-start justify-between gap-3 mb-3">
        <div className="flex-1 min-w-0">
          <h2 className="text-base font-semibold text-foreground group-hover:text-violet-300 transition-colors truncate">
            {domain.name}
          </h2>
          {domain.skill && domain.skill !== domain.name && (
            <span className="text-xs text-muted-foreground font-mono mt-0.5 block">
              skill: {domain.skill}
            </span>
          )}
        </div>
        {totalGaps > 0 && (
          <span className="flex-shrink-0 flex items-center gap-1 text-xs text-orange-400 bg-orange-500/10 border border-orange-500/20 rounded px-2 py-0.5">
            <AlertTriangle className="w-3 h-3" />
            {totalGaps} gap{totalGaps !== 1 ? 's' : ''}
          </span>
        )}
      </div>

      {domain.description && (
        <p className="text-sm text-muted-foreground line-clamp-2 mb-4">
          {domain.description}
        </p>
      )}

      <div className="flex items-center gap-4 text-xs text-muted-foreground border-t border-border/30 pt-3 mt-auto">
        {(domain.decision_count ?? 0) > 0 && (
          <span className="flex items-center gap-1">
            <Database className="w-3 h-3" />
            {domain.decision_count} decision{domain.decision_count !== 1 ? 's' : ''}
          </span>
        )}
        {(domain.version_count ?? 0) > 0 && (
          <span className="flex items-center gap-1">
            <GitCommit className="w-3 h-3" />
            {domain.version_count} snapshot{domain.version_count !== 1 ? 's' : ''}
          </span>
        )}
        {(domain.experiment_count ?? 0) > 0 && (
          <span className="flex items-center gap-1">
            <FlaskConical className="w-3 h-3" />
            {domain.experiment_count} experiment{domain.experiment_count !== 1 ? 's' : ''}
          </span>
        )}
        <span className="ml-auto">{formatDate(domain.created)}</span>
      </div>
    </Link>
  );
}
