'use client';

import { useState, useEffect } from 'react';
import Link from 'next/link';
import { T } from '@/components/tech-recon/tokens';
import { Icon, BackNav, GroupHeader, StatusBadge, TypeChip } from '@/components/tech-recon/atoms';
import type { Investigation } from '@/lib/tech-recon';

interface InvestigationWithCounts extends Investigation {
  type?: string;
  systems_count?: number;
  analyses_count?: number;
}

// Status group order for sorting
const STATUS_GROUP_ORDER: Record<string, number> = {
  evaluating: 0, synthesis: 0, active: 0,
  scoping: 1,
  paused: 2,
  completed: 3, done: 3,
  archived: 4,
};

const STATUS_GROUP_LABEL: Record<string, string> = {
  evaluating: 'Active', synthesis: 'Active', active: 'Active',
  scoping: 'Scoping',
  paused: 'Paused',
  completed: 'Completed', done: 'Completed',
  archived: 'Archived',
};

function groupByStatus(investigations: InvestigationWithCounts[]) {
  const groups: Record<string, InvestigationWithCounts[]> = {};
  const groupOrder: Record<string, number> = {};

  for (const inv of investigations) {
    const status = (inv.status || 'unknown').toLowerCase();
    const label = STATUS_GROUP_LABEL[status] || 'Other';
    const order = STATUS_GROUP_ORDER[status] ?? 5;
    if (!groups[label]) { groups[label] = []; groupOrder[label] = order; }
    groups[label].push(inv);
  }

  return Object.entries(groups)
    .sort(([a], [b]) => (groupOrder[a] ?? 5) - (groupOrder[b] ?? 5))
    .map(([label, items]) => ({ label, items, accent: label === 'Active' }));
}

function InvestigationRow({ investigation }: { investigation: InvestigationWithCounts }) {
  const statusColor = T.statusColor(investigation.status);
  const isActive = ['active', 'evaluating', 'synthesis'].includes((investigation.status || '').toLowerCase());
  const typeCfg = T.investigationTypeConfig(investigation.type);

  const meta: string[] = [];
  if (investigation.systems_count !== undefined) {
    meta.push(`${investigation.systems_count} system${investigation.systems_count !== 1 ? 's' : ''}`);
  }
  if (investigation.analyses_count) {
    meta.push(`${investigation.analyses_count} analys${investigation.analyses_count !== 1 ? 'es' : 'is'}`);
  }

  return (
    <Link
      href={`/tech-recon/investigation/${investigation.id}`}
      style={{
        display: 'grid',
        gridTemplateColumns: '14px 56px 1fr auto',
        gap: 14,
        alignItems: 'center',
        padding: '10px 14px',
        borderTop: `1px solid ${T.borderDim}`,
        cursor: 'pointer',
        background: 'transparent',
        textDecoration: 'none',
        color: 'inherit',
        transition: 'background 0.12s',
      }}
      onMouseEnter={e => { e.currentTarget.style.background = 'rgba(90,173,175,0.06)'; }}
      onMouseLeave={e => { e.currentTarget.style.background = 'transparent'; }}
    >
      {/* Status dot */}
      <span style={{
        display: 'inline-block', width: 8, height: 8, borderRadius: 4,
        background: isActive ? statusColor : 'transparent',
        border: `1.5px solid ${statusColor}`,
      }} />

      {/* Type chip */}
      <TypeChip short={typeCfg.short} color={typeCfg.color} icon={typeCfg.icon} />

      {/* Name + metadata */}
      <div style={{ minWidth: 0, display: 'flex', flexDirection: 'column', gap: 2 }}>
        <span style={{
          fontSize: 13.5, color: T.fg,
          overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap',
        }}>
          {investigation.name}
        </span>
        <span style={{ fontFamily: T.mono, fontSize: 10.5, color: T.fgFaint }}>
          {meta.length > 0 ? meta.join(' · ') : (investigation.goal ? investigation.goal.slice(0, 80) + (investigation.goal.length > 80 ? '...' : '') : '')}
        </span>
      </div>

      {/* Status badge */}
      <StatusBadge status={investigation.status || 'unknown'} />
    </Link>
  );
}

