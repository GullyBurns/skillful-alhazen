'use client';
import { useState, useEffect, use } from 'react';
import {
  T,
} from '@/components/single-paper-deep-dive/tokens';
import {
  BackNav, HeaderStrip, SectionNav, Panel, KV, StatusBadge, TypeChip,
  FilterChip, ClaimRow, MarkdownContent, Icon,
} from '@/components/single-paper-deep-dive/atoms';

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

interface DiveEvidence {
  id: string;
  evidence_type: string;
  experimental_design?: string;
  data_summary?: string;
  source_doi?: string;
  source_title?: string;
  source_url?: string;
}

interface DiveClaim {
  id: string;
  type: 'primary' | 'secondary' | 'peripheral';
  statement: string;
  evidence: DiveEvidence[];
}

interface DiveCitationImpact {
  id: string;
  impact_type: string;
  impact_summary: string;
  citing_doi?: string;
  citing_title?: string;
}

interface DiveAnalysis {
  id: string;
  doi?: string;
  title?: string;
  year?: number;
  paper_type?: string;
  status: string;
  source_count?: number;
  scope_note?: string;
  claims: DiveClaim[];
  citation_impacts: DiveCitationImpact[];
}

interface SourcePaper {
  key: string;
  source_doi?: string;
  source_title?: string;
  source_url?: string;
  evidence_types: Set<string>;
  claim_count: number;
}

// ---------------------------------------------------------------------------
// Derived data helpers
// ---------------------------------------------------------------------------

function deriveUniqueSources(claims: DiveClaim[]): SourcePaper[] {
  const map = new Map<string, SourcePaper>();
  for (const claim of claims) {
    for (const ev of claim.evidence) {
      const key = ev.source_doi || ev.source_title || ev.source_url || ev.id;
      if (!key) continue;
      if (!map.has(key)) {
        map.set(key, {
          key,
          source_doi: ev.source_doi,
          source_title: ev.source_title,
          source_url: ev.source_url,
          evidence_types: new Set(),
          claim_count: 0,
        });
      }
      const src = map.get(key)!;
      src.evidence_types.add(ev.evidence_type);
      src.claim_count += 1;
    }
  }
  return Array.from(map.values()).sort((a, b) => b.claim_count - a.claim_count);
}

// ---------------------------------------------------------------------------
// Section: Paper metadata
// ---------------------------------------------------------------------------

function PaperSection({ analysis }: { analysis: DiveAnalysis }) {
  const doiHref = analysis.doi ? `https://doi.org/${analysis.doi}` : undefined;
  const progress = analysis.source_count != null ? (analysis.source_count / 100) * 100 : 0;

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
      <Panel title="Focal Paper">
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16 }}>
          <KV label="DOI">
            {doiHref ? (
              <a href={doiHref} target="_blank" rel="noopener"
                style={{ display: 'inline-flex', alignItems: 'center', gap: 5, color: T.blue, fontFamily: T.mono, fontSize: 12 }}>
                {analysis.doi}
                <Icon name="external" size={12} color={T.blue} />
              </a>
            ) : (
              <span style={{ fontFamily: T.mono, fontSize: 12, color: T.fgDim }}>—</span>
            )}
          </KV>
          <KV label="Year" value={analysis.year?.toString() || '—'} mono />
          <KV label="Type">
            {analysis.paper_type
              ? <TypeChip label={analysis.paper_type} color={T.teal} />
              : <span style={{ color: T.fgFaint, fontFamily: T.mono, fontSize: 12 }}>—</span>}
          </KV>
          <KV label="Status">
            <StatusBadge status={analysis.status} color={T.statusColor(analysis.status)} />
          </KV>
        </div>
      </Panel>

      <Panel title="Sources Examined">
        <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <span style={{ fontFamily: T.mono, fontSize: 12, color: T.fgDim }}>
              {analysis.source_count ?? 0} / 100 sources
            </span>
            <span style={{ fontFamily: T.mono, fontSize: 11, color: T.fgFaint }}>
              {progress.toFixed(0)}%
            </span>
          </div>
          <div style={{
            height: 6,
            background: T.borderDim,
            borderRadius: 3,
            overflow: 'hidden',
          }}>
            <div style={{
              height: '100%',
              width: `${Math.min(progress, 100)}%`,
              background: progress >= 80 ? T.rust : T.teal,
              borderRadius: 3,
              transition: 'width 0.3s',
            }} />
          </div>
        </div>
      </Panel>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Section: Sources (information artifacts loaded)
