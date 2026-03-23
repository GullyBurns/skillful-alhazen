'use client';

import { SeverityBadge, PhaseBadge, GapStatusBadge } from './badges';
import { AlertTriangle } from 'lucide-react';

export interface Gap {
  id: string;
  name?: string;
  description?: string;
  phase?: number;
  severity?: string;
  status?: string;
  created?: string;
}

function formatDate(iso?: string) {
  if (!iso) return '';
  return new Date(iso.replace('.000000000', '')).toLocaleDateString('en-US', {
    month: 'short', day: 'numeric', year: 'numeric',
  });
}

const SEVERITY_ORDER: Record<string, number> = { critical: 0, moderate: 1, minor: 2 };

export function GapsList({ gaps }: { gaps: Gap[] }) {
  if (gaps.length === 0) {
    return (
      <div className="text-sm text-muted-foreground italic px-1">No open gaps recorded.</div>
    );
  }

  const sorted = [...gaps].sort((a, b) => {
    const sa = SEVERITY_ORDER[a.severity?.toLowerCase() ?? ''] ?? 9;
    const sb = SEVERITY_ORDER[b.severity?.toLowerCase() ?? ''] ?? 9;
    return sa - sb;
  });

  return (
    <div className="space-y-3">
      {sorted.map((gap) => (
        <div
          key={gap.id}
          className="rounded-lg border border-border/40 bg-card/30 p-4 space-y-2"
        >
          <div className="flex flex-wrap items-center gap-2">
            <SeverityBadge severity={gap.severity} />
            {gap.phase != null && <PhaseBadge phase={gap.phase} />}
            <GapStatusBadge status={gap.status} />
            {gap.created && (
              <span className="ml-auto text-xs text-muted-foreground">{formatDate(gap.created)}</span>
            )}
          </div>
          <p className="text-sm text-foreground/90 leading-relaxed">
            {gap.description ?? gap.name ?? '(no description)'}
          </p>
        </div>
      ))}
    </div>
  );
}
