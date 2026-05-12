'use client';

import { useState, useEffect, use } from 'react';
import Link from 'next/link';
import { T } from '@/components/tech-recon/tokens';
import {
  Icon, Panel, KV, BackNav, HeaderStrip, StatusBadge, TypeChip,
  FilterChip, MarkdownContent, SectionNav, GroupHeader,
  type SectionKey, type StageCompletion, type SectionNavItem,
  DEFAULT_SECTION_ICONS,
} from '@/components/tech-recon/atoms';
import { ReportContent } from '@/components/tech-recon/report-content';
import type {
  Investigation, TechReconSystem, TechReconNote, TechReconAnalysis,
  TechReconArtifact, SystemData,
} from '@/lib/tech-recon';

// ─── Scope Section ─────────────────────────────────────────────

function ScopeSection({ investigation }: { investigation: Investigation }) {
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
      <Panel
        title="Goal"
        borderColor={`${T.teal}55`}
        bgColor="rgba(90,173,175,0.04)"
      >
        {investigation.goal ? (
          <MarkdownContent content={investigation.goal} />
        ) : (
          <p style={{ fontSize: 13, color: T.fgFaint, fontStyle: 'italic' }}>No goal defined.</p>
        )}
      </Panel>

      <Panel
        title="Success Criteria"
        borderColor={`${T.olive}55`}
        bgColor="rgba(184,200,74,0.04)"
      >
        {investigation.criteria ? (
          <MarkdownContent content={investigation.criteria} />
        ) : (
          <p style={{ fontSize: 13, color: T.fgFaint, fontStyle: 'italic' }}>No criteria defined.</p>
        )}
      </Panel>
    </div>
  );
}

// ─── Discovery Section (Systems Table) ─────────────────────────

const TRACKED_TOPICS = ['architecture', 'api', 'data-model', 'assessment', 'context-storage', 'integration'];

