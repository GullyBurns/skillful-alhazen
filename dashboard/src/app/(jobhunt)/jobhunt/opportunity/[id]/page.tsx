'use client';

import { useState, useEffect, use } from 'react';
import Link from 'next/link';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';

/* ── Starry Night palette ── */
const T = {
  bg: '#070d1c',
  bgRaised: '#0c1628',
  panel: 'rgba(12,22,40,0.72)',
  fg: '#c8dde8',
  fgDim: '#8ba4b8',
  fgFaint: '#5e7387',
  teal: '#5aadaf',
  blue: '#5b8ab8',
  olive: '#b8c84a',
  mint: '#62c4bc',
  rust: '#c87a4a',
  border: 'rgba(90,173,175,0.18)',
  borderDim: 'rgba(200,221,232,0.08)',
  mono: "'JetBrains Mono', monospace",
  serif: "'DM Serif Display', serif",
  sans: "'DM Sans', sans-serif",
};

/* ── Note type config ── */
const NOTE_TYPES: Record<string, { label: string; short: string; color: string }> = {
  'jhunt-application-note': { label: 'Application', short: 'APP', color: '#5aadaf' },
  'jhunt-research-note': { label: 'Research', short: 'RES', color: '#8ba4b8' },
  'jhunt-fit-analysis-note': { label: 'Fit analysis', short: 'FIT', color: '#62c4bc' },
  'jhunt-interview-note': { label: 'Interview', short: 'INT', color: '#5b8ab8' },
  'jhunt-interaction-note': { label: 'Interaction', short: 'TALK', color: '#5b8ab8' },
  'jhunt-strategy-note': { label: 'Strategy', short: 'STRAT', color: '#8ba4b8' },
  'jhunt-skill-gap-note': { label: 'Skill gap', short: 'GAP', color: '#c87a4a' },
  'jhunt-opp-summary-note': { label: 'Summary', short: 'SUM', color: '#b8c84a' },
  'jhunt-cc-brief-note': { label: 'CC brief', short: 'BRIEF', color: '#b8c84a' },
  'jhunt-cc-feedback-note': { label: 'Feedback', short: 'FEEDBACK', color: '#c87a4a' },
};

/* ── Kind config ── */
const KINDS: Record<string, { label: string; short: string; color: string; showRequirements: boolean }> = {
  'jhunt-position': { label: 'Position', short: 'POS', color: '#5aadaf', showRequirements: true },
  'jhunt-engagement': { label: 'Engagement', short: 'ENG', color: '#5b8ab8', showRequirements: false },
  'jhunt-venture': { label: 'Venture', short: 'VEN', color: '#b8c84a', showRequirements: false },
  'jhunt-lead': { label: 'Lead', short: 'LED', color: '#62c4bc', showRequirements: false },
};

const LEVEL_COLORS: Record<string, string> = {
  strong: '#62c4bc',
  some: '#b8c84a',
  learning: '#c87a4a',
  none: '#5e7387',
};

function noteTypeMeta(type: string | undefined | null) {
  if (!type) return { label: 'note', short: '?', color: T.fgDim };
  return NOTE_TYPES[type] || { label: type.replace(/^jhunt-/, '').replace(/-note$/, ''), short: '?', color: T.fgDim };
}

function kindMeta(type: string) {
  return KINDS[type] || KINDS['jhunt-lead'];
}

function initials(name: string): string {
  return name.split(/\s+/).map(w => w[0]).join('').toUpperCase().slice(0, 2);
}

/* ── Component ── */

interface OpportunityPageProps {
  params: Promise<{ id: string }>;
}

