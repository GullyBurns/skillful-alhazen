import React from 'react';

const severityConfig: Record<string, { label: string; className: string }> = {
  critical: { label: 'Critical', className: 'bg-red-500/20 text-red-400 border border-red-500/30' },
  moderate: { label: 'Moderate', className: 'bg-orange-500/20 text-orange-400 border border-orange-500/30' },
  minor:    { label: 'Minor',    className: 'bg-yellow-500/20 text-yellow-400 border border-yellow-500/30' },
};

const phaseConfig: Record<string, { label: string; className: string }> = {
  '1': { label: 'Phase 1 · Goal',       className: 'bg-violet-500/20 text-violet-300' },
  '2': { label: 'Phase 2 · Schema',     className: 'bg-blue-500/20 text-blue-300' },
  '3': { label: 'Phase 3 · Sources',    className: 'bg-cyan-500/20 text-cyan-300' },
  '4': { label: 'Phase 4 · Derivation', className: 'bg-emerald-500/20 text-emerald-300' },
  '5': { label: 'Phase 5 · Analysis',   className: 'bg-amber-500/20 text-amber-300' },
};

const feasibilityConfig: Record<string, { label: string; className: string }> = {
  yes:     { label: 'Complete',  className: 'bg-emerald-500/20 text-emerald-400' },
  partial: { label: 'Partial',   className: 'bg-yellow-500/20 text-yellow-400' },
  no:      { label: 'Blocked',   className: 'bg-red-500/20 text-red-400' },
  unknown: { label: 'Unknown',   className: 'bg-zinc-500/20 text-zinc-400' },
};

const decisionTypeConfig: Record<string, { className: string }> = {
  entity:     { className: 'bg-violet-500/20 text-violet-300' },
  relation:   { className: 'bg-blue-500/20 text-blue-300' },
  attribute:  { className: 'bg-cyan-500/20 text-cyan-300' },
  hierarchy:  { className: 'bg-emerald-500/20 text-emerald-300' },
  constraint: { className: 'bg-amber-500/20 text-amber-300' },
};

function Badge({ className, children }: { className: string; children: React.ReactNode }) {
  return (
    <span className={`inline-flex items-center px-2 py-0.5 rounded text-xs font-medium ${className}`}>
      {children}
    </span>
  );
}

export function SeverityBadge({ severity }: { severity?: string | null }) {
  const cfg = severity ? severityConfig[severity.toLowerCase()] : null;
  if (!cfg) return <Badge className="bg-zinc-500/20 text-zinc-400">—</Badge>;
  return <Badge className={cfg.className}>{cfg.label}</Badge>;
}

export function PhaseBadge({ phase }: { phase?: number | null }) {
  const key = String(phase ?? '');
  const cfg = phaseConfig[key];
  if (!cfg) return null;
  return <Badge className={cfg.className}>{cfg.label}</Badge>;
}

export function FeasibilityBadge({ feasibility }: { feasibility?: string | null }) {
  const cfg = feasibility ? feasibilityConfig[feasibility.toLowerCase()] : null;
  if (!cfg) return <Badge className="bg-zinc-500/20 text-zinc-400">Unknown</Badge>;
  return <Badge className={cfg.className}>{cfg.label}</Badge>;
}

export function DecisionTypeBadge({ type }: { type?: string | null }) {
  const cfg = type ? decisionTypeConfig[type.toLowerCase()] : null;
  const label = type ? type.charAt(0).toUpperCase() + type.slice(1) : '—';
  return (
    <Badge className={cfg ? cfg.className : 'bg-zinc-500/20 text-zinc-400'}>
      {label}
    </Badge>
  );
}

export function GapStatusBadge({ status }: { status?: string | null }) {
  if (status === 'resolved') {
    return <Badge className="bg-emerald-500/20 text-emerald-400">Resolved</Badge>;
  }
  return <Badge className="bg-red-500/20 text-red-400">Open</Badge>;
}
