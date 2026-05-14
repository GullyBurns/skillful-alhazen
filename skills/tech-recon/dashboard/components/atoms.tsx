'use client';

import { type CSSProperties, type ReactNode } from 'react';
import Link from 'next/link';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { T } from './tokens';

// ─── Icon ──────────────────────────────────────────────────────
// Inline SVG icon component matching the Dossier design reference.
// No lucide-react — all paths are self-contained.

interface IconProps {
  name: string;
  size?: number;
  color?: string;
  style?: CSSProperties;
}

export function Icon({ name, size = 14, color = 'currentColor', style }: IconProps) {
  const s = size;
  const common = {
    width: s,
    height: s,
    viewBox: '0 0 24 24',
    fill: 'none',
    stroke: color,
    strokeWidth: 1.6,
    strokeLinecap: 'round' as const,
    strokeLinejoin: 'round' as const,
    style,
  };
  switch (name) {
    case 'arrow-left':
      return <svg {...common}><path d="M19 12H5M12 19l-7-7 7-7" /></svg>;
    case 'arrow-right':
      return <svg {...common}><path d="M5 12h14M13 6l6 6-6 6" /></svg>;
    case 'external':
      return <svg {...common}><path d="M14 4h6v6" /><path d="M20 4l-9 9" /><path d="M19 14v5a1 1 0 0 1-1 1H5a1 1 0 0 1-1-1V6a1 1 0 0 1 1-1h5" /></svg>;
    case 'refresh':
      return <svg {...common}><path d="M21 12a9 9 0 0 1-9 9 9 9 0 0 1-9-9 9 9 0 0 1 9-9 9 9 0 0 1 6.4 2.6L21 3v5h-5" /></svg>;
    case 'search':
      return <svg {...common}><circle cx="11" cy="11" r="7" /><path d="M21 21l-4-4" /></svg>;
    case 'target':
      return <svg {...common}><circle cx="12" cy="12" r="9" /><circle cx="12" cy="12" r="5" /><circle cx="12" cy="12" r="1.5" fill={color} stroke="none" /></svg>;
    case 'check':
      return <svg {...common}><path d="M5 12l4 4 10-10" /></svg>;
    case 'cross':
      return <svg {...common}><path d="M5 5l14 14M19 5L5 19" /></svg>;
    case 'chevron-right':
      return <svg {...common}><path d="M9 6l6 6-6 6" /></svg>;
    case 'chevron-down':
      return <svg {...common}><path d="M6 9l6 6 6-6" /></svg>;
    case 'code':
      return <svg {...common}><path d="M9 8l-5 4 5 4M15 8l5 4-5 4" /></svg>;
    case 'link':
      return <svg {...common}><path d="M10 14a4 4 0 0 0 5.66 0l3-3a4 4 0 0 0-5.66-5.66l-1 1" /><path d="M14 10a4 4 0 0 0-5.66 0l-3 3a4 4 0 0 0 5.66 5.66l1-1" /></svg>;
    case 'graph':
      return <svg {...common}><circle cx="6" cy="18" r="2" /><circle cx="12" cy="6" r="2" /><circle cx="18" cy="14" r="2" /><path d="M7.5 17l3-9M13.5 7.5l3 5.5" /></svg>;
    case 'share':
      return <svg {...common}><circle cx="6" cy="12" r="2.5" /><circle cx="18" cy="6" r="2.5" /><circle cx="18" cy="18" r="2.5" /><path d="M8 11l8-4M8 13l8 4" /></svg>;
    case 'doc':
      return <svg {...common}><path d="M14 3H6a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V9z" /><path d="M14 3v6h6" /></svg>;
    case 'book':
      return <svg {...common}><path d="M4 4v15a2 2 0 0 1 2-2h14V3H6a2 2 0 0 0-2 2z" /><path d="M4 19a2 2 0 0 0 2 2h14" /></svg>;
    case 'bar-chart':
      return <svg {...common}><rect x="3" y="12" width="4" height="9" rx="1" /><rect x="10" y="7" width="4" height="14" rx="1" /><rect x="17" y="3" width="4" height="18" rx="1" /></svg>;
    case 'play':
      return <svg {...common} fill={color}><path d="M6 4l14 8-14 8z" stroke="none" /></svg>;
    case 'square':
      return <svg {...common}><rect x="4" y="4" width="16" height="16" rx="2" /></svg>;
    case 'circle':
      return <svg {...common}><circle cx="12" cy="12" r="9" /></svg>;
    case 'diamond':
      return <svg {...common}><path d="M12 3 L21 12 L12 21 L3 12 Z" /></svg>;
    case 'triangle':
      return <svg {...common}><path d="M12 4 L21 19 L3 19 Z" /></svg>;
    case 'star':
      return <svg {...common}><path d="M12 3l2.5 6 6.5.5-5 4.5 1.5 6.5L12 17l-5.5 3.5L8 14 3 9.5 9.5 9z" /></svg>;
    case 'sticky-note':
      return <svg {...common}><path d="M15.5 3H5a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2V8.5L15.5 3z" /><path d="M14 3v6h6" /></svg>;
    case 'flask':
      return <svg {...common}><path d="M9 3h6M10 3v7.4a2 2 0 0 1-.4 1.2L4 19a1 1 0 0 0 .8 1.6h14.4a1 1 0 0 0 .8-1.6l-5.6-7.4A2 2 0 0 1 14 10.4V3" /></svg>;
    case 'file-output':
      return <svg {...common}><path d="M14 3H6a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V9z" /><path d="M14 3v6h6" /><path d="M9 15l3 3 3-3" /></svg>;
    case 'clipboard-check':
      return <svg {...common}><rect x="8" y="2" width="8" height="4" rx="1" /><path d="M16 4h2a2 2 0 0 1 2 2v14a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2V6a2 2 0 0 1 2-2h2" /><path d="M9 14l2 2 4-4" /></svg>;
    case 'globe':
      return <svg {...common}><circle cx="12" cy="12" r="9" /><path d="M2 12h20M12 2a14.5 14.5 0 0 1 0 20 14.5 14.5 0 0 1 0-20" /></svg>;
    case 'folder':
      return <svg {...common}><path d="M4 4h5l2 2h9a2 2 0 0 1 2 2v10a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V6a2 2 0 0 1 2-2z" /></svg>;
    case 'package':
      return <svg {...common}><path d="M12 3l9 4.5v9L12 21l-9-4.5v-9z" /><path d="M12 12l9-4.5M12 12v9M12 12L3 7.5" /></svg>;
    case 'sparkles':
      return <svg {...common}><path d="M12 3v4M12 17v4M3 12h4M17 12h4M6 6l2.5 2.5M15.5 15.5L18 18M6 18l2.5-2.5M15.5 8.5L18 6" /></svg>;
    default:
      return <svg {...common}><circle cx="12" cy="12" r="6" /></svg>;
  }
}

