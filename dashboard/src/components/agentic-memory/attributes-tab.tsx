'use client';

import { useState } from 'react';
import { colors, formatRelativeDate } from './tokens';
import MarkdownContent from './markdown';

interface AttributesTabProps {
  entityData: Record<string, unknown> | null;
}

interface ContextDomain {
  key: string;
  label: string;
  attrName: string;
}

// Attributes that are short/structural and should stay in the key-value table
const SHORT_ATTRS = new Set([
  'id', 'name', 'created-at', 'updated-at', 'provenance', 'source-uri',
  'iri', 'license', 'valid-from', 'valid-until', '_type',
  'content-hash', 'cache-path', 'format', 'mime-type', 'file-size', 'token-count',
]);

// Detect "context domain" attributes dynamically: any string attribute
// whose value is long (>100 chars) and whose name suggests prose content
function detectContextDomains(data: Record<string, unknown>): ContextDomain[] {
  const domains: ContextDomain[] = [];
  for (const [key, value] of Object.entries(data)) {
    if (SHORT_ATTRS.has(key)) continue;
    if (typeof value !== 'string') continue;
    if (value.length < 80) continue;
    // This is a long text attribute — show as a collapsible card
    const label = key
      .replace(/^(nbmem-|jhunt-|trec-|alh-|scilit-|slog-|sltrend-|dm-)/, '')
      .replace(/-/g, ' ')
      .replace(/\b\w/g, c => c.toUpperCase());
    domains.push({ key, label, attrName: key });
  }
  return domains;
}

function isUrl(value: string): boolean {
  try {
    const url = new URL(value);
    return url.protocol === 'http:' || url.protocol === 'https:';
  } catch {
    return false;
  }
}

function isDateLike(value: string): boolean {
  // Match ISO date patterns like 2026-05-04T12:00:00 or 2026-05-04
  return /^\d{4}-\d{2}-\d{2}(T\d{2}:\d{2}:\d{2})?/.test(value);
}

