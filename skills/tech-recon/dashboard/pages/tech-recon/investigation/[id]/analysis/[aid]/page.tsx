'use client';

import { useState, useEffect, use } from 'react';
import Link from 'next/link';
import { T } from '@/components/tech-recon/tokens';
import { Icon, BackNav, Panel } from '@/components/tech-recon/atoms';
import { AnalysisRunner } from '@/components/tech-recon/analysis-runner';
import type { TechReconAnalysis } from '@/lib/tech-recon';

export default function AnalysisPage({ params }: { params: Promise<{ id: string; aid: string }> }) {
  const { id, aid } = use(params);
  const [analysis, setAnalysis] = useState<TechReconAnalysis | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    setLoading(true);
    setError(null);
    fetch(`/api/tech-recon/analysis/${aid}`)
      .then(r => { if (!r.ok) throw new Error(`API error: ${r.status}`); return r.json(); })
      .then(json => setAnalysis(json.analysis || json))
      .catch(err => setError(err instanceof Error ? err.message : String(err)))
      .finally(() => setLoading(false));
  }, [aid]);

  if (loading) {
    return (
      <div style={{ minHeight: '100vh', display: 'flex', alignItems: 'center', justifyContent: 'center', background: T.bg }}>
        <Icon name="refresh" size={24} color={T.fgFaint} />
      </div>
    );
  }

  if (error || !analysis) {
    return (
      <div style={{ minHeight: '100vh', background: T.bg, color: T.fg, fontFamily: T.sans }}>
        <header style={{ borderBottom: `1px solid ${T.borderDim}`, background: T.bgRaised, padding: '12px 24px' }}>
          <BackNav href={`/tech-recon/investigation/${id}`} label="Investigation" />
        </header>
        <main style={{ maxWidth: 1200, margin: '0 auto', padding: '48px 24px', textAlign: 'center' }}>
          <p style={{ color: '#e05555' }}>{error || 'Analysis not found'}</p>
        </main>
      </div>
    );
  }

  const typeColor = T.analysisTypeColor(analysis.type);

  return (
    <div style={{ minHeight: '100vh', display: 'flex', flexDirection: 'column', background: T.bg, color: T.fg, fontFamily: T.sans }}>
      {/* Header breadcrumb */}
      <header style={{
        borderBottom: `1px solid ${T.borderDim}`,
        background: T.bgRaised,
        padding: '12px 24px',
      }}>
        <div style={{ maxWidth: 1200, margin: '0 auto', display: 'flex', alignItems: 'center', gap: 12, fontSize: 12 }}>
          <BackNav href="/tech-recon" label="Tech Recon" />
          <span style={{ color: T.fgFaint }}>/</span>
          <Link href={`/tech-recon/investigation/${id}`} style={{ color: T.teal, textDecoration: 'none', fontFamily: T.mono, fontSize: 12 }}>
            Investigation
          </Link>
        </div>
      </header>

      <main style={{ maxWidth: 1200, margin: '0 auto', padding: 24, flex: 1, width: '100%' }}>
        {/* Title + type badge */}
        <div style={{ marginBottom: 24 }}>
          <div style={{ display: 'flex', alignItems: 'flex-start', gap: 12, marginBottom: 8 }}>
            <h1 style={{
              margin: 0, fontFamily: T.serif, fontSize: 28, lineHeight: 1.15,
              fontWeight: 400, color: T.fg, letterSpacing: '-0.4px', flex: 1,
            }}>{analysis.title}</h1>
            {analysis.type && (
              <span style={{
                fontFamily: T.mono, fontSize: 10.5, letterSpacing: '0.6px', fontWeight: 600,
                textTransform: 'uppercase', padding: '3px 8px', borderRadius: 2,
                color: typeColor, border: `1px solid ${typeColor}66`,
                background: T.tintBg(typeColor), flexShrink: 0, marginTop: 4,
              }}>{analysis.type}</span>
            )}
          </div>

          {analysis.description && (
            <p style={{ fontSize: 13.5, lineHeight: 1.55, color: T.fgDim, maxWidth: 640, margin: 0 }}>
              {analysis.description}
            </p>
          )}
        </div>

        {/* Analysis panel */}
        <Panel title="Analysis">
          <AnalysisRunner
            analysisId={aid}
            title={analysis.title}
            description={analysis.description}
            plotCode={analysis.plot_code}
            analysisType={analysis.type || 'plot'}
          />

          {analysis.query && (
            <div style={{ marginTop: 20, paddingTop: 20, borderTop: `1px solid ${T.borderDim}` }}>
              <h2 style={{
                fontFamily: T.mono, fontSize: 10.5, fontWeight: 600, textTransform: 'uppercase',
                letterSpacing: '1px', color: T.fgDim, marginBottom: 12,
              }}>Query</h2>
              <pre style={{
                fontFamily: T.mono, fontSize: 12, background: T.bgSunken,
                border: `1px solid ${T.borderDim}`, borderRadius: 4,
                padding: 16, overflowX: 'auto', color: T.fg,
              }}><code>{analysis.query}</code></pre>
            </div>
          )}
        </Panel>
      </main>

      <footer style={{ borderTop: `1px solid ${T.borderDim}`, marginTop: 'auto', padding: '16px 24px' }}>
        <div style={{
          maxWidth: 1200, margin: '0 auto',
          display: 'flex', alignItems: 'center', gap: 10,
          fontFamily: T.mono, fontSize: 10, color: T.fgFaint, letterSpacing: '0.6px',
        }}>
          <span>analysis · {aid}</span>
          <span>·</span>
          <span>shape: show-analysis --json</span>
        </div>
      </footer>
    </div>
  );
}
