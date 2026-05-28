'use client';
import React, { useState } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { T } from './tokens';

// ---------------------------------------------------------------------------
// Icon primitives
// ---------------------------------------------------------------------------

export function Icon({ name, size = 16, color }: { name: string; size?: number; color?: string }) {
  const c = color || T.fgDim;
  const s = { width: size, height: size, flexShrink: 0 } as React.CSSProperties;
  if (name === 'arrow-left') return (
    <svg style={s} viewBox="0 0 16 16" fill="none" stroke={c} strokeWidth="1.5">
      <path d="M10 3L5 8l5 5" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
  if (name === 'external') return (
    <svg style={s} viewBox="0 0 16 16" fill="none" stroke={c} strokeWidth="1.5">
      <path d="M6 3H3v10h10v-3M9 3h4v4M13 3L7 9" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
  if (name === 'chevron-down') return (
    <svg style={s} viewBox="0 0 16 16" fill="none" stroke={c} strokeWidth="1.5">
      <path d="M4 6l4 4 4-4" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
  if (name === 'chevron-right') return (
    <svg style={s} viewBox="0 0 16 16" fill="none" stroke={c} strokeWidth="1.5">
      <path d="M6 4l4 4-4 4" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
  if (name === 'check') return (
    <svg style={s} viewBox="0 0 16 16" fill="none" stroke={c} strokeWidth="1.5">
      <path d="M3 8l3.5 3.5L13 4" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
  if (name === 'dot') return (
    <svg style={s} viewBox="0 0 16 16" fill={c}>
      <circle cx="8" cy="8" r="3.5" />
    </svg>
  );
  return <span style={{ width: size, height: size, display: 'inline-block' }} />;
}

// ---------------------------------------------------------------------------
// Layout primitives
// ---------------------------------------------------------------------------

export function Panel({
  title,
  action,
  borderColor,
  bgColor,
  children,
  style,
}: {
  title?: React.ReactNode;
  action?: React.ReactNode;
  borderColor?: string;
  bgColor?: string;
  children?: React.ReactNode;
  style?: React.CSSProperties;
}) {
  return (
    <div style={{
      border: `1px solid ${borderColor || T.border}`,
      borderRadius: 6,
      background: bgColor || T.panel,
      overflow: 'hidden',
      ...style,
    }}>
      {title && (
        <div style={{
          display: 'flex', alignItems: 'center', justifyContent: 'space-between',
          padding: '8px 14px',
          borderBottom: `1px solid ${borderColor || T.border}`,
          background: T.bgRaised,
        }}>
          <span style={{ fontFamily: T.mono, fontSize: 11, color: T.fgDim, textTransform: 'uppercase', letterSpacing: '0.08em' }}>
            {title}
          </span>
          {action && <span>{action}</span>}
        </div>
      )}
      <div style={{ padding: 14 }}>{children}</div>
    </div>
  );
}

export function KV({
  label,
  value,
  mono,
  accent,
  children,
}: {
  label: string;
  value?: React.ReactNode;
  mono?: boolean;
  accent?: string;
  children?: React.ReactNode;
}) {
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 3 }}>
      <span style={{ fontFamily: T.mono, fontSize: 10, color: T.fgFaint, textTransform: 'uppercase', letterSpacing: '0.08em' }}>
        {label}
      </span>
      <span style={{
        fontFamily: mono ? T.mono : T.sans,
        fontSize: mono ? 12 : 13,
        color: accent || T.fg,
      }}>
        {children ?? value}
      </span>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Badge and chip components
// ---------------------------------------------------------------------------

export function StatusBadge({ status, color }: { status: string; color?: string }) {
  const c = color || T.statusColor(status);
  return (
    <span style={{
      fontFamily: T.mono,
      fontSize: 10,
      color: c,
      border: `1px solid ${c}`,
      borderRadius: 3,
      padding: '2px 7px',
      textTransform: 'uppercase',
      letterSpacing: '0.08em',
      background: `${c}18`,
    }}>
      {status}
    </span>
  );
}

export function TypeChip({ label, color }: { label: string; color: string }) {
  return (
    <span style={{
      fontFamily: T.mono,
      fontSize: 10,
      color,
      border: `1px solid ${color}`,
      borderRadius: 3,
      padding: '2px 7px',
      textTransform: 'uppercase',
      letterSpacing: '0.06em',
      background: `${color}18`,
      whiteSpace: 'nowrap',
    }}>
      {label}
    </span>
  );
}

export function FilterChip({
  active,
  onClick,
  color,
  children,
}: {
  active: boolean;
  onClick: () => void;
  color: string;
  children: React.ReactNode;
}) {
  return (
    <button
      onClick={onClick}
      style={{
        fontFamily: T.mono,
        fontSize: 11,
        color: active ? color : T.fgDim,
        border: `1px solid ${active ? color : T.borderDim}`,
        borderRadius: 4,
        padding: '4px 10px',
        background: active ? `${color}18` : 'transparent',
        cursor: 'pointer',
        transition: 'all 0.1s',
        letterSpacing: '0.04em',
      }}
    >
      {children}
    </button>
  );
}

// ---------------------------------------------------------------------------
// Navigation components
// ---------------------------------------------------------------------------

export function BackNav({ href, label }: { href: string; label: string }) {
  return (
    <a href={href} style={{
      display: 'inline-flex', alignItems: 'center', gap: 6,
      fontFamily: T.mono, fontSize: 11, color: T.fgDim,
      textDecoration: 'none', marginBottom: 16,
    }}>
      <Icon name="arrow-left" size={14} color={T.fgDim} />
      {label}
    </a>
  );
}

export function SectionNav({
  items,
  active,
  onSelect,
  completion,
}: {
  items: { id: string; label: string; count?: number }[];
  active: string;
  onSelect: (id: string) => void;
  completion?: Record<string, boolean>;
}) {
  return (
    <div style={{
      width: 160,
      flexShrink: 0,
      display: 'flex',
      flexDirection: 'column',
      gap: 2,
    }}>
      {items.map(item => {
        const isActive = item.id === active;
        const isDone = completion?.[item.id];
        return (
          <button
            key={item.id}
            onClick={() => onSelect(item.id)}
            style={{
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'space-between',
              padding: '8px 12px',
              borderRadius: 4,
              border: isActive ? `1px solid ${T.teal}` : `1px solid transparent`,
              background: isActive ? T.tealDim : 'transparent',
              cursor: 'pointer',
              textAlign: 'left',
              gap: 6,
            }}
          >
            <span style={{
              fontFamily: T.sans,
              fontSize: 12,
              color: isActive ? T.teal : T.fgDim,
              fontWeight: isActive ? 500 : 400,
              flex: 1,
            }}>
              {item.label}
              {item.count !== undefined && (
                <span style={{ color: T.fgFaint, marginLeft: 4 }}>({item.count})</span>
              )}
            </span>
            {isDone && <Icon name="check" size={12} color={T.teal} />}
          </button>
        );
      })}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Header strip for detail pages
// ---------------------------------------------------------------------------

export function HeaderStrip({
  title,
  meta,
  children,
}: {
  title: string;
  meta?: React.ReactNode;
  children?: React.ReactNode;
}) {
  return (
    <div style={{
      background: T.bgRaised,
      border: `1px solid ${T.border}`,
      borderRadius: 6,
      padding: '16px 20px',
      marginBottom: 16,
    }}>
      <h1 style={{
        fontFamily: T.serif,
        fontSize: 20,
        color: T.fg,
        margin: 0,
        lineHeight: 1.3,
      }}>
        {title}
      </h1>
      {meta && (
        <div style={{
          display: 'flex',
          alignItems: 'center',
          gap: 12,
          marginTop: 10,
          flexWrap: 'wrap',
        }}>
          {meta}
        </div>
      )}
      {children}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Markdown renderer (unescapes TypeDB-stored \n sequences)
// ---------------------------------------------------------------------------

const mdComponents = {
  p: ({ children }: { children?: React.ReactNode }) => (
    <p style={{ margin: '0 0 8px', color: T.fg, lineHeight: 1.6, fontSize: 13 }}>{children}</p>
  ),
  code: ({ children }: { children?: React.ReactNode }) => (
    <code style={{ fontFamily: T.mono, fontSize: 11, color: T.teal, background: T.bgSunken, padding: '1px 4px', borderRadius: 3 }}>
      {children}
    </code>
  ),
  a: ({ href, children }: { href?: string; children?: React.ReactNode }) => (
    <a href={href} target="_blank" rel="noopener" style={{ color: T.teal, textDecoration: 'none' }}>
      {children}
    </a>
  ),
};

export function MarkdownContent({ content }: { content: string }) {
  const unescaped = content.replace(/\\n/g, '\n');
  return (
    <ReactMarkdown remarkPlugins={[remarkGfm]} components={mdComponents as never}>
      {unescaped}
    </ReactMarkdown>
  );
}

// ---------------------------------------------------------------------------
// Expandable claim row (used in Claims section)
// ---------------------------------------------------------------------------

export function ClaimRow({ claim }: { claim: { id: string; type: string; statement: string; evidence: unknown[] } }) {
  const [open, setOpen] = useState(false);
  const evidenceList = claim.evidence as Array<{
    id: string; evidence_type: string; experimental_design?: string;
    data_summary?: string; source_doi?: string; source_title?: string; source_url?: string;
  }>;
  const color = T.claimTypeColor(claim.type);

  return (
    <div style={{
      border: `1px solid ${open ? color + '44' : T.border}`,
      borderRadius: 6,
      background: open ? T.panelHi : T.panel,
      marginBottom: 8,
      overflow: 'hidden',
      transition: 'border-color 0.15s',
    }}>
      <button
        onClick={() => setOpen(o => !o)}
        style={{
          width: '100%', display: 'flex', alignItems: 'flex-start', gap: 10,
          padding: '10px 14px', background: 'transparent', border: 'none',
          cursor: 'pointer', textAlign: 'left',
        }}
      >
        <div style={{ paddingTop: 2, flexShrink: 0 }}>
          <Icon name={open ? 'chevron-down' : 'chevron-right'} size={14} color={T.fgFaint} />
        </div>
        <div style={{ flex: 1, minWidth: 0 }}>
          <p style={{
            fontFamily: T.sans, fontSize: 13, color: T.fg,
            margin: 0, lineHeight: 1.55,
          }}>
            {claim.statement}
          </p>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginTop: 6 }}>
            <TypeChip label={claim.type} color={color} />
            <span style={{ fontFamily: T.mono, fontSize: 11, color: T.fgFaint }}>
              {evidenceList.length} evidence record{evidenceList.length !== 1 ? 's' : ''}
            </span>
          </div>
        </div>
      </button>

      {open && (
        <div style={{ padding: '0 14px 14px', borderTop: `1px solid ${T.borderDim}` }}>
          {evidenceList.length === 0 ? (
            <p style={{ fontFamily: T.mono, fontSize: 11, color: T.fgFaint, margin: '12px 0 0' }}>
              No evidence recorded
            </p>
          ) : (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 10, marginTop: 12 }}>
              {evidenceList.map(ev => (
                <EvidenceCard key={ev.id} evidence={ev} />
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
}

export function EvidenceCard({ evidence }: {
  evidence: {
    id: string; evidence_type: string; experimental_design?: string;
    data_summary?: string; source_doi?: string; source_title?: string; source_url?: string;
  }
}) {
  const color = T.evidenceTypeColor(evidence.evidence_type);
  const sourceHref = evidence.source_doi
    ? `https://doi.org/${evidence.source_doi}`
    : evidence.source_url;

  return (
    <div style={{
      border: `1px solid ${T.borderDim}`,
      borderRadius: 5,
      background: T.bgSunken,
      padding: 12,
    }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 8 }}>
        <TypeChip label={evidence.evidence_type} color={color} />
        {(evidence.source_title || evidence.source_doi) && (
          <span style={{ fontFamily: T.sans, fontSize: 12, color: T.fgDim, flex: 1, minWidth: 0 }}>
            {sourceHref ? (
              <a href={sourceHref} target="_blank" rel="noopener" style={{ color: T.blue, textDecoration: 'none' }}>
                {evidence.source_title || evidence.source_doi}
              </a>
            ) : (
              evidence.source_title || evidence.source_doi
            )}
          </span>
        )}
      </div>
      {evidence.experimental_design && (
        <div style={{ marginBottom: 6 }}>
          <span style={{ fontFamily: T.mono, fontSize: 10, color: T.fgFaint, textTransform: 'uppercase', letterSpacing: '0.07em' }}>
            Design
          </span>
          <p style={{ fontFamily: T.sans, fontSize: 12, color: T.fgDim, margin: '3px 0 0', lineHeight: 1.5 }}>
            {evidence.experimental_design}
          </p>
        </div>
      )}
      {evidence.data_summary && (
        <div>
          <span style={{ fontFamily: T.mono, fontSize: 10, color: T.fgFaint, textTransform: 'uppercase', letterSpacing: '0.07em' }}>
            Data
          </span>
          <p style={{ fontFamily: T.sans, fontSize: 12, color: T.fg, margin: '3px 0 0', lineHeight: 1.5 }}>
            {evidence.data_summary}
          </p>
        </div>
      )}
    </div>
  );
}
