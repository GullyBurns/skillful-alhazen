'use client';

import { useState, useEffect, useMemo } from 'react';
import {
  colors,
  namespaceBadges,
  getNamespace,
  getNamespaceColor,
  getNamespaceColorRgba,
  stripPrefix,
} from './tokens';

interface SchemaEntity {
  parent?: string;
  subtypes?: string[];
  instance_count?: number;
  owns?: string[];
}

interface SchemaResponse {
  success: boolean;
  source: string;
  entities: Record<string, SchemaEntity>;
  relations: Record<string, { roles?: string[] }>;
}

interface SchemaTreeProps {
  onSelectType: (typeName: string) => void;
  onSelectNone: () => void;
  selectedType: string | null;
  expandNamespace?: string | null;
}

interface NamespaceGroup {
  namespace: string;
  types: Array<{ name: string; instanceCount: number }>;
  totalInstances: number;
}

export default function SchemaTree({
  onSelectType,
  onSelectNone,
  selectedType,
  expandNamespace,
}: SchemaTreeProps) {
  const [schema, setSchema] = useState<SchemaResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [expandedNamespaces, setExpandedNamespaces] = useState<Set<string>>(new Set());
  const [searchQuery, setSearchQuery] = useState('');

  // Fetch schema on mount
  useEffect(() => {
    fetch('/api/agentic-memory/schema?full=true')
      .then((res) => {
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        return res.json();
      })
      .then((data: SchemaResponse) => {
        setSchema(data);
        setLoading(false);
      })
      .catch((err) => {
        setError(err.message);
        setLoading(false);
      });
  }, []);

  // Auto-expand namespace when expandNamespace prop changes
  useEffect(() => {
    if (expandNamespace) {
      setExpandedNamespaces((prev) => {
        const next = new Set(prev);
        next.add(expandNamespace);
        return next;
      });
    }
  }, [expandNamespace]);

  // Group entities by namespace
  const namespaceGroups = useMemo<NamespaceGroup[]>(() => {
    if (!schema) return [];

    const groups: Record<string, NamespaceGroup> = {};

    for (const [typeName, entity] of Object.entries(schema.entities)) {
      const ns = getNamespace(typeName);
      if (ns === 'unknown') continue;
      if (!groups[ns]) {
        groups[ns] = { namespace: ns, types: [], totalInstances: 0 };
      }
      const count = entity.instance_count ?? 0;
      groups[ns].types.push({ name: typeName, instanceCount: count });
      // Only sum direct instances for types in this namespace
      groups[ns].totalInstances += count;
    }

    // Sort types within each namespace
    for (const group of Object.values(groups)) {
      group.types.sort((a, b) => a.name.localeCompare(b.name));
    }

    // Sort namespaces: known ones first (by badge priority), then unknown
    const badgeOrder: Record<string, number> = { CORE: 0, OS: 1, SKILL: 2, LEGACY: 3 };
    return Object.values(groups).sort((a, b) => {
      const aBadge = namespaceBadges[a.namespace] ?? 'LEGACY';
      const bBadge = namespaceBadges[b.namespace] ?? 'LEGACY';
      const orderDiff = (badgeOrder[aBadge] ?? 9) - (badgeOrder[bBadge] ?? 9);
      if (orderDiff !== 0) return orderDiff;
      return a.namespace.localeCompare(b.namespace);
    });
  }, [schema]);

  // Filter by search
  const filteredGroups = useMemo(() => {
    if (!searchQuery.trim()) return namespaceGroups;
    const q = searchQuery.toLowerCase();
    return namespaceGroups
      .map((group) => ({
        ...group,
        types: group.types.filter((t) => t.name.toLowerCase().includes(q)),
      }))
      .filter((group) => group.types.length > 0);
  }, [namespaceGroups, searchQuery]);

  // Totals
  const totalEntities = useMemo(() => {
    if (!schema) return 0;
    return Object.values(schema.entities).reduce(
      (sum, e) => sum + (e.instance_count ?? 0),
      0
    );
  }, [schema]);

  const totalNamespaces = namespaceGroups.length;

  const toggleNamespace = (ns: string) => {
    setExpandedNamespaces((prev) => {
      const next = new Set(prev);
      if (next.has(ns)) {
        next.delete(ns);
      } else {
        next.add(ns);
      }
      return next;
    });
  };

  if (loading) {
    return (
      <div
        style={{
          padding: '24px 16px',
          color: colors.fgDim,
          fontFamily: "'DM Sans', sans-serif",
          fontSize: 13,
        }}
      >
        Loading schema...
      </div>
    );
  }

  if (error) {
    return (
      <div
        style={{
          padding: '24px 16px',
          color: colors.rust,
          fontFamily: "'DM Sans', sans-serif",
          fontSize: 13,
        }}
      >
        Error: {error}
      </div>
    );
  }

  return (
    <div
      style={{
        display: 'flex',
        flexDirection: 'column',
        height: '100%',
        background: colors.bgRaised,
        borderRight: `1px solid ${colors.border}`,
        overflow: 'hidden',
      }}
    >
      {/* Header */}
      <div
        style={{
          padding: '20px 16px 12px',
          borderBottom: `1px solid ${colors.borderDim}`,
        }}
      >
        <h2
          style={{
            margin: 0,
            fontFamily: "'DM Serif Display', serif",
            fontSize: 18,
            fontWeight: 400,
            color: colors.fg,
            letterSpacing: '0.02em',
          }}
        >
          Alhazen Notebook
        </h2>
        <div
          style={{
            marginTop: 6,
            fontFamily: "'JetBrains Mono', monospace",
            fontSize: 11,
            color: colors.fgDim,
            display: 'flex',
            gap: 12,
          }}
        >
          <span>
            {totalEntities.toLocaleString()} entities
          </span>
          <span style={{ color: colors.fgFaint }}>|</span>
          <span>
            {totalNamespaces} namespaces
          </span>
        </div>
      </div>

      {/* Search */}
      <div style={{ padding: '10px 16px 6px' }}>
        <input
          type="text"
          placeholder="Filter types..."
          value={searchQuery}
          onChange={(e) => setSearchQuery(e.target.value)}
          style={{
            width: '100%',
            padding: '6px 10px',
            background: colors.bg,
            border: `1px solid ${colors.border}`,
            borderRadius: 4,
            color: colors.fg,
            fontFamily: "'DM Sans', sans-serif",
            fontSize: 12,
            outline: 'none',
            boxSizing: 'border-box',
          }}
          onFocus={(e) => {
            e.currentTarget.style.borderColor = colors.borderHi;
          }}
          onBlur={(e) => {
            e.currentTarget.style.borderColor = colors.border;
          }}
        />
      </div>

      {/* Tree */}
      <div
        style={{
          flex: 1,
          overflowY: 'auto',
          padding: '4px 0',
        }}
      >
        {filteredGroups.map((group) => {
          const isExpanded = expandedNamespaces.has(group.namespace);
          const nsColor = getNamespaceColor(group.namespace);
          const badge = namespaceBadges[group.namespace] ?? 'LEGACY';

          return (
            <div key={group.namespace}>
              {/* Namespace header row */}
              <div
                onClick={() => toggleNamespace(group.namespace)}
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: 6,
                  padding: '6px 16px',
                  cursor: 'pointer',
                  userSelect: 'none',
                  transition: 'background 0.12s',
                }}
                onMouseEnter={(e) => {
                  e.currentTarget.style.background = getNamespaceColorRgba(
                    group.namespace,
                    0.06
                  );
                }}
                onMouseLeave={(e) => {
                  e.currentTarget.style.background = 'transparent';
                }}
              >
                {/* Triangle */}
                <span
                  style={{
                    display: 'inline-block',
                    width: 10,
                    fontSize: 9,
                    color: colors.fgFaint,
                    transform: isExpanded ? 'rotate(90deg)' : 'rotate(0deg)',
                    transition: 'transform 0.15s',
                    flexShrink: 0,
                  }}
                >
                  &#9654;
                </span>

                {/* Namespace label */}
                <span
                  style={{
                    fontFamily: "'JetBrains Mono', monospace",
                    fontSize: 12,
                    fontWeight: 600,
                    color: nsColor,
                    letterSpacing: '0.04em',
                  }}
                >
                  {group.namespace}
                </span>

                {/* Badge */}
                <span
                  style={{
                    fontFamily: "'JetBrains Mono', monospace",
                    fontSize: 9,
                    color: nsColor,
                    opacity: 0.6,
                    padding: '1px 4px',
                    border: `1px solid ${getNamespaceColorRgba(group.namespace, 0.25)}`,
                    borderRadius: 3,
                    letterSpacing: '0.06em',
                  }}
                >
                  {badge}
                </span>

                {/* Spacer */}
                <span style={{ flex: 1 }} />

                {/* Aggregate count */}
                <span
                  style={{
                    fontFamily: "'JetBrains Mono', monospace",
                    fontSize: 10,
                    color: colors.fgFaint,
                  }}
                >
                  {group.totalInstances.toLocaleString()}
                </span>
              </div>

              {/* Entity type rows */}
              {isExpanded &&
                group.types.map((typeInfo) => {
                  const isSelected = selectedType === typeInfo.name;
                  return (
                    <div
                      key={typeInfo.name}
                      onClick={() => {
                        if (isSelected) {
                          onSelectNone();
                        } else {
                          onSelectType(typeInfo.name);
                        }
                      }}
                      style={{
                        display: 'flex',
                        alignItems: 'center',
                        gap: 8,
                        padding: '4px 16px 4px 36px',
                        cursor: 'pointer',
                        userSelect: 'none',
                        background: isSelected
                          ? getNamespaceColorRgba(group.namespace, 0.12)
                          : 'transparent',
                        borderLeft: isSelected
                          ? `2px solid ${nsColor}`
                          : '2px solid transparent',
                        transition: 'background 0.1s',
                      }}
                      onMouseEnter={(e) => {
                        if (!isSelected) {
                          e.currentTarget.style.background = getNamespaceColorRgba(
                            group.namespace,
                            0.06
                          );
                        }
                      }}
                      onMouseLeave={(e) => {
                        if (!isSelected) {
                          e.currentTarget.style.background = 'transparent';
                        }
                      }}
                    >
                      {/* Colored dot */}
                      <span
                        style={{
                          width: 6,
                          height: 6,
                          borderRadius: '50%',
                          background: nsColor,
                          opacity: typeInfo.instanceCount > 0 ? 1 : 0.3,
                          flexShrink: 0,
                        }}
                      />

                      {/* Type name (stripped) */}
                      <span
                        style={{
                          fontFamily: "'DM Sans', sans-serif",
                          fontSize: 12,
                          color: isSelected ? colors.fg : colors.fgDim,
                          flex: 1,
                          overflow: 'hidden',
                          textOverflow: 'ellipsis',
                          whiteSpace: 'nowrap',
                        }}
                      >
                        {stripPrefix(typeInfo.name)}
                      </span>

                      {/* Instance count */}
                      {typeInfo.instanceCount > 0 && (
                        <span
                          style={{
                            fontFamily: "'JetBrains Mono', monospace",
                            fontSize: 10,
                            color: colors.fgFaint,
                            flexShrink: 0,
                          }}
                        >
                          {typeInfo.instanceCount.toLocaleString()}
                        </span>
                      )}
                    </div>
                  );
                })}
            </div>
          );
        })}

        {filteredGroups.length === 0 && searchQuery && (
          <div
            style={{
              padding: '16px',
              color: colors.fgFaint,
              fontFamily: "'DM Sans', sans-serif",
              fontSize: 12,
              textAlign: 'center',
            }}
          >
            No types matching "{searchQuery}"
          </div>
        )}
      </div>
    </div>
  );
}
