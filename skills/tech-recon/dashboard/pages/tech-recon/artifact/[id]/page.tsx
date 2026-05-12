'use client';

import { useState, useEffect, use } from 'react';
import { T } from '@/components/tech-recon/tokens';
import { Icon, Panel, KV, BackNav } from '@/components/tech-recon/atoms';
import type { TechReconArtifact } from '@/lib/tech-recon';

interface ArtifactWithPreview extends TechReconArtifact {
  content_preview?: string;
}

export default function ArtifactPage({ params }: { params: Promise<{ id: string }> }) {
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
      <div style={{ minHeight: '100vh', display: 'flex', alignItems: 'center', justifyContent: 'center', background: T.bg }}>
        <span style={{ fontFamily: T.mono, fontSize: 11, color: T.fgFaint }}>Loading...</span>
      </div>
    );
  }

  if (error || !artifact) {
    return (
      <div style={{ minHeight: '100vh', background: T.bg, color: T.fg, fontFamily: T.sans }}>
        <header style={{ borderBottom: `1px solid ${T.borderDim}`, background: T.bgRaised, padding: '12px 24px' }}>
          <BackNav href="/tech-recon" label="Tech Recon" />
        </header>
        <main style={{ maxWidth: 1200, margin: '0 auto', padding: '48px 24px', textAlign: 'center' }}>
          <p style={{ color: '#e05555' }}>{error || 'Artifact not found'}</p>
        </main>
      </div>
    );
  }

  const preview = artifact.content_preview ? artifact.content_preview.slice(0, 2000) : null;

  return (
    <div style={{ minHeight: '100vh', display: 'flex', flexDirection: 'column', background: T.bg, color: T.fg, fontFamily: T.sans }}>
      {/* Header */}
      <header style={{
        borderBottom: `1px solid ${T.borderDim}`,
        background: T.bgRaised,
        padding: '12px 24px',
        display: 'flex', alignItems: 'center', justifyContent: 'space-between',
      }}>
        <BackNav href="/tech-recon" label="Tech Recon" />
        <div style={{ display: 'flex', alignItems: 'center', gap: 12, flexShrink: 0 }}>
          {artifact.url && (
            <a href={artifact.url} target="_blank" rel="noopener noreferrer" style={{
              color: T.teal, textDecoration: 'none', fontSize: 12,
              display: 'flex', alignItems: 'center', gap: 4,
              fontFamily: T.mono,
            }}>
              <Icon name="external" size={14} /> Open URL
            </a>
          )}
          <button
            onClick={fetchData}
            style={{
              fontFamily: T.mono, fontSize: 10.5, color: T.fgDim,
              padding: '6px 12px', borderRadius: 2,
              border: `1px solid ${T.borderDim}`, background: 'transparent',
              cursor: 'pointer', display: 'flex', alignItems: 'center', gap: 6,
            }}
          >
            <Icon name="refresh" size={14} />
            refresh
          </button>
        </div>
      </header>

      <main style={{ maxWidth: 1200, margin: '0 auto', padding: 24, flex: 1, width: '100%' }}>
        {/* Title + metadata */}
        <div style={{ marginBottom: 24 }}>
          <h1 style={{
            margin: '0 0 8px', fontFamily: T.serif, fontSize: 22, lineHeight: 1.3,
            fontWeight: 400, color: T.fg, wordBreak: 'break-all',
          }}>{artifact.url || artifact.id}</h1>

          <div style={{
            display: 'flex', flexWrap: 'wrap', gap: 14, marginTop: 12, paddingTop: 12,
            borderTop: `1px solid ${T.borderDim}`,
          }}>
            {artifact.type && (
              <div style={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
                <span style={{ fontFamily: T.mono, fontSize: 9.5, letterSpacing: '1.2px', textTransform: 'uppercase', color: T.fgFaint }}>Type</span>
                <span style={{
                  fontFamily: T.mono, fontSize: 10.5, letterSpacing: '0.6px', fontWeight: 600,
                  textTransform: 'uppercase', padding: '2px 7px', borderRadius: 2,
                  color: T.artifactTypeColor(artifact.type),
                  border: `1px solid ${T.artifactTypeColor(artifact.type)}66`,
                }}>{artifact.type}</span>
              </div>
            )}
            {artifact.format && (
              <div style={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
                <span style={{ fontFamily: T.mono, fontSize: 9.5, letterSpacing: '1.2px', textTransform: 'uppercase', color: T.fgFaint }}>Format</span>
                <span style={{
                  fontFamily: T.mono, fontSize: 10.5, letterSpacing: '0.6px', fontWeight: 600,
                  textTransform: 'uppercase', padding: '2px 7px', borderRadius: 2,
                  color: T.formatColor(artifact.format),
                  border: `1px solid ${T.formatColor(artifact.format)}66`,
                }}>{artifact.format}</span>
              </div>
            )}
            <div style={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
              <span style={{ fontFamily: T.mono, fontSize: 9.5, letterSpacing: '1.2px', textTransform: 'uppercase', color: T.fgFaint }}>Cache</span>
              {artifact.cache_path ? (
                <span style={{ fontSize: 13, color: T.teal, fontFamily: T.mono, display: 'flex', alignItems: 'center', gap: 4 }}>
                  <Icon name="check" size={14} color={T.teal} /> Cached
                </span>
              ) : (
                <span style={{ fontSize: 13, color: T.fgFaint, fontFamily: T.mono }}>Not cached</span>
              )}
            </div>
          </div>
          {artifact.cache_path && (
            <p style={{ fontFamily: T.mono, fontSize: 10, color: T.fgFaint, marginTop: 8 }}>{artifact.cache_path}</p>
          )}
        </div>

        {/* Content preview panel */}
        <Panel title="Content Preview">
          {preview ? (
            <pre style={{
              fontFamily: T.mono, fontSize: 12, lineHeight: 1.5,
              background: T.bgSunken, border: `1px solid ${T.borderDim}`,
              borderRadius: 4, padding: 16, overflowX: 'auto',
              whiteSpace: 'pre-wrap', maxHeight: '70vh', color: T.fg,
            }}><code>{preview}</code></pre>
          ) : (
            <p style={{ fontSize: 13, color: T.fgFaint, fontStyle: 'italic', padding: '16px 0' }}>
              No content preview available. The artifact may need to be ingested first.
            </p>
          )}
        </Panel>
      </main>

      <footer style={{ borderTop: `1px solid ${T.borderDim}`, marginTop: 'auto', padding: '16px 24px' }}>
        <div style={{
          maxWidth: 1200, margin: '0 auto',
          display: 'flex', alignItems: 'center', gap: 10,
          fontFamily: T.mono, fontSize: 10, color: T.fgFaint, letterSpacing: '0.6px',
        }}>
          <span>artifact · {id}</span>
          <span>·</span>
          <span>shape: show-artifact --json</span>
        </div>
      </footer>
    </div>
  );
}