// ─── Panel ─────────────────────────────────────────────────────
// Dark container with teal border, mono uppercase title header.

interface PanelProps {
  title?: string;
  action?: ReactNode;
  borderColor?: string;
  bgColor?: string;
  children: ReactNode;
  style?: CSSProperties;
}

export function Panel({ title, action, borderColor, bgColor, children, style }: PanelProps) {
  return (
    <section style={{
      background: bgColor || T.panel,
      border: `1px solid ${borderColor || T.border}`,
      borderRadius: 4,
      padding: '14px 16px',
      display: 'flex',
      flexDirection: 'column',
      gap: 12,
      ...style,
    }}>
      {(title || action) && (
        <header style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
          <h3 style={{
            margin: 0,
            fontFamily: T.mono,
            fontSize: 10.5,
            fontWeight: 600,
            letterSpacing: '1.4px',
            textTransform: 'uppercase',
            color: T.fgDim,
          }}>{title}</h3>
          <div style={{ flex: 1 }} />
          {action}
        </header>
      )}
      {children}
    </section>
  );
}

// ─── KV ────────────────────────────────────────────────────────
// Key-value display: uppercase mono label over value.

interface KVProps {
  label: string;
  value: string | number | null | undefined;
  mono?: boolean;
  accent?: string | null;
}

export function KV({ label, value, mono, accent }: KVProps) {
  if (value == null) return null;
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 2, minWidth: 0 }}>
      <span style={{
        fontFamily: T.mono,
        fontSize: 9.5,
        letterSpacing: '1.2px',
        textTransform: 'uppercase',
        color: T.fgFaint,
      }}>{label}</span>
      <span style={{
        fontSize: 13,
        color: accent || T.fg,
        fontFamily: mono ? T.mono : T.sans,
      }}>{value}</span>
    </div>
  );
}