export default function TechReconPage() {
  const [investigations, setInvestigations] = useState<InvestigationWithCounts[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetch('/api/tech-recon/investigations')
      .then(r => r.ok ? r.json() : Promise.reject(`API returned ${r.status}`))
      .then(json => setInvestigations(json.investigations || []))
      .catch(err => setError(String(err)))
      .finally(() => setLoading(false));
  }, []);

  if (loading) {
    return (
      <div style={{
        minHeight: '100vh', display: 'flex', alignItems: 'center', justifyContent: 'center',
        background: T.bg, fontFamily: T.sans,
      }}>
        <span style={{ fontFamily: T.mono, fontSize: 11, color: T.fgFaint }}>Loading...</span>
      </div>
    );
  }

  const groups = groupByStatus(investigations);

  return (
    <div style={{
      minHeight: '100vh',
      background: T.bg,
      color: T.fg,
      fontFamily: T.sans,
      display: 'flex',
      flexDirection: 'column',
    }}>
      {/* Header */}
      <header style={{
        borderBottom: `1px solid ${T.borderDim}`,
        background: T.bgRaised,
        padding: '20px 24px',
      }}>
        <div style={{ maxWidth: 1200, margin: '0 auto', display: 'flex', alignItems: 'center', gap: 24 }}>
          <BackNav href="/" label="Hub" />
          <div>
            <h1 style={{
              margin: 0,
              fontFamily: T.serif,
              fontSize: 26,
              fontWeight: 400,
              color: T.fg,
              letterSpacing: '-0.4px',
            }}>Tech Recon</h1>
            <span style={{ fontFamily: T.mono, fontSize: 11, color: T.fgDim }}>
              {investigations.length} investigation{investigations.length !== 1 ? 's' : ''} · systematic technology analysis
            </span>
          </div>
        </div>
      </header>

      <main style={{ maxWidth: 1200, margin: '0 auto', padding: '24px', width: '100%', flex: 1 }}>
        {/* Error */}
        {error && (
          <div style={{
            background: 'rgba(200,80,80,0.1)',
            color: '#e05555',
            padding: '12px 16px',
            borderRadius: 4,
            marginBottom: 24,
            border: '1px solid rgba(200,80,80,0.2)',
          }}>
            <strong style={{ fontFamily: T.mono, fontSize: 10.5, letterSpacing: '0.8px', textTransform: 'uppercase' }}>Error</strong>
            <p style={{ fontSize: 13, marginTop: 4, marginBottom: 0 }}>{error}</p>
            <p style={{ fontSize: 12, color: T.fgDim, marginTop: 4, marginBottom: 0 }}>
              Make sure TypeDB is running and the tech-recon skill is configured.
            </p>
          </div>
        )}

        {/* Grouped investigation rows */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: 20 }}>
          {groups.map(group => (
            <section
              key={group.label}
              style={{
                background: group.accent ? 'rgba(90,173,175,0.04)' : T.panel,
                border: `1px solid ${group.accent ? 'rgba(90,173,175,0.32)' : T.borderDim}`,
                borderRadius: 4,
              }}
            >
              <GroupHeader
                label={group.label}
                count={group.items.length}
                hint={group.accent ? 'investigations with active work' : undefined}
              />
              <div>
                {group.items.map(inv => (
                  <InvestigationRow key={inv.id} investigation={inv} />
                ))}
              </div>
            </section>
          ))}
        </div>

        {/* Empty state */}
        {investigations.length === 0 && !error && (
          <div style={{
            display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center',
            padding: '64px 0', textAlign: 'center',
          }}>
            <Icon name="search" size={48} color={T.fgFaint} style={{ marginBottom: 16, opacity: 0.4 }} />
            <h2 style={{ fontFamily: T.serif, fontSize: 18, fontWeight: 400, marginBottom: 8, color: T.fg }}>No investigations yet</h2>
            <p style={{ fontSize: 13, color: T.fgDim, maxWidth: 400, lineHeight: 1.6 }}>
              Start a Tech Recon investigation using the CLI to explore software systems,
              then come back here to see your findings.
            </p>
          </div>
        )}
      </main>

      {/* Footer */}
      <footer style={{
        borderTop: `1px solid ${T.borderDim}`,
        marginTop: 'auto',
        padding: '16px 24px',
      }}>
        <p style={{
          fontFamily: T.mono,
          fontSize: 10,
          color: T.fgFaint,
          textAlign: 'center',
          letterSpacing: '0.8px',
          margin: 0,
        }}>tech-recon · typedb + next.js</p>
      </footer>
    </div>
  );
}
