'use client';
import { useState, useEffect } from 'react';
import { T } from '@/components/single-paper-deep-dive/tokens';

interface AnalysisSummary {
  id: string;
  doi?: string;
  title?: string;
  year?: number;
  status: string;
  source_count?: number;
}

const STATUS_ORDER = ['in-progress', 'complete', 'scope-exhausted'];
const STATUS_LABELS: Record<string, string> = {
  'in-progress': 'In Progress',
  'complete': 'Complete',
  'scope-exhausted': 'Scope Exhausted',
};

function Row({ analysis }: { analysis: AnalysisSummary }) {
  const color = T.statusColor(analysis.status);
  const doiHref = analysis.doi ? `https://doi.org/${analysis.doi}` : undefined;

  return (
    <a
      href={`/dive/analysis/${encodeURIComponent(analysis.id)}`}
      style={{
        display: 'flex',
        alignItems: 'flex-start',
        gap: 14,
        padding: '12px 16px',
        border: `1px solid ${T.border}`,
        borderRadius: 6,
        background: T.panel,
        textDecoration: 'none',
        marginBottom: 8,
        transition: 'border-color 0.12s',
      }}
      onMouseEnter={e => (e.currentTarget.style.borderColor = T.borderHi)}
      onMouseLeave={e => (e.currentTarget.style.borderColor = T.border)}
    >
      {/* Status dot */}
      <div style={{ paddingTop: 4, flexShrink: 0 }}>
        <div style={{ width: 8, height: 8, borderRadius: '50%', background: color }} />
      </div>

      {/* Content */}
      <div style={{ flex: 1, minWidth: 0 }}>
        <p style={{
          fontFamily: T.serif,
          fontSize: 15,
          color: T.fg,
          margin: '0 0 4px',
          lineHeight: 1.4,
        }}>
          {analysis.title || analysis.doi || analysis.id}
        </p>
        <div style={{ display: 'flex', alignItems: 'center', gap: 10, flexWrap: 'wrap' }}>
          {analysis.doi && (
            <span
              style={{ fontFamily: T.mono, fontSize: 11, color: T.blue }}
              onClick={e => { e.preventDefault(); if (doiHref) window.open(doiHref, '_blank'); }}
            >
              {analysis.doi}
            </span>
          )}
          {analysis.year && (
            <span style={{ fontFamily: T.mono, fontSize: 11, color: T.fgFaint }}>
              {analysis.year}
            </span>
          )}
          <span style={{
            fontFamily: T.mono,
            fontSize: 10,
            color,
            border: `1px solid ${color}`,
            borderRadius: 3,
            padding: '1px 6px',
            background: `${color}18`,
            textTransform: 'uppercase',
            letterSpacing: '0.06em',
          }}>
            {STATUS_LABELS[analysis.status] || analysis.status}
          </span>
        </div>
      </div>

      {/* Sources */}
      <div style={{ textAlign: 'right', flexShrink: 0 }}>
        <span style={{ fontFamily: T.mono, fontSize: 11, color: T.fgFaint }}>
          {analysis.source_count != null ? `${analysis.source_count}/100 sources` : 'no sources yet'}
        </span>
      </div>
    </a>
  );
}

export default function DivePage() {
  const [analyses, setAnalyses] = useState<AnalysisSummary[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetch('/api/single-paper-deep-dive/analyses')
      .then(r => r.json())
      .then(d => { setAnalyses(d.analyses || []); setLoading(false); })
      .catch(() => setLoading(false));
  }, []);

  const grouped: Record<string, AnalysisSummary[]> = {};
  analyses.forEach(a => {
    const key = a.status || 'unknown';
    (grouped[key] = grouped[key] || []).push(a);
  });

  const total = analyses.length;
  const complete = (grouped['complete'] || []).length;
  const inProgress = (grouped['in-progress'] || []).length;

  return (
    <div style={{
      maxWidth: 960,
      margin: '0 auto',
      padding: '32px 24px',
      fontFamily: T.sans,
      color: T.fg,
    }}>
      {/* Page header */}
      <div style={{ marginBottom: 24 }}>
        <h1 style={{ fontFamily: T.serif, fontSize: 26, color: T.fg, margin: '0 0 6px' }}>
          Paper Deep Dive
        </h1>
        <p style={{ fontFamily: T.sans, fontSize: 13, color: T.fgDim, margin: 0 }}>
          Structured claim extraction, evidence tracing, and citation impact analysis.
        </p>
      </div>

      {/* Stats bar */}
      <div style={{
        display: 'flex',
        gap: 12,
        marginBottom: 24,
      }}>
        {[
          { label: 'Total', value: total, color: T.teal },
          { label: 'Complete', value: complete, color: T.mint },
          { label: 'In Progress', value: inProgress, color: T.blue },
        ].map(s => (
          <div key={s.label} style={{
            padding: '10px 16px',
            border: `1px solid ${T.border}`,
            borderRadius: 6,
            background: T.panel,
            minWidth: 80,
          }}>
            <div style={{ fontFamily: T.mono, fontSize: 20, color: s.color, fontWeight: 600 }}>
              {loading ? '—' : s.value}
            </div>
            <div style={{ fontFamily: T.mono, fontSize: 10, color: T.fgFaint, textTransform: 'uppercase', letterSpacing: '0.08em', marginTop: 2 }}>
              {s.label}
            </div>
          </div>
        ))}
      </div>

      {/* Analyses list */}
      {loading ? (
        <p style={{ fontFamily: T.mono, fontSize: 12, color: T.fgFaint }}>Loading...</p>
      ) : analyses.length === 0 ? (
        <div style={{ padding: 32, textAlign: 'center', border: `1px solid ${T.borderDim}`, borderRadius: 6 }}>
          <p style={{ fontFamily: T.mono, fontSize: 12, color: T.fgFaint }}>
            No analyses yet. Start one with the single-paper-deep-dive skill.
          </p>
        </div>
      ) : (
        STATUS_ORDER.map(status => {
          const group = grouped[status];
          if (!group || group.length === 0) return null;
          return (
            <div key={status} style={{ marginBottom: 24 }}>
              <div style={{
                fontFamily: T.mono,
                fontSize: 11,
                color: T.fgFaint,
                textTransform: 'uppercase',
                letterSpacing: '0.1em',
                marginBottom: 8,
              }}>
                {STATUS_LABELS[status]} ({group.length})
              </div>
              {group.map(a => <Row key={a.id} analysis={a} />)}
            </div>
          );
        })
      )}
    </div>
  );
}