// ─── StatusBadge ───────────────────────────────────────────────
// Mono uppercase bordered badge.

interface StatusBadgeProps {
  status: string;
  color?: string;
  dim?: boolean;
}

export function StatusBadge({ status, color, dim }: StatusBadgeProps) {
  const c = color || T.statusColor(status);
  return (
    <span style={{
      fontFamily: T.mono,
      fontSize: 9.5,
      letterSpacing: '0.8px',
      textTransform: 'uppercase',
      padding: '1.5px 7px',
      borderRadius: 2,
      color: dim ? T.fgFaint : c,
      border: `1px solid ${dim ? T.borderDim : `${c}66`}`,
      whiteSpace: 'nowrap',
    }}>{status}</span>
  );
}

// ─── TypeChip ──────────────────────────────────────────────────
// Bordered pill with short code and optional icon.

interface TypeChipProps {
  short: string;
  color: string;
  icon?: string;
}

export function TypeChip({ short, color, icon }: TypeChipProps) {
  return (
    <span style={{
      display: 'inline-flex',
      alignItems: 'center',
      gap: 4,
      padding: '3px 8px',
      borderRadius: 3,
      background: 'transparent',
      border: `1px solid ${color}`,
      color,
      fontFamily: T.mono,
      fontSize: 10.5,
      letterSpacing: '1px',
      fontWeight: 600,
    }}>
      {icon && <Icon name={icon} size={11} color={color} />}
      {short}
    </span>
  );
}

// ─── FilterChip ────────────────────────────────────────────────
// Togglable pill for filtering.

interface FilterChipProps {
  active: boolean;
  onClick: () => void;
  color: string;
  children: ReactNode;
}

export function FilterChip({ active, onClick, color, children }: FilterChipProps) {
  return (
    <button
      onClick={onClick}
      style={{
        fontFamily: T.mono,
        fontSize: 10.5,
        letterSpacing: '0.4px',
        padding: '3px 8px',
        borderRadius: 3,
        cursor: 'pointer',
        background: active ? color : 'transparent',
        color: active ? T.bg : color,
        border: `1px solid ${active ? color : T.borderDim}`,
        textTransform: 'lowercase',
      }}
    >{children}</button>
  );
}

// ─── GroupHeader ────────────────────────────────────────────────

interface GroupHeaderProps {
  label: string;
  count: number;
  hint?: string;
}

export function GroupHeader({ label, count, hint }: GroupHeaderProps) {
  return (
    <div style={{
      display: 'flex',
      alignItems: 'baseline',
      gap: 12,
      padding: '14px 16px 8px',
    }}>
      <h3 style={{
        margin: 0,
        fontFamily: T.mono,
        fontSize: 10.5,
        fontWeight: 600,
        letterSpacing: '1.4px',
        textTransform: 'uppercase',
        color: T.fg,
      }}>{label}</h3>
      <span style={{ fontFamily: T.mono, fontSize: 10.5, color: T.fgFaint }}>{count}</span>
      <span style={{ flex: 1 }} />
      {hint && (
        <span style={{ fontFamily: T.mono, fontSize: 10, color: T.fgFaint, fontStyle: 'italic' }}>{hint}</span>
      )}
    </div>
  );
}

// ─── BackNav ───────────────────────────────────────────────────
// Simple back-link with arrow icon.

interface BackNavProps {
  href: string;
  label: string;
}

export function BackNav({ href, label }: BackNavProps) {
  return (
    <Link
      href={href}
      style={{
        display: 'inline-flex',
        alignItems: 'center',
        gap: 6,
        fontFamily: T.mono,
        fontSize: 12,
        color: T.teal,
        textDecoration: 'none',
      }}
    >
      <Icon name="arrow-left" size={14} color={T.teal} />
      {label}
    </Link>
  );
}

// ─── HeaderStrip ───────────────────────────────────────────────
// Full-width header bar with type chip, serif title, description, KV row, tags.

interface HeaderStripProps {
  typeChip?: { short: string; color: string; icon?: string };
  context?: string;
  title: string;
  description?: string;
  kvPairs?: Array<{ label: string; value: string | number | null | undefined; accent?: string | null }>;
  tags?: string[];
}