// ---------------------------------------------------------------------------

function SourcesSection({ sources, analysis }: { sources: SourcePaper[]; analysis: DiveAnalysis }) {
  const totalEvidence = analysis.claims.reduce((n, c) => n + c.evidence.length, 0);
  const doiHref = analysis.doi ? `https://doi.org/${analysis.doi}` : undefined;

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
      <div style={{
        fontFamily: T.mono,
        fontSize: 11,
        color: T.fgFaint,
        padding: '8px 0',
      }}>
        {sources.length} source papers examined across {totalEvidence} evidence records
      </div>

      {/* Focal paper */}
      <Panel title="Focal Paper" borderColor={T.teal + '44'}>
        <div style={{ display: 'flex', alignItems: 'flex-start', gap: 12 }}>
          <TypeChip label="focal" color={T.teal} />
          <div style={{ flex: 1, minWidth: 0 }}>
            <p style={{ fontFamily: T.sans, fontSize: 13, color: T.fg, margin: '0 0 4px', lineHeight: 1.4 }}>
              {analysis.title}
            </p>
            {doiHref && (
              <a href={doiHref} target="_blank" rel="noopener"
                style={{ display: 'inline-flex', alignItems: 'center', gap: 4, fontFamily: T.mono, fontSize: 11, color: T.blue }}>
                {analysis.doi}
                <Icon name="external" size={11} color={T.blue} />
              </a>
            )}
          </div>
        </div>
      </Panel>

      {/* Cited sources */}
      {sources.length === 0 ? (
        <div style={{ padding: 20, textAlign: 'center', border: `1px solid ${T.borderDim}`, borderRadius: 6 }}>
          <p style={{ fontFamily: T.mono, fontSize: 11, color: T.fgFaint, margin: 0 }}>
            No evidence sources recorded yet
          </p>
        </div>
      ) : (
        <Panel title={`Cited Sources (${sources.length})`}>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 0 }}>
            {sources.map((src, i) => {
              const href = src.source_doi ? `https://doi.org/${src.source_doi}` : src.source_url;
              return (
                <div key={src.key} style={{
                  display: 'flex',
                  alignItems: 'flex-start',
                  gap: 12,
                  padding: '10px 0',
                  borderBottom: i < sources.length - 1 ? `1px solid ${T.borderDim}` : 'none',
                }}>
                  <div style={{ flexShrink: 0, paddingTop: 2 }}>
                    {Array.from(src.evidence_types).map(et => (
                      <TypeChip key={et} label={et.slice(0, 3)} color={T.evidenceTypeColor(et)} />
                    ))}
                  </div>
                  <div style={{ flex: 1, minWidth: 0 }}>
                    <p style={{ fontFamily: T.sans, fontSize: 13, color: T.fg, margin: '0 0 3px', lineHeight: 1.4 }}>
                      {src.source_title || src.source_doi || href || 'Unknown source'}
                    </p>
                    {src.source_doi && (
                      <a href={`https://doi.org/${src.source_doi}`} target="_blank" rel="noopener"
                        style={{ fontFamily: T.mono, fontSize: 11, color: T.blue, textDecoration: 'none' }}>
                        {src.source_doi}
                      </a>
                    )}
                  </div>
                  <div style={{ flexShrink: 0, textAlign: 'right' }}>
                    <span style={{ fontFamily: T.mono, fontSize: 11, color: T.fgFaint }}>
                      {src.claim_count} claim{src.claim_count !== 1 ? 's' : ''}
                    </span>
                  </div>
                </div>
              );
            })}
          </div>
        </Panel>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Section: Claims & Evidence (sensemaking)
// ---------------------------------------------------------------------------

function ClaimsSection({ claimsByType }: {
  claimsByType: Record<string, DiveClaim[]>;
}) {
  const [activeType, setActiveType] = useState<'primary' | 'secondary' | 'peripheral'>('primary');
  const tiers: Array<{ id: 'primary' | 'secondary' | 'peripheral'; label: string }> = [
    { id: 'primary', label: 'Primary' },
    { id: 'secondary', label: 'Secondary' },
    { id: 'peripheral', label: 'Peripheral' },
  ];

  const displayed = claimsByType[activeType] || [];

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
      {/* Tier filter */}
      <div style={{ display: 'flex', gap: 6 }}>
        {tiers.map(tier => (
          <FilterChip
            key={tier.id}
            active={activeType === tier.id}
            onClick={() => setActiveType(tier.id)}
            color={T.claimTypeColor(tier.id)}
          >
            {tier.label} ({(claimsByType[tier.id] || []).length})
          </FilterChip>
        ))}
      </div>

      {/* Claims list */}
      {displayed.length === 0 ? (
        <div style={{ padding: 20, textAlign: 'center', border: `1px solid ${T.borderDim}`, borderRadius: 6 }}>
          <p style={{ fontFamily: T.mono, fontSize: 11, color: T.fgFaint, margin: 0 }}>
            No {activeType} claims recorded
          </p>
        </div>
      ) : (
        <div>
          {displayed.map(claim => (
            <ClaimRow key={claim.id} claim={claim} />
          ))}
        </div>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Section: Citation Impact (analysis)
// ---------------------------------------------------------------------------

function ImpactSection({ impacts }: { impacts: DiveCitationImpact[] }) {
  const [filter, setFilter] = useState<string>('all');
  const impactTypes = ['all', 'extends', 'supports', 'nuances', 'refutes', 'uses', 'unrelated'];
  const displayed = filter === 'all' ? impacts : impacts.filter(i => i.impact_type === filter);

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
      {/* Impact type filter */}
      <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
        {impactTypes.map(type => {
          const count = type === 'all' ? impacts.length : impacts.filter(i => i.impact_type === type).length;
          if (count === 0 && type !== 'all') return null;
          const color = type === 'all' ? T.teal : T.impactTypeColor(type);
          return (
            <FilterChip key={type} active={filter === type} onClick={() => setFilter(type)} color={color}>
              {type} ({count})
            </FilterChip>
          );
        })}
      </div>

      {/* Impact cards */}
      {displayed.length === 0 ? (
        <div style={{ padding: 20, textAlign: 'center', border: `1px solid ${T.borderDim}`, borderRadius: 6 }}>
          <p style={{ fontFamily: T.mono, fontSize: 11, color: T.fgFaint, margin: 0 }}>
            No citation impacts recorded yet
          </p>
        </div>
      ) : (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
          {displayed.map(impact => {
            const color = T.impactTypeColor(impact.impact_type);
            const href = impact.citing_doi ? `https://doi.org/${impact.citing_doi}` : undefined;
            return (
              <div key={impact.id} style={{
                border: `1px solid ${color}30`,
                borderLeft: `3px solid ${color}`,
                borderRadius: 5,
                background: T.panel,
                padding: 14,
              }}>
                <div style={{ display: 'flex', alignItems: 'flex-start', gap: 10, marginBottom: 8 }}>
                  <TypeChip label={impact.impact_type} color={color} />
                  <div style={{ flex: 1, minWidth: 0 }}>
                    <p style={{ fontFamily: T.sans, fontSize: 13, color: T.fg, margin: '0 0 3px', lineHeight: 1.4 }}>
                      {impact.citing_title || impact.citing_doi || '—'}
                    </p>
                    {href && (
                      <a href={href} target="_blank" rel="noopener"
                        style={{ display: 'inline-flex', alignItems: 'center', gap: 4, fontFamily: T.mono, fontSize: 11, color: T.blue }}>
                        {impact.citing_doi}
                        <Icon name="external" size={11} color={T.blue} />
                      </a>
                    )}
                  </div>
                </div>
                <p style={{ fontFamily: T.sans, fontSize: 13, color: T.fgDim, margin: 0, lineHeight: 1.55 }}>
                  {impact.impact_summary}
                </p>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Section: Summary (conclusions)
// ---------------------------------------------------------------------------

function SummarySection({
  analysis,
  claimsByType,
  sources,
}: {
  analysis: DiveAnalysis;
  claimsByType: Record<string, DiveClaim[]>;
  sources: SourcePaper[];
}) {
  const totalEvidence = analysis.claims.reduce((n, c) => n + c.evidence.length, 0);
  const tiers: Array<{ id: string; label: string }> = [
    { id: 'primary', label: 'Primary' },
    { id: 'secondary', label: 'Secondary' },
    { id: 'peripheral', label: 'Peripheral' },
  ];

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
      {/* Claim counts */}
      <Panel title="Claim Summary">
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 12 }}>
          {tiers.map(tier => {
            const count = (claimsByType[tier.id] || []).length;
            const color = T.claimTypeColor(tier.id);
            return (
              <div key={tier.id} style={{
                textAlign: 'center',
                padding: '12px 8px',
                border: `1px solid ${color}33`,
                borderRadius: 5,
                background: `${color}08`,
              }}>
                <div style={{ fontFamily: T.mono, fontSize: 24, color, fontWeight: 600 }}>
                  {count}
                </div>
                <div style={{ fontFamily: T.mono, fontSize: 10, color: T.fgFaint, textTransform: 'uppercase', letterSpacing: '0.08em', marginTop: 4 }}>
                  {tier.label}
                </div>
              </div>
            );
          })}
        </div>
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12, marginTop: 14 }}>
          <KV label="Evidence Records" value={totalEvidence.toString()} mono />
          <KV label="Source Papers" value={sources.length.toString()} mono />
          <KV label="Citation Impacts" value={analysis.citation_impacts.length.toString()} mono />
          <KV label="Sources / Budget">
            <span style={{ fontFamily: T.mono, fontSize: 12, color: (analysis.source_count ?? 0) >= 80 ? T.rust : T.fg }}>
              {analysis.source_count ?? 0} / 100
            </span>
          </KV>
        </div>
      </Panel>

      {/* Scope note */}
      {analysis.scope_note && (
        <Panel title="Scope Note">
          <MarkdownContent content={analysis.scope_note} />
        </Panel>
      )}

      {/* Analysis status */}
      <Panel title="Analysis Status">
        <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
          <StatusBadge status={analysis.status} color={T.statusColor(analysis.status)} />
          <span style={{ fontFamily: T.sans, fontSize: 13, color: T.fgDim }}>
            {analysis.status === 'complete' && 'Analysis complete — all identified claims and sources processed.'}
            {analysis.status === 'in-progress' && 'Analysis is ongoing — claims and evidence are still being gathered.'}
            {analysis.status === 'scope-exhausted' && 'Source budget exhausted (100 sources). See Further Investigation Map in scope note.'}
          </span>
        </div>
      </Panel>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Main page
// ---------------------------------------------------------------------------

const SECTIONS = [
  { id: 'paper', label: 'Paper' },
  { id: 'sources', label: 'Sources' },
  { id: 'claims', label: 'Claims & Evidence' },
  { id: 'impact', label: 'Citation Impact' },
  { id: 'summary', label: 'Summary' },
];

export default function AnalysisPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params);
  const [analysis, setAnalysis] = useState<DiveAnalysis | null>(null);
  const [loading, setLoading] = useState(true);
  const [section, setSection] = useState('paper');

  useEffect(() => {
    fetch(`/api/single-paper-deep-dive/analysis/${encodeURIComponent(id)}`)
      .then(r => r.json())
      .then(d => { setAnalysis(d.analysis || null); setLoading(false); })
      .catch(() => setLoading(false));
  }, [id]);

  if (loading) {
    return (
      <div style={{ maxWidth: 960, margin: '0 auto', padding: '32px 24px', color: T.fgFaint, fontFamily: T.mono, fontSize: 12 }}>
        Loading analysis...
      </div>
    );
  }

  if (!analysis) {
    return (
      <div style={{ maxWidth: 960, margin: '0 auto', padding: '32px 24px' }}>
        <BackNav href="/dive" label="All Analyses" />
        <p style={{ fontFamily: T.mono, fontSize: 12, color: T.rust }}>Analysis not found.</p>
      </div>
    );
  }

  // Derived data
  const claimsByType: Record<string, DiveClaim[]> = { primary: [], secondary: [], peripheral: [] };
  analysis.claims.forEach(c => {
    (claimsByType[c.type] = claimsByType[c.type] || []).push(c);
  });
  const sources = deriveUniqueSources(analysis.claims);

  const completion: Record<string, boolean> = {
    paper: true,
    sources: sources.length > 0,
    claims: analysis.claims.length > 0,
    impact: analysis.citation_impacts.length > 0,
    summary: analysis.status === 'complete' || analysis.status === 'scope-exhausted',
  };

  const totalClaims = analysis.claims.length;
  const totalEvidence = analysis.claims.reduce((n, c) => n + c.evidence.length, 0);

  const sectionItems = [
    { id: 'paper', label: 'Paper' },
    { id: 'sources', label: 'Sources', count: sources.length },
    { id: 'claims', label: 'Claims & Evidence', count: totalClaims },
    { id: 'impact', label: 'Citation Impact', count: analysis.citation_impacts.length },
    { id: 'summary', label: 'Summary' },
  ];

  return (
    <div style={{
      maxWidth: 960,
      margin: '0 auto',
      padding: '32px 24px',
      fontFamily: T.sans,
      color: T.fg,
    }}>
      <BackNav href="/dive" label="All Analyses" />

      <HeaderStrip
        title={analysis.title || analysis.doi || analysis.id}
        meta={
          <>
            {analysis.paper_type && <TypeChip label={analysis.paper_type} color={T.teal} />}
            {analysis.year && (
              <span style={{ fontFamily: T.mono, fontSize: 11, color: T.fgFaint }}>{analysis.year}</span>
            )}
            <StatusBadge status={analysis.status} color={T.statusColor(analysis.status)} />
            <span style={{ fontFamily: T.mono, fontSize: 11, color: T.fgFaint }}>
              {analysis.source_count ?? 0}/100 sources · {totalClaims} claims · {totalEvidence} evidence
            </span>
          </>
        }
      />

      {/* Two-column layout */}
      <div style={{ display: 'flex', gap: 14, alignItems: 'flex-start' }}>
        <SectionNav
          items={sectionItems}
          active={section}
          onSelect={setSection}
          completion={completion}
        />

        <div style={{ flex: 1, minWidth: 0 }}>
          {section === 'paper' && <PaperSection analysis={analysis} />}
          {section === 'sources' && <SourcesSection sources={sources} analysis={analysis} />}
          {section === 'claims' && <ClaimsSection claimsByType={claimsByType} />}
          {section === 'impact' && <ImpactSection impacts={analysis.citation_impacts} />}
          {section === 'summary' && (
            <SummarySection analysis={analysis} claimsByType={claimsByType} sources={sources} />
          )}
        </div>
      </div>
    </div>
  );
}