export default function AttributesTab({ entityData }: AttributesTabProps) {
  const [expandedDomains, setExpandedDomains] = useState<Set<string>>(new Set());

  const toggleDomain = (key: string) => {
    setExpandedDomains((prev) => {
      const next = new Set(prev);
      if (next.has(key)) {
        next.delete(key);
      } else {
        next.add(key);
      }
      return next;
    });
  };

  // Detect long text attributes to show as collapsible domain cards
  const contextDomains = entityData ? detectContextDomains(entityData) : [];
  const domainKeys = new Set(contextDomains.map(d => d.attrName));

  // Filter out standard display fields and domain fields from raw attributes table
  const attributeEntries = entityData
    ? Object.entries(entityData).filter(
        ([key, value]) =>
          !['id', 'name', 'description', '_type'].includes(key) &&
          !domainKeys.has(key) &&
          value != null
      )
    : [];

  const hasContextDomains = contextDomains.length > 0;

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 20 }}>
      {/* Context Domain Cards (person/operator-user only) */}
      {hasContextDomains && (
        <div>
          <div
            style={{
              fontFamily: 'JetBrains Mono, monospace',
              fontSize: 10,
              fontWeight: 500,
              letterSpacing: '0.08em',
              textTransform: 'uppercase',
              color: colors.fgFaint,
              marginBottom: 10,
            }}
          >
            DETAIL FIELDS
          </div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
            {contextDomains.map((domain) => {
              const value = entityData?.[domain.attrName] as string | undefined;
              if (!value || !value.trim()) return null;
              const isExpanded = expandedDomains.has(domain.key);
              const preview = value.length > 60 ? value.slice(0, 60) + '...' : value;

              return (
                <div
                  key={domain.key}
                  style={{
                    background: colors.panel,
                    border: `1px solid ${colors.borderDim}`,
                    borderRadius: 3,
                    padding: '12px 14px',
                  }}
                >
                  {/* Card header */}
                  <div
                    onClick={() => toggleDomain(domain.key)}
                    style={{
                      display: 'flex',
                      alignItems: 'center',
                      gap: 8,
                      cursor: 'pointer',
                      userSelect: 'none',
                    }}
                  >
                    <span
                      style={{
                        fontSize: 9,
                        color: colors.fgFaint,
                        display: 'inline-block',
                        transform: isExpanded ? 'rotate(90deg)' : 'rotate(0deg)',
                        transition: 'transform 0.15s',
                      }}
                    >
                      &#9654;
                    </span>
                    <span
                      style={{
                        fontFamily: 'JetBrains Mono, monospace',
                        fontSize: 10.5,
                        fontWeight: 500,
                        letterSpacing: '0.06em',
                        textTransform: 'uppercase',
                        color: colors.mint,
                      }}
                    >
                      {domain.label}
                    </span>
                  </div>

                  {/* Content */}
                  {isExpanded ? (
                    <div style={{ paddingLeft: 18, marginTop: 8 }}>
                      <MarkdownContent>{value}</MarkdownContent>
                    </div>
                  ) : (
                    <div
                      style={{
                        fontFamily: 'DM Sans, sans-serif',
                        fontSize: 12,
                        color: colors.fgFaint,
                        fontStyle: 'italic',
                        paddingLeft: 18,
                        marginTop: 4,
                      }}
                    >
                      {preview}
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        </div>
      )}

      {/* Attributes Table */}
      {attributeEntries.length > 0 && (
        <div>
          <div
            style={{
              fontFamily: 'JetBrains Mono, monospace',
              fontSize: 10,
              fontWeight: 500,
              letterSpacing: '0.08em',
              textTransform: 'uppercase',
              color: colors.fgFaint,
              marginBottom: 10,
            }}
          >
            ATTRIBUTES
          </div>
          <div
            style={{
              background: colors.panel,
              border: `1px solid ${colors.borderDim}`,
              borderRadius: 3,
              overflow: 'hidden',
            }}
          >
            {attributeEntries.map(([key, value], idx) => {
              const strValue = String(value);
              const isLast = idx === attributeEntries.length - 1;

              return (
                <div
                  key={key}
                  style={{
                    display: 'grid',
                    gridTemplateColumns: '160px 1fr',
                    borderBottom: isLast ? 'none' : `1px solid ${colors.borderDim}`,
                    alignItems: 'baseline',
                  }}
                >
                  {/* Key */}
                  <div
                    style={{
                      fontFamily: 'JetBrains Mono, monospace',
                      fontSize: 10.5,
                      color: colors.fgFaint,
                      padding: '8px 12px',
                      wordBreak: 'break-all',
                    }}
                  >
                    {key}
                  </div>

                  {/* Value */}
                  <div
                    style={{
                      fontFamily: 'DM Sans, sans-serif',
                      fontSize: 13,
                      padding: '8px 12px',
                      wordBreak: 'break-word',
                    }}
                  >
                    {isUrl(strValue) ? (
                      <a
                        href={strValue}
                        target="_blank"
                        rel="noopener noreferrer"
                        style={{
                          color: colors.teal,
                          textDecoration: 'underline',
                          textUnderlineOffset: 2,
                        }}
                      >
                        {strValue}
                      </a>
                    ) : isDateLike(strValue) ? (
                      <span style={{ color: colors.fgDim }}>
                        {formatRelativeDate(strValue)}
                        <span
                          style={{
                            marginLeft: 8,
                            fontSize: 10,
                            color: colors.fgFaint,
                            fontFamily: 'JetBrains Mono, monospace',
                          }}
                        >
                          {strValue}
                        </span>
                      </span>
                    ) : strValue.length > 100 || strValue.includes('\n') ? (
                      <MarkdownContent>{strValue}</MarkdownContent>
                    ) : (
                      <span style={{ color: colors.fgDim }}>{strValue}</span>
                    )}
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      )}

      {/* Empty state */}
      {attributeEntries.length === 0 && !hasContextDomains && (
        <div
          style={{
            color: colors.fgFaint,
            fontFamily: 'JetBrains Mono, monospace',
            fontSize: 11,
            padding: 24,
            textAlign: 'center',
          }}
        >
          No attributes found for this entity.
        </div>
      )}
    </div>
  );
}