export function HeaderStrip({ typeChip, context, title, description, kvPairs, tags }: HeaderStripProps) {
  return (
    <header style={{
      background: T.bgRaised,
      border: `1px solid ${T.border}`,
      borderRadius: 4,
      padding: '18px 22px',
      display: 'flex',
      flexDirection: 'column',
      gap: 14,
    }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 12, flexWrap: 'wrap' }}>
        {typeChip && <TypeChip short={typeChip.short} color={typeChip.color} icon={typeChip.icon} />}
        {context && (
          <>
            <span style={{ color: T.fgFaint, fontFamily: T.mono, fontSize: 11 }}>·</span>
            <span style={{ color: T.fgDim, fontSize: 13, fontFamily: T.mono }}>{context}</span>
          </>
        )}
      </div>

      <h1 style={{
        margin: 0,
        fontFamily: T.serif,
        fontSize: 28,
        lineHeight: 1.15,
        fontWeight: 400,
        color: T.fg,
        letterSpacing: '-0.4px',
      }}>{title}</h1>

      {description && (
        <p style={{
          margin: 0,
          fontSize: 13.5,
          lineHeight: 1.55,
          color: T.fgDim,
          maxWidth: 720,
        }}>{description}</p>
      )}

      {kvPairs && kvPairs.length > 0 && (
        <div style={{
          display: 'flex',
          alignItems: 'center',
          gap: 14,
          flexWrap: 'wrap',
          paddingTop: 10,
          borderTop: `1px solid ${T.borderDim}`,
          marginTop: 4,
        }}>
          {kvPairs.map(kv => (
            <KV key={kv.label} label={kv.label} value={kv.value} mono accent={kv.accent} />
          ))}
        </div>
      )}

      {tags && tags.length > 0 && (
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6 }}>
          {tags.map(t => (
            <span key={t} style={{
              fontFamily: T.mono,
              fontSize: 10.5,
              color: T.fgDim,
              padding: '2px 7px',
              border: `1px solid ${T.borderDim}`,
              borderRadius: 3,
            }}>{t}</span>
          ))}
        </div>
      )}
    </header>
  );
}

// ─── MarkdownContent ───────────────────────────────────────────
// Renders markdown with inline-styled component overrides for Starry Night palette.
// Replaces `prose prose-sm dark:prose-invert` Tailwind classes.

interface MarkdownContentProps {
  content: string;
  style?: CSSProperties;
}