function DiscoverySection({ systems, systemDataMap }: { systems: TechReconSystem[]; systemDataMap: Record<string, SystemData> }) {
  const topicsBySys: Record<string, Set<string>> = {};
  systems.forEach(s => {
    const notes = systemDataMap[s.id]?.notes ?? [];
    topicsBySys[s.id] = new Set(notes.map(n => n.topic?.toLowerCase()).filter(Boolean) as string[]);
  });

  const presentTopics = TRACKED_TOPICS.filter(t =>
    systems.some(s => topicsBySys[s.id]?.has(t))
  );

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
      <h2 style={{
        fontFamily: T.mono, fontSize: 10.5, fontWeight: 600, textTransform: 'uppercase',
        letterSpacing: '1px', color: T.fgDim, margin: 0,
      }}>Systems under investigation ({systems.length})</h2>

      <div style={{ overflowX: 'auto', borderRadius: 4, border: `1px solid ${T.borderDim}` }}>
        <table style={{ width: '100%', fontSize: 13, borderCollapse: 'collapse' }}>
          <thead>
            <tr style={{ borderBottom: `1px solid ${T.borderDim}`, background: T.bgSunken }}>
              <th style={thStyle}>Name</th>
              <th style={thStyle}>Language</th>
              <th style={{ ...thStyle, textAlign: 'center' }}>Artifacts</th>
              {presentTopics.map(t => (
                <th key={t} style={{ ...thStyle, textAlign: 'center', whiteSpace: 'nowrap' }}>
                  {t.replace(/-/g, ' ')}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {systems.map((s, idx) => {
              const topics = topicsBySys[s.id] ?? new Set();
              const isShallow = (s.artifacts_count ?? 0) < 3 && (s.artifacts_count ?? 0) > 0;
              return (
                <tr key={s.id} style={{
                  borderBottom: idx < systems.length - 1 ? `1px solid ${T.borderDim}` : 'none',
                  background: idx % 2 === 1 ? 'rgba(12,22,40,0.3)' : 'transparent',
                }}>
                  <td style={tdStyle}>
                    <Link href={`/tech-recon/system/${s.id}`} style={{ color: T.teal, textDecoration: 'none', fontWeight: 500 }}>
                      {s.name}
                    </Link>
                  </td>
                  <td style={tdStyle}>
                    {s.language && (
                      <span style={{
                        fontFamily: T.mono, fontSize: 10, letterSpacing: '0.4px',
                        padding: '2px 6px', borderRadius: 2,
                        border: `1px solid ${T.borderDim}`, color: T.languageColor(s.language),
                      }}>{s.language}</span>
                    )}
                  </td>
                  <td style={{ ...tdStyle, textAlign: 'center' }}>
                    <span style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 6 }}>
                      <span style={{ color: isShallow ? T.olive : T.fg }}>{s.artifacts_count ?? 0}</span>
                      {s.url && (
                        <a href={s.url} target="_blank" rel="noopener noreferrer" style={{ color: T.teal }}>
                          <Icon name="external" size={12} />
                        </a>
                      )}
                    </span>
                  </td>
                  {presentTopics.map(t => (
                    <td key={t} style={{ ...tdStyle, textAlign: 'center' }}>
                      {topics.has(t) && <Icon name="check" size={14} color={T.teal} />}
                    </td>
                  ))}
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}

const thStyle: React.CSSProperties = {
  textAlign: 'left',
  padding: '8px 12px',
  fontFamily: T.mono,
  fontSize: 9.5,
  fontWeight: 600,
  color: T.fgFaint,
  textTransform: 'uppercase',
  letterSpacing: '1px',
};

const tdStyle: React.CSSProperties = {
  padding: '8px 12px',
  color: T.fg,
};

// ─── Sensemaking Section ───────────────────────────────────────

function SensemakingSection({
  systems, systemDataMap, selectedIteration,
}: {
  systems: TechReconSystem[];
  systemDataMap: Record<string, SystemData>;
  selectedIteration?: number;
}) {
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const selected = systems.find(s => s.id === selectedId);
  const rawData = selectedId ? (systemDataMap[selectedId] ?? { artifacts: [], notes: [] }) : null;
  const selectedData = rawData && selectedIteration !== undefined
    ? { ...rawData, notes: rawData.notes.filter(n => (n.iteration_number ?? 1) === selectedIteration) }
    : rawData;

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
      <h2 style={{
        fontFamily: T.mono, fontSize: 10.5, fontWeight: 600, textTransform: 'uppercase',
        letterSpacing: '1px', color: T.fgDim, margin: 0,
      }}>Ingestion &amp; Sensemaking — {systems.length} systems</h2>

      {/* System buttons */}
      <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8 }}>
        {systems.map(s => {
          const isActive = s.id === selectedId;
          return (
            <button
              key={s.id}
              onClick={() => setSelectedId(isActive ? null : s.id)}
              style={{
                padding: '6px 12px',
                borderRadius: 4,
                border: `1px solid ${isActive ? `${T.teal}66` : T.borderDim}`,
                background: 'transparent',
                color: isActive ? T.teal : T.fgDim,
                fontWeight: isActive ? 600 : 400,
                fontSize: 13,
                fontFamily: T.sans,
                cursor: 'pointer',
                transition: 'all 0.12s',
              }}
            >
              {s.name}
              <span style={{ fontFamily: T.mono, fontSize: 10.5, color: T.fgFaint, marginLeft: 6 }}>
                — {s.artifacts_count ?? 0}a/{s.notes_count ?? 0}n
              </span>
            </button>
          );
        })}
      </div>

      {/* Detail panel */}
      {selected && selectedData && (
        <Panel
          title={selected.name}
          borderColor={`${T.teal}55`}
          action={
            <button
              onClick={() => setSelectedId(null)}
              style={{
                background: 'transparent', border: 'none', cursor: 'pointer',
                fontFamily: T.mono, fontSize: 10.5, color: T.fgFaint,
              }}
            >x close</button>
          }
        >
          {/* Artifacts */}
          {selectedData.artifacts.length > 0 && (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
              <span style={{
                fontFamily: T.mono, fontSize: 10.5, fontWeight: 600, textTransform: 'uppercase',
                letterSpacing: '1px', color: T.fgDim,
              }}>Artifacts ({selectedData.artifacts.length})</span>
              <div style={{ borderRadius: 4, border: `1px solid ${T.borderDim}` }}>
                {selectedData.artifacts.map((art, i) => (
                  <div key={art.id} style={{
                    display: 'flex', alignItems: 'center', gap: 8,
                    padding: '8px 12px',
                    borderTop: i > 0 ? `1px solid ${T.borderDim}` : 'none',
                  }}>
                    <Icon name="globe" size={14} color={T.fgDim} />
                    <span style={{ flex: 1, fontSize: 12, color: T.fg, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                      {art.url || art.id}
                    </span>
                    <span style={{
                      fontFamily: T.mono, fontSize: 10, padding: '1px 6px', borderRadius: 2,
                      border: `1px solid ${T.formatColor(art.format)}66`,
                      color: T.formatColor(art.format),
                    }}>{art.format}</span>
                    {art.cache_path && (
                      <span style={{
                        fontFamily: T.mono, fontSize: 10, padding: '1px 6px', borderRadius: 2,
                        border: `1px solid ${T.teal}66`, color: T.teal,
                      }}>cached</span>
                    )}
                    {art.url && (
                      <a href={art.url} target="_blank" rel="noopener noreferrer" style={{ color: T.teal }}>
                        <Icon name="external" size={12} />
                      </a>
                    )}
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Notes */}
          {selectedData.notes.length > 0 && (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
              <span style={{
                fontFamily: T.mono, fontSize: 10.5, fontWeight: 600, textTransform: 'uppercase',
                letterSpacing: '1px', color: T.fgDim,
              }}>Sensemaking Notes ({selectedData.notes.length})</span>
              <NotesList notes={selectedData.notes} />
            </div>
          )}

          {selectedData.artifacts.length === 0 && selectedData.notes.length === 0 && (
            <p style={{ fontSize: 13, color: T.fgFaint, fontStyle: 'italic' }}>No artifacts or notes ingested yet.</p>
          )}
        </Panel>
      )}
    </div>
  );
}

// ─── Notes list with expandable items ──────────────────────────

function NotesList({ notes }: { notes: TechReconNote[] }) {
  return (
    <div style={{ borderRadius: 4, border: `1px solid ${T.borderDim}`, overflow: 'hidden' }}>
      {notes.map(note => <NoteItem key={note.id} note={note} />)}
    </div>
  );
}

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
          transition: 'background 0.12s',
        }}
        onMouseEnter={e => { e.currentTarget.style.background = 'rgba(12,22,40,0.5)'; }}
        onMouseLeave={e => { e.currentTarget.style.background = 'transparent'; }}
      >
        <Icon name={open ? 'chevron-down' : 'chevron-right'} size={14} color={T.fgFaint} />
        <Icon name={topicCfg.icon} size={14} color={topicCfg.color} />
        {note.topic && (
          <span style={{
            fontFamily: T.mono, fontSize: 10, letterSpacing: '0.4px',
            padding: '1px 6px', borderRadius: 2,
            border: `1px solid ${T.borderDim}`, color: T.fgDim,
          }}>{note.topic}</span>
        )}
        <span style={{
          fontFamily: T.mono, fontSize: 10, padding: '1px 6px', borderRadius: 2,
          border: `1px solid ${T.formatColor(note.format)}66`,
          color: T.formatColor(note.format),
        }}>{note.format}</span>
        <span style={{ flex: 1, fontSize: 12, color: T.fgDim, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
          {firstLine}
        </span>
      </button>
      {open && (
        <div style={{
          padding: '12px 16px',
          borderTop: `1px solid ${T.borderDim}`,
          background: T.bgSunken,
        }}>
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

// ─── Analysis Section ──────────────────────────────────────────

function AnalysisSection({
  analyses, vizPlanNotes, investigationId,
}: {
  analyses: TechReconAnalysis[];
  vizPlanNotes: TechReconNote[];
  investigationId: string;
}) {
  const hasAnalyses = analyses.length > 0;
  const hasVizPlan = vizPlanNotes.length > 0;

  if (!hasAnalyses && !hasVizPlan) {
    return (
      <div style={{
        border: `1px solid ${T.borderDim}`, borderRadius: 4,
        background: T.bgSunken, padding: '32px 24px', textAlign: 'center',
      }}>
        <p style={{ fontSize: 13, color: T.fgDim }}>No visualization plan or analyses yet.</p>
        <pre style={{
          display: 'inline-block', textAlign: 'left', fontFamily: T.mono, fontSize: 12,
          background: T.panel, borderRadius: 4, padding: '8px 16px', marginTop: 12,
          color: T.fgDim,
        }}>
          {`uv run python .claude/skills/tech-recon/tech_recon.py plan-analyses --investigation ${investigationId}`}
        </pre>
      </div>
    );
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 24 }}>
      <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
        <h3 style={{
          fontFamily: T.mono, fontSize: 10.5, fontWeight: 600, textTransform: 'uppercase',
          letterSpacing: '1px', color: T.fgDim, margin: 0,
        }}>Analyses ({analyses.length})</h3>

        {hasAnalyses ? (
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(280px, 1fr))', gap: 14 }}>
            {analyses.map(analysis => {
              const typeColor = T.analysisTypeColor(analysis.type);
              return (
                <div key={analysis.id} style={{
                  background: T.panel, border: `1px solid ${T.borderDim}`,
                  borderRadius: 4, padding: 16, display: 'flex', flexDirection: 'column', gap: 10,
                }}>
                  <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', gap: 8 }}>
                    <Link
                      href={`/tech-recon/investigation/${investigationId}/analysis/${analysis.id}`}
                      style={{ color: T.teal, textDecoration: 'underline', textUnderlineOffset: '2px', fontSize: 13, fontWeight: 600, lineHeight: 1.3 }}
                    >
                      {analysis.title}
                    </Link>
                    <span style={{
                      fontFamily: T.mono, fontSize: 10, letterSpacing: '0.4px', textTransform: 'uppercase',
                      padding: '1px 6px', borderRadius: 2, flexShrink: 0,
                      border: `1px solid ${typeColor}66`, color: typeColor,
                    }}>{analysis.type}</span>
                  </div>
                  {analysis.description && (
                    <p style={{ fontSize: 12, color: T.fgDim, margin: 0, lineHeight: 1.5, display: '-webkit-box', WebkitLineClamp: 2, WebkitBoxOrient: 'vertical', overflow: 'hidden' }}>
                      {analysis.description}
                    </p>
                  )}
                  <Link
                    href={`/tech-recon/investigation/${investigationId}/analysis/${analysis.id}`}
                    style={{
                      fontFamily: T.mono, fontSize: 11, color: T.fgDim,
                      textAlign: 'center', padding: '6px 0',
                      border: `1px solid ${T.borderDim}`, borderRadius: 3,
                      textDecoration: 'none', display: 'block',
                      transition: 'all 0.12s',
                    }}
                    onMouseEnter={e => {
                      e.currentTarget.style.borderColor = `${T.teal}66`;
                      e.currentTarget.style.color = T.teal;
                    }}
                    onMouseLeave={e => {
                      e.currentTarget.style.borderColor = T.borderDim;
                      e.currentTarget.style.color = T.fgDim;
                    }}
                  >
                    Run Analysis →
                  </Link>
                </div>
              );
            })}
          </div>
        ) : (
          <p style={{ fontSize: 13, color: T.fgFaint, fontStyle: 'italic' }}>
            No analyses planned yet.
          </p>
        )}
      </div>

      {hasVizPlan && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
          <h4 style={{
            fontFamily: T.mono, fontSize: 10.5, fontWeight: 600, textTransform: 'uppercase',
            letterSpacing: '1px', color: T.fgDim, margin: 0,
          }}>Visualization Plan</h4>
          {vizPlanNotes.map(note => (
            <pre key={note.id} style={{
              fontFamily: T.mono, fontSize: 12, background: T.bgSunken,
              border: `1px solid ${T.borderDim}`, borderRadius: 4,
              padding: 16, overflowX: 'auto', whiteSpace: 'pre-wrap', color: T.fg,
            }}><code>{note.content ?? note.content_preview ?? '(no content)'}</code></pre>
          ))}
        </div>
      )}
    </div>
  );
}

// ─── Outputs Section ───────────────────────────────────────────

const SPECIAL_TOPICS = new Set(['viz-plan', 'synthesis-report', 'completion-assessment']);

function OutputsSection({
  synthesisNote, completionNote, investigationId, notes = [],
}: {
  synthesisNote: TechReconNote | null;
  completionNote: TechReconNote | null;
  investigationId: string;
  notes?: TechReconNote[];
}) {
  const investigationNotes = notes.filter(n => !SPECIAL_TOPICS.has(n.topic ?? ''));
  const [activeCard, setActiveCard] = useState<'synthesis' | 'completion' | null>(
    synthesisNote ? 'synthesis' : completionNote ? 'completion' : null
  );

  const toggle = (key: 'synthesis' | 'completion') => setActiveCard(prev => prev === key ? null : key);

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
      {/* Output buttons */}
      <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8 }}>
        <button
          onClick={() => synthesisNote && toggle('synthesis')}
          style={{
            padding: '6px 12px', borderRadius: 4, fontSize: 13, cursor: synthesisNote ? 'pointer' : 'default',
            display: 'flex', alignItems: 'center', gap: 8,
            opacity: synthesisNote ? 1 : 0.5,
            border: `1px solid ${activeCard === 'synthesis' ? `${T.teal}66` : T.borderDim}`,
            color: activeCard === 'synthesis' ? T.teal : T.fgDim,
            fontWeight: activeCard === 'synthesis' ? 600 : 400,
            background: 'transparent', fontFamily: T.sans,
          }}
        >
          <Icon name="doc" size={14} />
          Synthesis Report
          {synthesisNote?.created_at && (
            <span style={{ fontFamily: T.mono, fontSize: 10, color: T.fgFaint, marginLeft: 4 }}>
              · {new Date(synthesisNote.created_at).toLocaleDateString('en-US', { month: 'short', day: 'numeric' })}
            </span>
          )}
          {!synthesisNote && <span style={{ fontFamily: T.mono, fontSize: 10, color: T.fgFaint }}>— missing</span>}
        </button>

        <button
          onClick={() => completionNote && toggle('completion')}
          style={{
            padding: '6px 12px', borderRadius: 4, fontSize: 13, cursor: completionNote ? 'pointer' : 'default',
            display: 'flex', alignItems: 'center', gap: 8,
            opacity: completionNote ? 1 : 0.5,
            border: `1px solid ${activeCard === 'completion' ? `${T.olive}66` : T.borderDim}`,
            color: activeCard === 'completion' ? T.olive : T.fgDim,
            fontWeight: activeCard === 'completion' ? 600 : 400,
            background: 'transparent', fontFamily: T.sans,
          }}
        >
          <Icon name="clipboard-check" size={14} />
          Completion Assessment
          {completionNote?.created_at && (
            <span style={{ fontFamily: T.mono, fontSize: 10, color: T.fgFaint, marginLeft: 4 }}>
              · {new Date(completionNote.created_at).toLocaleDateString('en-US', { month: 'short', day: 'numeric' })}
            </span>
          )}
          {!completionNote && <span style={{ fontFamily: T.mono, fontSize: 10, color: T.fgFaint }}>— missing</span>}
        </button>
      </div>

      {/* Content panel */}
      {activeCard === 'synthesis' && synthesisNote && (
        <Panel title="Synthesis Report" borderColor={`${T.teal}55`}>
          <ReportContent noteId={synthesisNote.id} preview={synthesisNote.content_preview} />
        </Panel>
      )}

      {activeCard === 'completion' && completionNote && (
        <Panel title="Completion Assessment" borderColor={`${T.olive}55`}>
          <ReportContent noteId={completionNote.id} preview={completionNote.content_preview} />
        </Panel>
      )}

      {investigationNotes.length > 0 && (
        <div style={{ marginTop: 8, paddingTop: 16, borderTop: `1px solid ${T.borderDim}` }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 12 }}>
            <Icon name="sticky-note" size={14} color={T.blue} />
            <span style={{
              fontFamily: T.mono, fontSize: 10.5, fontWeight: 600, textTransform: 'uppercase',
              letterSpacing: '1px', color: T.blue,
            }}>Investigation Notes</span>
          </div>
          <NotesList notes={investigationNotes} />
        </div>
      )}
    </div>
  );
}

// ─── Main Page ─────────────────────────────────────────────────

interface PageData {
  investigation: Investigation;
  systems: TechReconSystem[];
  notes: TechReconNote[];
  analyses: TechReconAnalysis[];
}

export default function InvestigationPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params);
  const [data, setData] = useState<PageData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [activeSection, setActiveSection] = useState<SectionKey>('scope');
  const [systemDataMap, setSystemDataMap] = useState<Record<string, SystemData> | null>(null);
  const [systemDataLoading, setSystemDataLoading] = useState(false);
  const [selectedIteration, setSelectedIteration] = useState<number | null>(null);

  const fetchData = async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await fetch(`/api/tech-recon/investigation/${id}`);
      if (!res.ok) throw new Error(`API error: ${res.status}`);
      setData(await res.json());
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { fetchData(); }, [id]);

  // Lazy-fetch system data for Discovery/Sensemaking
  useEffect(() => {
    if (!['discovery', 'sensemaking'].includes(activeSection) || systemDataMap !== null || !data) return;
    setSystemDataLoading(true);
    Promise.all(
      data.systems.map(s =>
        fetch(`/api/tech-recon/system/${s.id}`)
          .then(r => r.json())
          .then(d => ({ id: s.id, artifacts: (d.artifacts ?? []) as TechReconArtifact[], notes: (d.notes ?? []) as TechReconNote[] }))
      )
    )
      .then(results => {
        const map: Record<string, SystemData> = {};
        results.forEach(r => { map[r.id] = { artifacts: r.artifacts, notes: r.notes }; });
        setSystemDataMap(map);
      })
      .finally(() => setSystemDataLoading(false));
  }, [activeSection, data, systemDataMap]);

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

  if (error || !data) {
    return (
      <div style={{ minHeight: '100vh', background: T.bg, color: T.fg, fontFamily: T.sans }}>
        <header style={{ borderBottom: `1px solid ${T.borderDim}`, background: T.bgRaised, padding: '12px 24px' }}>
          <BackNav href="/tech-recon" label="Tech Recon" />
        </header>
        <main style={{ maxWidth: 1200, margin: '0 auto', padding: '48px 24px', textAlign: 'center' }}>
          <p style={{ color: '#e05555' }}>{error || 'Investigation not found'}</p>
        </main>
      </div>
    );
  }

  const { investigation, systems, notes, analyses } = data;
  const typeCfg = T.investigationTypeConfig((investigation as any).type);

  const iterations = Array.from(new Set(notes.map(n => n.iteration_number ?? 1))).sort((a, b) => a - b);
  const currentIteration = investigation.iteration_number ?? 1;
  const activeIteration = selectedIteration ?? currentIteration;

  const iterNotes = notes.filter(n => (n.iteration_number ?? 1) === activeIteration);
  const vizPlanNotes = iterNotes.filter(n => n.topic === 'viz-plan');
  const synthesisNote = iterNotes.find(n => n.topic === 'synthesis-report') ?? null;
  const completionNote = iterNotes.find(n => n.topic === 'completion-assessment') ?? null;

  const totalArtifacts = systems.reduce((s, sys) => s + (sys.artifacts_count ?? 0), 0);
  const totalNotes = systems.reduce((s, sys) => s + (sys.notes_count ?? 0), 0);
  const completion: StageCompletion = {
    scope: !!(investigation.goal || investigation.criteria),
    discovery: systems.length > 0,
    sensemaking: totalArtifacts > 0 && totalNotes > 0,
    analysis: analyses.length > 0,
    outputs: synthesisNote !== null,
  };

  const navItems: SectionNavItem[] = [
    { key: 'scope', label: 'Scope', icon: DEFAULT_SECTION_ICONS.scope },
    { key: 'discovery', label: 'Discovery', icon: DEFAULT_SECTION_ICONS.discovery, count: systems.length },
    { key: 'sensemaking', label: 'Sensemaking', icon: DEFAULT_SECTION_ICONS.sensemaking, count: systems.length },
    { key: 'analysis', label: 'Analysis', icon: DEFAULT_SECTION_ICONS.analysis, count: analyses.length },
    { key: 'outputs', label: 'Outputs', icon: DEFAULT_SECTION_ICONS.outputs, hasReport: synthesisNote !== null, hasAssessment: completionNote !== null },
  ];

  const spinner = (
    <div style={{ display: 'flex', justifyContent: 'center', padding: '48px 0' }}>
      <span style={{ fontFamily: T.mono, fontSize: 11, color: T.fgFaint }}>Loading...</span>
    </div>
  );

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
        <button
          onClick={fetchData}
          style={{
            fontFamily: T.mono, fontSize: 10.5, letterSpacing: '0.6px',
            color: T.fgDim, padding: '6px 12px', borderRadius: 2,
            border: `1px solid ${T.borderDim}`, background: 'transparent',
            cursor: 'pointer', display: 'flex', alignItems: 'center', gap: 6,
            transition: 'all 0.12s',
          }}
          onMouseEnter={e => {
            e.currentTarget.style.color = T.teal;
            e.currentTarget.style.borderColor = `${T.teal}66`;
          }}
          onMouseLeave={e => {
            e.currentTarget.style.color = T.fgDim;
            e.currentTarget.style.borderColor = T.borderDim;
          }}
        >
          <Icon name="refresh" size={14} />
          refresh
        </button>
      </header>

      {/* Main layout */}
      <div style={{ maxWidth: 1200, margin: '0 auto', padding: '24px', display: 'flex', gap: 32, flex: 1, width: '100%' }}>
        {/* Sidebar */}
        <aside style={{ width: 192, flexShrink: 0 }}>
          <div style={{ position: 'sticky', top: 24 }}>
            <SectionNav
              items={navItems}
              active={activeSection}
              onSelect={setActiveSection}
              completion={completion}
              iterations={iterations}
              activeIteration={activeIteration}
              onSelectIteration={setSelectedIteration}
            />
          </div>
        </aside>

        {/* Content */}
        <main style={{ flex: 1, minWidth: 0 }}>
          {/* Title + KV metadata */}
          <div style={{ marginBottom: 24 }}>
            <div style={{ display: 'flex', alignItems: 'flex-start', gap: 12, marginBottom: 8 }}>
              <TypeChip short={typeCfg.short} color={typeCfg.color} icon={typeCfg.icon} />
              <h1 style={{
                margin: 0, fontFamily: T.serif, fontSize: 28, lineHeight: 1.15,
                fontWeight: 400, color: T.fg, letterSpacing: '-0.4px', flex: 1,
              }}>{investigation.name}</h1>
              {investigation.status && <StatusBadge status={investigation.status} />}
            </div>

            {investigation.goal && (
              <p style={{ fontSize: 13.5, lineHeight: 1.55, color: T.fgDim, maxWidth: 640, margin: '0 0 12px' }}>
                {investigation.goal}
              </p>
            )}

            <div style={{
              display: 'flex', flexWrap: 'wrap', gap: 14, paddingTop: 12,
              borderTop: `1px solid ${T.borderDim}`,
            }}>
              <KV label="Systems" value={systems.length} mono />
              <KV label="Artifacts" value={totalArtifacts || null} mono />
              <KV label="Notes" value={totalNotes || null} mono />
              <KV label="Analyses" value={analyses.length || null} mono />
              {iterations.length > 1 && <KV label="Iteration" value={`v${activeIteration}`} mono />}
            </div>
          </div>

          {/* Section content panel */}
          <section style={{
            background: T.panel,
            border: `1px solid ${T.border}`,
            borderRadius: 4,
            padding: 20,
          }}>
            {/* Section header */}
            <div style={{
              display: 'flex', alignItems: 'center', gap: 8,
              marginBottom: 16, paddingBottom: 12, borderBottom: `1px solid ${T.borderDim}`,
            }}>
              <span style={{
                fontFamily: T.mono, fontSize: 10.5, fontWeight: 600,
                letterSpacing: '1.2px', textTransform: 'uppercase', color: T.fgDim,
              }}>
                {activeSection}
              </span>
            </div>

            {activeSection === 'scope' && <ScopeSection investigation={investigation} />}
            {activeSection === 'discovery' && (
              systemDataLoading ? spinner : <DiscoverySection systems={systems} systemDataMap={systemDataMap ?? {}} />
            )}
            {activeSection === 'sensemaking' && (
              systemDataLoading ? spinner : <SensemakingSection systems={systems} systemDataMap={systemDataMap ?? {}} selectedIteration={activeIteration} />
            )}
            {activeSection === 'analysis' && (
              <AnalysisSection analyses={analyses} vizPlanNotes={vizPlanNotes} investigationId={id} />
            )}
            {activeSection === 'outputs' && (
              <OutputsSection synthesisNote={synthesisNote} completionNote={completionNote} investigationId={id} notes={iterNotes} />
            )}
          </section>
        </main>
      </div>

      {/* Footer */}
      <footer style={{
        borderTop: `1px solid ${T.borderDim}`,
        marginTop: 'auto',
        padding: '16px 24px',
      }}>
        <div style={{
          maxWidth: 1200, margin: '0 auto',
          display: 'flex', alignItems: 'center', gap: 10,
          fontFamily: T.mono, fontSize: 10, color: T.fgFaint, letterSpacing: '0.6px',
        }}>
          <span>investigation · {investigation.id}</span>
          <span>·</span>
          <span>shape: show-investigation --json</span>
        </div>
      </footer>
    </div>
  );
}
