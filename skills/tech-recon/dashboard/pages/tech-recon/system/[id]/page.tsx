'use client';

import { useState, useEffect, use } from 'react';
import Link from 'next/link';
import { T } from '@/components/tech-recon/tokens';
import { Icon, Panel, KV, BackNav, StatusBadge, MarkdownContent } from '@/components/tech-recon/atoms';
import type { TechReconSystem, TechReconArtifact, TechReconNote } from '@/lib/tech-recon';

// ─── Note Item (expandable) ────────────────────────────────────

function NoteItem({ note }: { note: TechReconNote }) {
  const [open, setOpen] = useState(false);
  const [fullContent, setFullContent] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [fetched, setFetched] = useState(false);

  const toggle = () => {
    if (!open && !fetched) {
      setFetched(true);
      setLoading(true);
      fetch(`/api/tech-recon/note/${note.id}`)
        .then(r => r.json())
        .then(d => { if (d.note?.content) setFullContent(d.note.content); })
        .catch(() => setFullContent(note.content_preview ?? null))
        .finally(() => setLoading(false));
    }
    setOpen(!open);
  };

  const preview = note.content_preview ?? note.content ?? '';
  const firstLine = preview.split('\n').find(l => l.trim().length > 0)?.replace(/^#+\s*/, '').trim() ?? note.topic;
  const fmt = (note.format || 'md').toLowerCase();
  const topicCfg = T.topicConfig(note.topic);
  const content = fullContent ?? preview;

  return (
    <div style={{ borderTop: `1px solid ${T.borderDim}` }}>
      <button
        onClick={toggle}
        style={{
          width: '100%', display: 'flex', alignItems: 'center', gap: 8,
          padding: '8px 12px', textAlign: 'left', cursor: 'pointer',
          background: 'transparent', border: 'none', color: 'inherit',
        }}
        onMouseEnter={e => { e.currentTarget.style.background = 'rgba(12,22,40,0.5)'; }}
        onMouseLeave={e => { e.currentTarget.style.background = 'transparent'; }}
      >
        <Icon name={open ? 'chevron-down' : 'chevron-right'} size={14} color={T.fgFaint} />
        <Icon name={topicCfg.icon} size={14} color={topicCfg.color} />
        {note.topic && (
          <span style={{
            fontFamily: T.mono, fontSize: 10, padding: '1px 6px', borderRadius: 2,
            border: `1px solid ${T.borderDim}`, color: T.fgDim,
          }}>{note.topic}</span>
        )}
        <span style={{
          fontFamily: T.mono, fontSize: 10, padding: '1px 6px', borderRadius: 2,
          border: `1px solid ${T.formatColor(note.format)}66`, color: T.formatColor(note.format),
        }}>{note.format}</span>
        <span style={{ flex: 1, fontSize: 12, color: T.fgDim, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
          {firstLine}
        </span>
      </button>
      {open && (
        <div style={{ padding: '12px 16px', borderTop: `1px solid ${T.borderDim}`, background: T.bgSunken }}>
          {loading ? (
            <p style={{ fontSize: 12, color: T.fgDim }}>Loading...</p>
          ) : fmt === 'md' || fmt === 'markdown' ? (
            <MarkdownContent content={content} />
          ) : (
            <pre style={{
              fontFamily: T.mono, fontSize: 12, background: T.bgSunken,
              border: `1px solid ${T.borderDim}`, borderRadius: 4,
              padding: 12, overflowX: 'auto', color: T.fg,
            }}><code>{content}</code></pre>
          )}
        </div>
      )}
    </div>
  );
}

// ─── Main Page ─────────────────────────────────────────────────

interface PageData {
  system: TechReconSystem;
  artifacts: TechReconArtifact[];
  notes: TechReconNote[];
  investigation?: { id: string; name: string };
}

export default function SystemPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params);
  const [data, setData] = useState<PageData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchData = async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await fetch(`/api/tech-recon/system/${id}`);
      if (!res.ok) throw new Error(`API error: ${res.status}`);
      setData(await res.json());
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

  if (error || !data) {
    return (
      <div style={{ minHeight: '100vh', background: T.bg, color: T.fg, fontFamily: T.sans }}>
        <header style={{ borderBottom: `1px solid ${T.borderDim}`, background: T.bgRaised, padding: '12px 24px' }}>
          <BackNav href="/tech-recon" label="Tech Recon" />
        </header>
        <main style={{ maxWidth: 1200, margin: '0 auto', padding: '48px 24px', textAlign: 'center' }}>
          <p style={{ color: '#e05555' }}>{error || 'System not found'}</p>
        </main>
      </div>
    );
  }

  const { system, artifacts, notes, investigation } = data;

  return (
    <div style={{ minHeight: '100vh', display: 'flex', flexDirection: 'column', background: T.bg, color: T.fg, fontFamily: T.sans }}>
      {/* Header with breadcrumb */}
      <header style={{
        borderBottom: `1px solid ${T.borderDim}`,
        background: T.bgRaised,
        padding: '12px 24px',
        display: 'flex', alignItems: 'center', justifyContent: 'space-between',
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 12, fontSize: 12 }}>
          <BackNav href="/tech-recon" label="Tech Recon" />
          {investigation && (
            <>
              <span style={{ color: T.fgFaint }}>/</span>
              <Link href={`/tech-recon/investigation/${investigation.id}`} style={{ color: T.teal, textDecoration: 'none', fontFamily: T.mono, fontSize: 12 }}>
                {investigation.name}
              </Link>
            </>
          )}
        </div>
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
      </header>

      <main style={{ maxWidth: 1200, margin: '0 auto', padding: 24, flex: 1, width: '100%' }}>
        {/* Title + metadata */}
        <div style={{ marginBottom: 24 }}>
          <div style={{ display: 'flex', alignItems: 'flex-start', gap: 12, marginBottom: 8 }}>
            <h1 style={{
              margin: 0, fontFamily: T.serif, fontSize: 28, lineHeight: 1.15,
              fontWeight: 400, color: T.fg, letterSpacing: '-0.4px', flex: 1,
            }}>{system.name}</h1>
            {system.status && <StatusBadge status={system.status} color={T.systemStatusColor(system.status)} />}
          </div>

          <div style={{
            display: 'flex', flexWrap: 'wrap', gap: 14, marginTop: 12, paddingTop: 12,
            borderTop: `1px solid ${T.borderDim}`,
          }}>
            {system.language && <KV label="Language" value={system.language} mono accent={T.languageColor(system.language)} />}
            {system.license && <KV label="License" value={system.license} mono />}
            {system.star_count != null && system.star_count > 0 && <KV label="Stars" value={system.star_count.toLocaleString()} mono accent="#dbb34a" />}
            <KV label="Artifacts" value={artifacts.length} mono />
            <KV label="Notes" value={notes.length} mono />
            {system.url && (
              <div style={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
                <span style={{ fontFamily: T.mono, fontSize: 9.5, letterSpacing: '1.2px', textTransform: 'uppercase', color: T.fgFaint }}>Links</span>
                <span style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
                  <a href={system.url} target="_blank" rel="noopener noreferrer" style={{ color: T.teal, textDecoration: 'none', fontSize: 12, display: 'flex', alignItems: 'center', gap: 4 }}>
                    <Icon name="external" size={12} /> Website
                  </a>
                  {system.github_url && (
                    <a href={system.github_url} target="_blank" rel="noopener noreferrer" style={{ color: T.teal, textDecoration: 'none', fontSize: 12, display: 'flex', alignItems: 'center', gap: 4 }}>
                      <Icon name="external" size={12} /> GitHub
                    </a>
                  )}
                </span>
              </div>
            )}
          </div>
        </div>

        {/* Two-column layout */}
        <div style={{ display: 'grid', gridTemplateColumns: '1.6fr 1fr', gap: 20, alignItems: 'start' }}>
          {/* Left: Notes */}
          <div>
            {notes.length > 0 ? (
              <Panel title={`Notes (${notes.length})`}>
                <div style={{ borderRadius: 4, border: `1px solid ${T.borderDim}`, overflow: 'hidden' }}>
                  {notes.map(note => <NoteItem key={note.id} note={note} />)}
                </div>
              </Panel>
            ) : (
              <Panel title="Notes">
                <p style={{ fontSize: 13, color: T.fgFaint, fontStyle: 'italic' }}>No notes yet.</p>
              </Panel>
            )}
          </div>

          {/* Right: Artifacts */}
          <div>
            {artifacts.length > 0 ? (
              <Panel title={`Artifacts (${artifacts.length})`}>
                <div style={{ borderRadius: 4, border: `1px solid ${T.borderDim}` }}>
                  {artifacts.map((art, i) => (
                    <div key={art.id} style={{
                      display: 'flex', alignItems: 'center', gap: 8,
                      padding: '8px 12px',
                      borderTop: i > 0 ? `1px solid ${T.borderDim}` : 'none',
                    }}>
                      <Icon name="globe" size={14} color={T.fgDim} />
                      <Link
                        href={`/tech-recon/artifact/${art.id}`}
                        style={{ flex: 1, fontSize: 12, color: T.fg, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', textDecoration: 'none' }}
                      >
                        {art.url || art.id}
                      </Link>
                      <span style={{
                        fontFamily: T.mono, fontSize: 10, padding: '1px 6px', borderRadius: 2,
                        border: `1px solid ${T.formatColor(art.format)}66`, color: T.formatColor(art.format),
                      }}>{art.format}</span>
                      {art.cache_path && (
                        <span style={{
                          fontFamily: T.mono, fontSize: 10, padding: '1px 6px', borderRadius: 2,
                          border: `1px solid ${T.teal}66`, color: T.teal,
                        }}>cached</span>
                      )}
                      {art.url && (
                        <a href={art.url} target="_blank" rel="noopener noreferrer" style={{ color: T.teal, flexShrink: 0 }}>
                          <Icon name="external" size={12} />
                        </a>
                      )}
                    </div>
                  ))}
                </div>
              </Panel>
            ) : (
              <Panel title="Artifacts">
                <p style={{ fontSize: 13, color: T.fgFaint, fontStyle: 'italic' }}>No artifacts yet.</p>
              </Panel>
            )}
          </div>
        </div>

        {artifacts.length === 0 && notes.length === 0 && (
          <div style={{ textAlign: 'center', padding: '32px 0' }}>
            <p style={{ fontSize: 13, color: T.fgFaint, fontStyle: 'italic' }}>
              No artifacts or notes yet. Use{' '}
              <code style={{ fontFamily: T.mono, fontSize: 11, background: T.bgSunken, padding: '2px 6px', borderRadius: 3 }}>tech-recon ingest</code>{' '}
              to start collecting data.
            </p>
          </div>
        )}
      </main>

      <footer style={{ borderTop: `1px solid ${T.borderDim}`, marginTop: 'auto', padding: '16px 24px' }}>
        <div style={{
          maxWidth: 1200, margin: '0 auto',
          display: 'flex', alignItems: 'center', gap: 10,
          fontFamily: T.mono, fontSize: 10, color: T.fgFaint, letterSpacing: '0.6px',
        }}>
          <span>system · {id}</span>
          <span>·</span>
          <span>shape: show-system --json</span>
        </div>
      </footer>
    </div>
  );
}