/* eslint-disable @typescript-eslint/no-explicit-any */
const mdComponents: Record<string, React.ComponentType<any>> = {
  p: ({ children }: any) => (
    <p style={{ margin: '0 0 10px', lineHeight: 1.55, color: T.fg, fontSize: 13.5 }}>{children}</p>
  ),
  h1: ({ children }: any) => (
    <h1 style={{ fontFamily: T.serif, fontSize: 22, fontWeight: 400, color: T.fg, margin: '16px 0 8px', letterSpacing: '-0.3px' }}>{children}</h1>
  ),
  h2: ({ children }: any) => (
    <h2 style={{ fontFamily: T.serif, fontSize: 18, fontWeight: 400, color: T.fg, margin: '14px 0 6px', letterSpacing: '-0.2px' }}>{children}</h2>
  ),
  h3: ({ children }: any) => (
    <h3 style={{ fontFamily: T.mono, fontSize: 13, fontWeight: 600, color: T.fgDim, margin: '12px 0 6px', textTransform: 'uppercase', letterSpacing: '0.8px' }}>{children}</h3>
  ),
  h4: ({ children }: any) => (
    <h4 style={{ fontFamily: T.mono, fontSize: 12, fontWeight: 600, color: T.fgDim, margin: '10px 0 4px' }}>{children}</h4>
  ),
  a: ({ href, children }: any) => (
    <a href={href} target="_blank" rel="noopener noreferrer" style={{ color: T.teal, textDecoration: 'underline', textUnderlineOffset: '2px' }}>{children}</a>
  ),
  code: ({ children, className }: any) => {
    // Inline code (no className) vs code block (has className from remark)
    if (!className) {
      return (
        <code style={{
          fontFamily: T.mono,
          fontSize: '0.9em',
          background: T.bgSunken,
          padding: '1px 5px',
          borderRadius: 3,
          color: T.teal,
        }}>{children}</code>
      );
    }
    return <code className={className} style={{ fontFamily: T.mono, fontSize: 12 }}>{children}</code>;
  },
  pre: ({ children }: any) => (
    <pre style={{
      fontFamily: T.mono,
      fontSize: 12,
      background: T.bgSunken,
      border: `1px solid ${T.borderDim}`,
      borderRadius: 4,
      padding: '12px 14px',
      overflowX: 'auto',
      margin: '8px 0 12px',
      lineHeight: 1.5,
    }}>{children}</pre>
  ),
  ul: ({ children }: any) => (
    <ul style={{ margin: '4px 0 10px', paddingLeft: 20, listStyleType: 'disc', color: T.fgDim }}>{children}</ul>
  ),
  ol: ({ children }: any) => (
    <ol style={{ margin: '4px 0 10px', paddingLeft: 20, listStyleType: 'decimal', color: T.fgDim }}>{children}</ol>
  ),
  li: ({ children }: any) => (
    <li style={{ marginBottom: 4, fontSize: 13.5, lineHeight: 1.55, color: T.fg }}>{children}</li>
  ),
  blockquote: ({ children }: any) => (
    <blockquote style={{
      borderLeft: `3px solid ${T.borderDim}`,
      paddingLeft: 14,
      margin: '8px 0',
      color: T.fgDim,
      fontStyle: 'italic',
    }}>{children}</blockquote>
  ),
  table: ({ children }: any) => (
    <div style={{ overflowX: 'auto', margin: '8px 0' }}>
      <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 12 }}>{children}</table>
    </div>
  ),
  thead: ({ children }: any) => (
    <thead style={{ background: T.bgSunken }}>{children}</thead>
  ),
  th: ({ children }: any) => (
    <th style={{
      fontFamily: T.mono,
      fontSize: 10.5,
      fontWeight: 600,
      color: T.fgDim,
      textAlign: 'left',
      padding: '6px 10px',
      border: `1px solid ${T.borderDim}`,
      textTransform: 'uppercase',
      letterSpacing: '0.5px',
    }}>{children}</th>
  ),
  td: ({ children }: any) => (
    <td style={{
      padding: '5px 10px',
      border: `1px solid ${T.borderDim}`,
      color: T.fg,
      fontSize: 12.5,
    }}>{children}</td>
  ),
  strong: ({ children }: any) => (
    <strong style={{ fontWeight: 600, color: T.fg }}>{children}</strong>
  ),
  em: ({ children }: any) => (
    <em style={{ color: T.fgDim }}>{children}</em>
  ),
  hr: () => (
    <hr style={{ border: 'none', borderTop: `1px solid ${T.borderDim}`, margin: '12px 0' }} />
  ),
};
/* eslint-enable @typescript-eslint/no-explicit-any */

export function MarkdownContent({ content, style }: MarkdownContentProps) {
  // Content from TypeDB may have literal \n sequences instead of real newlines
  const unescaped = content.replace(/\\n/g, '\n');
  return (
    <div style={style}>
      <ReactMarkdown remarkPlugins={[remarkGfm]} components={mdComponents}>
        {unescaped}
      </ReactMarkdown>
    </div>
  );
}

// ─── SectionNav ────────────────────────────────────────────────
// Sidebar navigation for investigation sections, restyled with inline styles.

export type SectionKey = 'scope' | 'discovery' | 'sensemaking' | 'analysis' | 'outputs';

export interface StageCompletion {
  scope: boolean;
  discovery: boolean;
  sensemaking: boolean;
  analysis: boolean;
  outputs: boolean;
}

export interface SectionNavItem {
  key: SectionKey;
  label: string;
  icon: string; // Icon name string instead of LucideIcon
  count?: number;
  hasReport?: boolean;
  hasAssessment?: boolean;
}

export const DEFAULT_SECTION_ICONS: Record<SectionKey, string> = {
  scope: 'target',
  discovery: 'search',
  sensemaking: 'flask',
  analysis: 'bar-chart',
  outputs: 'file-output',
};

interface SectionNavProps {
  items: SectionNavItem[];
  active: SectionKey;
  onSelect: (key: SectionKey) => void;
  completion?: StageCompletion;
  iterations?: number[];
  activeIteration?: number;
  onSelectIteration?: (iter: number) => void;
}

