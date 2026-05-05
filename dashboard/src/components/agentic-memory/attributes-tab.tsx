'use client';

import { useEffect, useState, useCallback } from 'react';
import { colors, formatRelativeDate } from './tokens';
import MarkdownContent from './markdown';

interface AttributesTabProps {
  entityId: string;
  entityData: Record<string, unknown> | null;
}

interface ContextDomain {
  key: string;
  label: string;
  attrName: string;
}

const CONTEXT_DOMAINS: ContextDomain[] = [
  { key: 'identity', label: 'Identity', attrName: 'nbmem-identity-summary' },
  { key: 'role', label: 'Role', attrName: 'nbmem-role-description' },
  { key: 'goals', label: 'Goals', attrName: 'nbmem-goals-summary' },
  { key: 'preferences', label: 'Preferences', attrName: 'nbmem-preferences-summary' },
  { key: 'expertise', label: 'Expertise', attrName: 'nbmem-domain-expertise' },
  { key: 'communication', label: 'Communication Style', attrName: 'nbmem-communication-style' },
];

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

export default function AttributesTab({ entityId, entityData }: AttributesTabProps) {
  const [contextData, setContextData] = useState<Record<string, string> | null>(null);
  const [expandedDomains, setExpandedDomains] = useState<Set<string>>(new Set());
  const [loadingContext, setLoadingContext] = useState(true);

  const fetchContext = useCallback(async () => {
    setLoadingContext(true);
    try {
      const res = await fetch(`/api/agentic-memory/context?person=${entityId}`);
      if (res.ok) {
        const data = await res.json();
        if (data.success && data.context && typeof data.context === 'object') {
          setContextData(data.context);
        }
      }
    } catch {
      // Not a person entity or context unavailable -- that's fine
    } finally {
      setLoadingContext(false);
    }
  }, [entityId]);

  useEffect(() => {
    fetchContext();
  }, [fetchContext]);

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

  // Filter out standard display fields from raw attributes
  const attributeEntries = entityData
    ? Object.entries(entityData).filter(
        ([key]) => !['id', 'name', 'description'].includes(key) && entityData[key] != null
      )
    : [];

  const hasContextDomains =
    contextData &&
    CONTEXT_DOMAINS.some((d) => contextData[d.attrName] && contextData[d.attrName].trim());

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 20 }}>
      {/* Context Domain Cards (person/operator-user only) */}
      {!loadingContext && hasContextDomains && (
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
            CONTEXT DOMAINS
          </div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
            {CONTEXT_DOMAINS.map((domain) => {
              const value = contextData?.[domain.attrName];
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
      {attributeEntries.length === 0 && !hasContextDomains && !loadingContext && (
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