export default function OpportunityDossierPage({ params }: OpportunityPageProps) {
  const { id } = use(params);
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const [data, setData] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [activeFilter, setActiveFilter] = useState<string | null>(null);

  useEffect(() => {
    async function load() {
      setLoading(true);
      setError(null);
      try {
        const res = await fetch(`/api/jobhunt/opportunity/${id}`);
        if (!res.ok) throw new Error('Failed to fetch opportunity');
        const json = await res.json();
        if (!json.success) throw new Error('API returned failure');
        setData(json);
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Unknown error');
      } finally {
        setLoading(false);
      }
    }
    load();
  }, [id]);

  /* ── Loading ── */
  if (loading) {
    return (
      <div style={{ minHeight: '100vh', background: T.bg, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
        <span style={{ fontFamily: T.mono, fontSize: 14, color: T.fgDim }}>Loading...</span>
      </div>
    );
  }

  /* ── Error ── */
  if (error || !data) {
    return (
      <div style={{ minHeight: '100vh', background: T.bg, padding: 40 }}>
        <Link href="/jobhunt" style={{ fontFamily: T.mono, fontSize: 13, color: T.teal, textDecoration: 'none' }}>
          &larr; mission control
        </Link>
        <div style={{ marginTop: 24, padding: '14px 20px', background: 'rgba(200,122,74,0.12)', border: `1px solid ${T.rust}`, borderRadius: 6, color: T.rust, fontFamily: T.sans, fontSize: 14 }}>
          {error || 'Opportunity not found'}
        </div>
      </div>
    );
  }

  const opp = data.opportunity || {};
  const company = data.company || {};
  const notes: any[] = data.notes || [];
  const requirements: any[] = data.requirements || [];
  const contacts: any[] = data.contacts || [];
  const tags: string[] = data.tags || [];
  const backgroundReading: any[] = data.background_reading || [];
  const kind = kindMeta(data.type || '');

  /* Extract summary note (shown at top, excluded from timeline) */
  const summaryNote = notes.find((n: any) => n.type === 'jhunt-opp-summary-note');
  const timelineNotes = notes.filter((n: any) => n.type !== 'jhunt-opp-summary-note');

  /* Note type filter chips */
  const noteTypesPresent = [...new Set(timelineNotes.map((n: any) => n.type as string))];
  const filteredNotes = activeFilter ? timelineNotes.filter((n: any) => n.type === activeFilter) : timelineNotes;
  const sortedNotes = [...filteredNotes].sort((a: any, b: any) => {
    const da = a['created-at'] || '';
    const db = b['created-at'] || '';
    return db.localeCompare(da);
  });

  /* ── KV row helper ── */
  const kvPairs: { label: string; value: string | null | undefined }[] = [
    { label: 'Status', value: opp['jhunt-opportunity-status'] },
    { label: 'Priority', value: opp['jhunt-priority-level'] },
    { label: 'Deadline', value: opp['deadline'] },
    { label: 'Salary', value: opp['jhunt-salary-range'] },
    { label: 'Location', value: opp['location'] },
    { label: 'Remote', value: opp['jhunt-remote-policy'] },
  ].filter(kv => kv.value);

  return (
    <div style={{ minHeight: '100vh', background: T.bg, color: T.fg, fontFamily: T.sans }}>
      {/* ── Back nav ── */}
      <div style={{ padding: '14px 28px', borderBottom: `1px solid ${T.borderDim}` }}>
        <Link href="/jobhunt" style={{ fontFamily: T.mono, fontSize: 13, color: T.teal, textDecoration: 'none' }}>
          &larr; mission control
        </Link>
      </div>

      {/* ── Header strip ── */}
      <div style={{ background: T.bgRaised, padding: '28px 28px 22px', borderBottom: `1px solid ${T.border}` }}>
        {/* Kind badge */}
        <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 8 }}>
          <span style={{
            fontFamily: T.mono,
            fontSize: 11,
            fontWeight: 700,
            letterSpacing: 1.2,
            color: kind.color,
            border: `1px solid ${kind.color}`,
            borderRadius: 4,
            padding: '2px 8px',
          }}>
            {kind.short}
          </span>
          {company.name && (
            <span style={{ fontFamily: T.mono, fontSize: 13, color: T.fgDim }}>{company.name}</span>
          )}
        </div>

        {/* Title */}
        <h1 style={{ fontFamily: T.serif, fontSize: 28, fontWeight: 400, color: T.fg, margin: '4px 0 0' }}>
          {opp.name || 'Untitled'}
        </h1>

        {/* Description */}
        {opp.description && (
          <p style={{ fontSize: 13.5, color: T.fgDim, margin: '8px 0 0', lineHeight: 1.55, maxWidth: 720 }}>
            {opp.description}
          </p>
        )}

        {/* Status row */}
        {kvPairs.length > 0 && (
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: 20, marginTop: 16 }}>
            {kvPairs.map(kv => (
              <div key={kv.label} style={{ display: 'flex', alignItems: 'baseline', gap: 6 }}>
                <span style={{ fontFamily: T.mono, fontSize: 11, color: T.fgFaint, textTransform: 'uppercase', letterSpacing: 0.8 }}>
                  {kv.label}
                </span>
                <span style={{ fontFamily: T.sans, fontSize: 13, color: T.fg }}>{kv.value}</span>
              </div>
            ))}
          </div>
        )}

        {/* Tags */}
        {tags.length > 0 && (
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6, marginTop: 14 }}>
            {tags.map(tag => (
              <span key={tag} style={{
                fontFamily: T.mono,
                fontSize: 11,
                color: T.fgDim,
                border: `1px solid ${T.borderDim}`,
                borderRadius: 10,
                padding: '2px 10px',
              }}>
                {tag}
              </span>
            ))}
          </div>
        )}

        {/* Job URL */}
        {opp['jhunt-job-url'] && (
          <div style={{ marginTop: 12 }}>
            <a
              href={opp['jhunt-job-url']}
              target="_blank"
              rel="noopener noreferrer"
              style={{ fontFamily: T.mono, fontSize: 12, color: T.teal, textDecoration: 'underline', textUnderlineOffset: 3 }}
            >
              View job posting &rarr;
            </a>
          </div>
        )}
      </div>

      {/* ── Summary dossier ── */}
      {summaryNote?.content && (
        <div style={{ padding: '20px 28px 0' }}>
          <div style={{
            background: T.panel,
            border: `1px solid ${T.olive}33`,
            borderRadius: 8,
            padding: 20,
          }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 12 }}>
              <span style={{
                fontFamily: T.mono,
                fontSize: 10,
                fontWeight: 700,
                letterSpacing: 1,
                color: T.olive,
                background: `${T.olive}18`,
                borderRadius: 3,
                padding: '1px 6px',
              }}>
                SUM
              </span>
              <h2 style={{ fontFamily: T.serif, fontSize: 18, color: T.fg, margin: 0 }}>Summary</h2>
              {summaryNote['created-at'] && (
                <span style={{ fontFamily: T.mono, fontSize: 10, color: T.fgFaint, marginLeft: 'auto' }}>
                  updated {summaryNote['created-at']}
                </span>
              )}
            </div>
            <div style={{ fontSize: 13.5, color: T.fgDim, lineHeight: 1.65 }}>
              <ReactMarkdown
                remarkPlugins={[remarkGfm]}
                components={{
                  p: ({ children }) => <p style={{ margin: '4px 0' }}>{children}</p>,
                  h2: ({ children }) => <h2 style={{ fontSize: 15, fontWeight: 700, color: T.fg, margin: '14px 0 4px' }}>{children}</h2>,
                  h3: ({ children }) => <h3 style={{ fontSize: 14, fontWeight: 600, color: T.fg, margin: '10px 0 4px' }}>{children}</h3>,
                  ul: ({ children }) => <ul style={{ paddingLeft: 18, margin: '4px 0' }}>{children}</ul>,
                  li: ({ children }) => <li style={{ margin: '2px 0' }}>{children}</li>,
                  a: ({ href, children }) => <a href={href} target="_blank" rel="noopener noreferrer" style={{ color: T.teal, textDecoration: 'underline', textUnderlineOffset: 3 }}>{children}</a>,
                  strong: ({ children }) => <strong style={{ color: T.fg }}>{children}</strong>,
                }}
              >
                {summaryNote.content}
              </ReactMarkdown>
            </div>
          </div>
        </div>
      )}

      {/* ── Two-column layout ── */}
      <div style={{ display: 'grid', gridTemplateColumns: '1.6fr 1fr', gap: 24, padding: '24px 28px 48px', alignItems: 'start' }}>
        {/* ── Left column: Timeline ── */}
        <div>
          <div style={{ background: T.panel, border: `1px solid ${T.border}`, borderRadius: 8, padding: 20 }}>
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 16 }}>
              <h2 style={{ fontFamily: T.serif, fontSize: 18, color: T.fg, margin: 0 }}>Timeline</h2>
              <span style={{ fontFamily: T.mono, fontSize: 11, color: T.fgFaint }}>{timelineNotes.length} note{timelineNotes.length !== 1 ? 's' : ''}</span>
            </div>

            {/* Filter chips */}
            {noteTypesPresent.length > 1 && (
              <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6, marginBottom: 16 }}>
                <button
                  onClick={() => setActiveFilter(null)}
                  style={{
                    fontFamily: T.mono,
                    fontSize: 11,
                    color: activeFilter === null ? T.bg : T.fgDim,
                    background: activeFilter === null ? T.teal : 'transparent',
                    border: `1px solid ${activeFilter === null ? T.teal : T.borderDim}`,
                    borderRadius: 10,
                    padding: '3px 10px',
                    cursor: 'pointer',
                  }}
                >
                  ALL
                </button>
                {noteTypesPresent.map(nt => {
                  const m = noteTypeMeta(nt);
                  const active = activeFilter === nt;
                  return (
                    <button
                      key={nt}
                      onClick={() => setActiveFilter(active ? null : nt)}
                      style={{
                        fontFamily: T.mono,
                        fontSize: 11,
                        color: active ? T.bg : m.color,
                        background: active ? m.color : 'transparent',
                        border: `1px solid ${active ? m.color : T.borderDim}`,
                        borderRadius: 10,
                        padding: '3px 10px',
                        cursor: 'pointer',
                      }}
                    >
                      {m.short}
                    </button>
                  );
                })}
              </div>
            )}

            {/* Notes list */}
            {sortedNotes.length === 0 && (
              <p style={{ fontFamily: T.sans, fontSize: 13, color: T.fgFaint, textAlign: 'center', padding: 20 }}>
                No notes yet.
              </p>
            )}
            {sortedNotes.map((note: any, idx: number) => {
              const m = noteTypeMeta(note.type);
              return (
                <div key={note.id || idx} style={{
                  position: 'relative',
                  paddingLeft: 24,
                  paddingBottom: idx < sortedNotes.length - 1 ? 20 : 0,
                  borderLeft: idx < sortedNotes.length - 1 ? `1px solid ${T.borderDim}` : 'none',
                  marginLeft: 6,
                }}>
                  {/* Dot */}
                  <div style={{
                    position: 'absolute',
                    left: -5,
                    top: 4,
                    width: 10,
                    height: 10,
                    borderRadius: '50%',
                    background: m.color,
                    border: `2px solid ${T.bg}`,
                  }} />

                  {/* Type badge + name */}
                  <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 4 }}>
                    <span style={{
                      fontFamily: T.mono,
                      fontSize: 10,
                      fontWeight: 700,
                      letterSpacing: 1,
                      color: m.color,
                      background: `${m.color}18`,
                      borderRadius: 3,
                      padding: '1px 6px',
                    }}>
                      {m.short}
                    </span>
                    {note.name && (
                      <span style={{ fontFamily: T.sans, fontSize: 13, fontWeight: 600, color: T.fg }}>
                        {note.name}
                      </span>
                    )}
                    {note['created-at'] && (
                      <span style={{ fontFamily: T.mono, fontSize: 10, color: T.fgFaint, marginLeft: 'auto' }}>
                        {note['created-at']}
                      </span>
                    )}
                  </div>

                  {/* Type-specific extras */}
                  <div style={{ display: 'flex', gap: 12, flexWrap: 'wrap', marginBottom: note.content ? 6 : 0 }}>
                    {note['jhunt-fit-score'] != null && (
                      <span style={{ fontFamily: T.mono, fontSize: 11, color: T.mint }}>
                        fit: {typeof note['jhunt-fit-score'] === 'number' ? (note['jhunt-fit-score'] * 100).toFixed(0) + '%' : note['jhunt-fit-score']}
                      </span>
                    )}
                    {note['contact_name'] && (
                      <span style={{ fontFamily: T.mono, fontSize: 11, color: T.blue }}>
                        contact: {note['contact_name']}
                      </span>
                    )}
                    {note['application_status'] && (
                      <span style={{ fontFamily: T.mono, fontSize: 11, color: T.olive }}>
                        status: {note['application_status']}
                      </span>
                    )}
                  </div>

                  {/* Content */}
                  {note.content && (
                    <div style={{ fontSize: 13, color: T.fgDim, lineHeight: 1.6 }}>
                      <ReactMarkdown
                        remarkPlugins={[remarkGfm]}
                        components={{
                          p: ({ children }) => <p style={{ margin: '4px 0' }}>{children}</p>,
                          h1: ({ children }) => <h1 style={{ fontSize: 16, fontWeight: 700, color: T.fg, margin: '12px 0 4px' }}>{children}</h1>,
                          h2: ({ children }) => <h2 style={{ fontSize: 15, fontWeight: 700, color: T.fg, margin: '10px 0 4px' }}>{children}</h2>,
                          h3: ({ children }) => <h3 style={{ fontSize: 14, fontWeight: 600, color: T.fg, margin: '8px 0 4px' }}>{children}</h3>,
                          ul: ({ children }) => <ul style={{ paddingLeft: 18, margin: '4px 0' }}>{children}</ul>,
                          ol: ({ children }) => <ol style={{ paddingLeft: 18, margin: '4px 0' }}>{children}</ol>,
                          li: ({ children }) => <li style={{ margin: '2px 0' }}>{children}</li>,
                          a: ({ href, children }) => <a href={href} target="_blank" rel="noopener noreferrer" style={{ color: T.teal, textDecoration: 'underline', textUnderlineOffset: 3 }}>{children}</a>,
                          code: ({ children }) => <code style={{ fontFamily: T.mono, fontSize: 12, background: T.bgRaised, padding: '1px 5px', borderRadius: 3, color: T.olive }}>{children}</code>,
                          blockquote: ({ children }) => <blockquote style={{ borderLeft: `3px solid ${T.border}`, paddingLeft: 12, margin: '8px 0', color: T.fgFaint }}>{children}</blockquote>,
                          table: ({ children }) => <table style={{ borderCollapse: 'collapse', fontSize: 12, margin: '8px 0', width: '100%' }}>{children}</table>,
                          th: ({ children }) => <th style={{ border: `1px solid ${T.border}`, padding: '4px 8px', textAlign: 'left', fontFamily: T.mono, fontSize: 11, color: T.fgFaint }}>{children}</th>,
                          td: ({ children }) => <td style={{ border: `1px solid ${T.borderDim}`, padding: '4px 8px' }}>{children}</td>,
                        }}
                      >
                        {note.content}
                      </ReactMarkdown>
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        </div>

        {/* ── Right column ── */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
          {/* Contacts */}
          {contacts.length > 0 && (
            <div style={{ background: T.panel, border: `1px solid ${T.border}`, borderRadius: 8, padding: 20 }}>
              <h3 style={{ fontFamily: T.serif, fontSize: 16, color: T.fg, margin: '0 0 14px' }}>Contacts</h3>
              <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
                {contacts.map((c: any, idx: number) => (
                  <div key={c.id || idx} style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
                    {/* Initials avatar */}
                    <div style={{
                      width: 36,
                      height: 36,
                      borderRadius: '50%',
                      background: T.bgRaised,
                      border: `1px solid ${T.border}`,
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'center',
                      fontFamily: T.mono,
                      fontSize: 12,
                      fontWeight: 700,
                      color: T.teal,
                      flexShrink: 0,
                    }}>
                      {initials(c.name || '??')}
                    </div>
                    <div>
                      <div style={{ fontFamily: T.sans, fontSize: 13, fontWeight: 600, color: T.fg }}>
                        {c.name || 'Unknown'}
                      </div>
                      {c['jhunt-contact-role'] && (
                        <span style={{
                          fontFamily: T.mono,
                          fontSize: 10,
                          letterSpacing: 0.8,
                          color: T.blue,
                          background: `${T.blue}18`,
                          borderRadius: 3,
                          padding: '1px 6px',
                          textTransform: 'uppercase',
                        }}>
                          {c['jhunt-contact-role']}
                        </span>
                      )}
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Requirements (position only) */}
          {kind.showRequirements && requirements.length > 0 && (
            <div style={{ background: T.panel, border: `1px solid ${T.border}`, borderRadius: 8, padding: 20 }}>
              <h3 style={{ fontFamily: T.serif, fontSize: 16, color: T.fg, margin: '0 0 14px' }}>Requirements</h3>
              {/* Header row */}
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 80px 80px', gap: 4, marginBottom: 6 }}>
                <span style={{ fontFamily: T.mono, fontSize: 10, color: T.fgFaint, textTransform: 'uppercase', letterSpacing: 0.8 }}>Skill</span>
                <span style={{ fontFamily: T.mono, fontSize: 10, color: T.fgFaint, textTransform: 'uppercase', letterSpacing: 0.8 }}>Level</span>
                <span style={{ fontFamily: T.mono, fontSize: 10, color: T.fgFaint, textTransform: 'uppercase', letterSpacing: 0.8 }}>Yours</span>
              </div>
              {requirements.map((r: any, idx: number) => {
                const yourColor = LEVEL_COLORS[(r['jhunt-your-level'] || '').toLowerCase()] || T.fgFaint;
                return (
                  <div key={r.id || idx} style={{
                    display: 'grid',
                    gridTemplateColumns: '1fr 80px 80px',
                    gap: 4,
                    padding: '5px 0',
                    borderTop: idx > 0 ? `1px solid ${T.borderDim}` : 'none',
                  }}>
                    <span style={{ fontFamily: T.sans, fontSize: 13, color: T.fg }}>{r['slog-skill-name']}</span>
                    <span style={{ fontFamily: T.mono, fontSize: 11, color: T.fgDim }}>{r['jhunt-skill-level']}</span>
                    <span style={{ fontFamily: T.mono, fontSize: 11, color: yourColor, fontWeight: 600 }}>{r['jhunt-your-level'] || '-'}</span>
                  </div>
                );
              })}
            </div>
          )}

          {/* Background reading */}
          {backgroundReading.length > 0 && (
            <div style={{ background: T.panel, border: `1px solid ${T.border}`, borderRadius: 8, padding: 20 }}>
              <h3 style={{ fontFamily: T.serif, fontSize: 16, color: T.fg, margin: '0 0 14px' }}>Background Reading</h3>
              <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
                {backgroundReading.map((col: any, idx: number) => (
                  <div key={col['collection-id'] || idx} style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                    <span style={{ fontSize: 14 }}>&#128214;</span>
                    <Link
                      href={`/jobhunt/collection/${col['collection-id']}`}
                      style={{
                        fontFamily: T.sans,
                        fontSize: 13,
                        color: T.teal,
                        fontWeight: 600,
                        textDecoration: 'underline',
                        textUnderlineOffset: 3,
                      }}
                    >
                      {col['collection-name']}
                    </Link>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