export function SectionNav({ items, active, onSelect, completion, iterations, activeIteration, onSelectIteration }: SectionNavProps) {
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
      <nav style={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
        {items.map(item => {
          const isActive = item.key === active;
          const isDone = completion?.[item.key] ?? false;
          const isOutputs = item.key === 'outputs';

          return (
            <button
              key={item.key}
              onClick={() => onSelect(item.key)}
              style={{
                display: 'flex',
                flexDirection: 'column',
                alignItems: 'flex-start',
                width: '100%',
                padding: '8px 12px',
                borderRadius: 2,
                textAlign: 'left',
                cursor: 'pointer',
                background: isActive ? 'rgba(90,173,175,0.06)' : 'transparent',
                border: 'none',
                borderLeft: `4px solid ${isActive ? T.teal : 'transparent'}`,
                color: isActive ? T.teal : T.fgDim,
                transition: 'all 0.12s',
              }}
              onMouseEnter={e => {
                if (!isActive) {
                  e.currentTarget.style.background = 'rgba(200,221,232,0.04)';
                  e.currentTarget.style.color = T.fg;
                }
              }}
              onMouseLeave={e => {
                if (!isActive) {
                  e.currentTarget.style.background = 'transparent';
                  e.currentTarget.style.color = T.fgDim;
                }
              }}
            >
              <span style={{ display: 'flex', alignItems: 'center', gap: 8, width: '100%' }}>
                {/* Stage dot */}
                <span style={{
                  display: 'inline-block',
                  width: 6,
                  height: 6,
                  borderRadius: 3,
                  background: isDone ? T.teal : isActive ? T.olive : 'rgba(200,221,232,0.15)',
                  flexShrink: 0,
                  transition: 'background 0.15s',
                }} />
                <Icon name={item.icon} size={14} />
                <span style={{
                  fontFamily: T.mono,
                  fontSize: 11,
                  letterSpacing: '0.6px',
                  fontWeight: isActive ? 600 : 500,
                  flex: 1,
                }}>{item.label}</span>
                {item.count !== undefined && item.count > 0 && (
                  <span style={{
                    fontFamily: T.mono,
                    fontSize: 10,
                    color: T.fgFaint,
                    fontVariantNumeric: 'tabular-nums',
                  }}>{item.count}</span>
                )}
              </span>

              {isOutputs && (item.hasReport !== undefined || item.hasAssessment !== undefined) && (
                <span style={{
                  display: 'flex',
                  gap: 12,
                  marginTop: 4,
                  marginLeft: 28,
                  fontFamily: T.mono,
                  fontSize: 9.5,
                  letterSpacing: '0.6px',
                }}>
                  {item.hasReport !== undefined && (
                    <span style={{
                      display: 'flex',
                      alignItems: 'center',
                      gap: 3,
                      color: item.hasReport ? T.teal : 'rgba(200,221,232,0.2)',
                    }}>
                      <Icon name={item.hasReport ? 'check' : 'cross'} size={10} />
                      report
                    </span>
                  )}
                  {item.hasAssessment !== undefined && (
                    <span style={{
                      display: 'flex',
                      alignItems: 'center',
                      gap: 3,
                      color: item.hasAssessment ? T.teal : 'rgba(200,221,232,0.2)',
                    }}>
                      <Icon name={item.hasAssessment ? 'check' : 'cross'} size={10} />
                      assessed
                    </span>
                  )}
                </span>
              )}
            </button>
          );
        })}
      </nav>

      {/* Iteration selector */}
      {iterations && iterations.length > 1 && onSelectIteration && (
        <div style={{
          padding: '8px 12px 0',
          borderTop: `1px solid ${T.borderDim}`,
        }}>
          <span style={{
            fontFamily: T.mono,
            fontSize: 9,
            letterSpacing: '1.4px',
            textTransform: 'uppercase',
            color: T.fgFaint,
            display: 'block',
            marginBottom: 8,
          }}>Iteration</span>
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6 }}>
            {iterations.map(iter => (
              <button
                key={iter}
                onClick={() => onSelectIteration(iter)}
                style={{
                  padding: '2px 8px',
                  borderRadius: 2,
                  fontFamily: T.mono,
                  fontSize: 10,
                  letterSpacing: '0.6px',
                  border: `1px solid ${iter === activeIteration ? `${T.teal}66` : T.borderDim}`,
                  color: iter === activeIteration ? T.teal : T.fgFaint,
                  fontWeight: iter === activeIteration ? 600 : 400,
                  background: 'transparent',
                  cursor: 'pointer',
                }}
              >v{iter}</button>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
