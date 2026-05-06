'use client';

import { useState, useEffect, useMemo } from 'react';
import {
  colors,
  namespaceColors,
  namespaceBadges,
  getNamespace,
  getNamespaceColor,
  getNamespaceColorRgba,
  formatRelativeDate,
} from './tokens';

interface OverviewPanelProps {
  onSelectNamespace: (ns: string) => void;
  onSelectEntity: (id: string) => void;
}

interface EntityTypeInfo {
  parent?: string;
  owns?: string[];
  plays?: string[];
  subtypes?: string[];
  instance_count?: number;
}

interface RelationTypeInfo {
  roles?: string[];
  owns?: string[];
}

interface Episode {
  id: string;
  content: string;
  'alh-source-skill'?: string;
  'created-at'?: string;
}

interface NamespaceStats {
  namespace: string;
  totalInstances: number;
  entityTypeCount: number;
  relationCount: number;
}

const SKILL_TO_NAMESPACE: Record<string, string> = {
  'tech-recon': 'trec',
  'jobhunt': 'jhunt',
  'agentic-memory': 'nbmem',
  'typedb-notebook': 'alh',
  'scientific-literature': 'scilit',
  'literature-trends': 'sltrend',
  'dismech': 'dm',
  'web-search': 'alh',
  'skilllog': 'slog',
};

function skillToNamespace(skill: string | undefined): string {
  if (!skill) return 'unknown';
  return SKILL_TO_NAMESPACE[skill] ?? 'unknown';
}

export default function OverviewPanel({ onSelectNamespace, onSelectEntity }: OverviewPanelProps) {
  const [entities, setEntities] = useState<Record<string, EntityTypeInfo>>({});
  const [relations, setRelations] = useState<Record<string, RelationTypeInfo>>({});
  const [episodes, setEpisodes] = useState<Episode[]>([]);
  const [loading, setLoading] = useState(true);
  const [hoveredNs, setHoveredNs] = useState<string | null>(null);

  useEffect(() => {
    const fetchData = async () => {
      setLoading(true);
      try {
        const [schemaRes, episodesRes] = await Promise.all([
          fetch('/api/agentic-memory/schema?full=true'),
          fetch('/api/agentic-memory/episodes'),
        ]);
        if (schemaRes.ok) {
          const data = await schemaRes.json();
          setEntities(data.entities ?? {});
          setRelations(data.relations ?? {});
        }
        if (episodesRes.ok) {
          const data = await episodesRes.json();
          // API may return array directly or { episodes: [...] }
          setEpisodes(Array.isArray(data) ? data : (data.episodes ?? []));
        }
      } catch {
        // silently handle
      } finally {
        setLoading(false);
      }
    };
    fetchData();
  }, []);

  const namespaceStats = useMemo<NamespaceStats[]>(() => {
    const grouped: Record<string, { instances: number; entityTypes: Set<string>; relations: Set<string> }> = {};

    for (const [typeName, info] of Object.entries(entities)) {
      const ns = getNamespace(typeName);
      if (ns === 'unknown') continue;
      if (!grouped[ns]) {
        grouped[ns] = { instances: 0, entityTypes: new Set(), relations: new Set() };
      }
      grouped[ns].entityTypes.add(typeName);
      grouped[ns].instances += info.instance_count ?? 0;
    }

    for (const relName of Object.keys(relations)) {
      const ns = getNamespace(relName);
      if (!grouped[ns]) {
        grouped[ns] = { instances: 0, entityTypes: new Set(), relations: new Set() };
      }
      grouped[ns].relations.add(relName);
    }

    return Object.entries(grouped)
      .map(([namespace, stats]) => ({
        namespace,
        totalInstances: stats.instances,
        entityTypeCount: stats.entityTypes.size,
        relationCount: stats.relations.size,
      }))
      .sort((a, b) => b.totalInstances - a.totalInstances);
  }, [entities, relations]);

  const totalEntities = namespaceStats.reduce((sum, ns) => sum + ns.totalInstances, 0);
  const maxInstances = Math.max(1, ...namespaceStats.map((ns) => ns.totalInstances));

  const lastActivity = useMemo(() => {
    const dates = episodes
      .map((e) => e['created-at'])
      .filter(Boolean)
      .sort()
      .reverse();
    return dates[0] ? formatRelativeDate(dates[0]) : 'unknown';
  }, [episodes]);

  if (loading) {
    return (
      <div style={{ padding: 24, color: colors.fgFaint, fontFamily: 'JetBrains Mono, monospace', fontSize: 11 }}>
        Loading...
      </div>
    );
  }

  return (
    <div style={{ padding: 24, display: 'flex', flexDirection: 'column', gap: 24 }}>
      {/* Title area */}
      <div>
        <div
          style={{
            fontFamily: 'DM Serif Display, serif',
            fontSize: 24,
            color: colors.fg,
            marginBottom: 4,
          }}
        >
          Knowledge Graph
        </div>
        <div
          style={{
            fontFamily: 'JetBrains Mono, monospace',
            fontSize: 11,
            color: colors.fgFaint,
          }}
        >
          {totalEntities.toLocaleString()} entities &middot; last activity {lastActivity}
        </div>
      </div>

      {/* Namespace cards section */}
      <div>
        <div
          style={{
            fontFamily: 'JetBrains Mono, monospace',
            fontSize: 10,
            color: colors.fgFaint,
            textTransform: 'uppercase',
            letterSpacing: '1.4px',
            marginBottom: 10,
          }}
        >
          Namespaces
        </div>
        <div
          style={{
            display: 'grid',
            gridTemplateColumns: 'repeat(3, 1fr)',
            gap: 10,
          }}
        >
          {namespaceStats.map((ns) => {
            const nsColor = getNamespaceColor(ns.namespace);
            const badge = namespaceBadges[ns.namespace] ?? 'LEGACY';
            const isEmpty = ns.totalInstances === 0;
            const isHovered = hoveredNs === ns.namespace;
            const borderAlpha = isHovered ? 0.42 : 0.18;
            const densityWidth = (ns.totalInstances / maxInstances) * 100;

            return (
              <div
                key={ns.namespace}
                onClick={() => onSelectNamespace(ns.namespace)}
                onMouseEnter={() => setHoveredNs(ns.namespace)}
                onMouseLeave={() => setHoveredNs(null)}
                style={{
                  background: colors.panel,
                  border: `1px solid ${getNamespaceColorRgba(ns.namespace, borderAlpha)}`,
                  borderRadius: 3,
                  padding: 14,
                  cursor: 'pointer',
                  opacity: isEmpty ? 0.6 : 1,
                  transition: 'border-color 0.15s ease',
                }}
              >
                {/* Header row */}
                <div
                  style={{
                    display: 'flex',
                    justifyContent: 'space-between',
                    alignItems: 'center',
                    marginBottom: 8,
                  }}
                >
                  <span
                    style={{
                      fontFamily: 'JetBrains Mono, monospace',
                      fontSize: 11,
                      fontWeight: 700,
                      color: nsColor,
                    }}
                  >
                    {ns.namespace}
                  </span>
                  <span
                    style={{
                      fontFamily: 'JetBrains Mono, monospace',
                      fontSize: 9,
                      color: colors.fgFaint,
                    }}
                  >
                    {badge}
                  </span>
                </div>

                {/* Large instance count */}
                <div
                  style={{
                    fontSize: 22,
                    color: colors.fg,
                    fontFamily: 'DM Sans, sans-serif',
                    marginBottom: 4,
                  }}
                >
                  {ns.totalInstances.toLocaleString()}
                </div>

                {/* Entity types / relations */}
                <div
                  style={{
                    fontFamily: 'DM Sans, sans-serif',
                    fontSize: 10.5,
                    color: colors.fgDim,
                    marginBottom: 10,
                  }}
                >
                  {ns.entityTypeCount} entity types &middot; {ns.relationCount} relations
                </div>

                {/* Density bar */}
                <div
                  style={{
                    height: 3,
                    background: colors.borderDim,
                    borderRadius: 1.5,
                    overflow: 'hidden',
                  }}
                >
                  <div
                    style={{
                      height: '100%',
                      width: `${densityWidth}%`,
                      background: getNamespaceColorRgba(ns.namespace, 0.6),
                      borderRadius: 1.5,
                      transition: 'width 0.3s ease',
                    }}
                  />
                </div>
              </div>
            );
          })}
        </div>
      </div>

      {/* Activity feed section */}
      <div>
        <div
          style={{
            fontFamily: 'JetBrains Mono, monospace',
            fontSize: 10,
            color: colors.fgFaint,
            textTransform: 'uppercase',
            letterSpacing: '1.4px',
            marginBottom: 10,
          }}
        >
          Recent Agent Activity
        </div>
        <div
          style={{
            border: `1px solid ${colors.borderDim}`,
            borderRadius: 3,
            overflow: 'hidden',
          }}
        >
          {episodes.length === 0 ? (
            <div
              style={{
                padding: 16,
                fontFamily: 'DM Sans, sans-serif',
                fontSize: 12,
                color: colors.fgFaint,
                textAlign: 'center',
              }}
            >
              No recent activity
            </div>
          ) : (
            episodes.map((episode, idx) => {
              const lines = (episode.content ?? '').split('\n').filter(Boolean);
              const title = lines[0] ?? '';
              const snippet = lines[1] ?? '';
              const ns = skillToNamespace(episode['alh-source-skill']);
              const dotColor = getNamespaceColor(ns);
              const timestamp = episode['created-at']
                ? formatRelativeDate(episode['created-at'])
                : '';

              return (
                <div
                  key={episode.id}
                  onClick={() => onSelectEntity(episode.id)}
                  style={{
                    display: 'flex',
                    alignItems: 'flex-start',
                    gap: 10,
                    padding: '10px 14px',
                    cursor: 'pointer',
                    borderBottom:
                      idx < episodes.length - 1
                        ? `1px solid ${colors.borderDim}`
                        : 'none',
                  }}
                >
                  {/* Namespace dot */}
                  <div
                    style={{
                      width: 6,
                      height: 6,
                      borderRadius: '50%',
                      background: dotColor,
                      marginTop: 5,
                      flexShrink: 0,
                    }}
                  />

                  {/* Content */}
                  <div style={{ flex: 1, minWidth: 0 }}>
                    <div
                      style={{
                        fontFamily: 'DM Sans, sans-serif',
                        fontSize: 12,
                        color: colors.fg,
                        whiteSpace: 'nowrap',
                        overflow: 'hidden',
                        textOverflow: 'ellipsis',
                      }}
                    >
                      {title}
                    </div>
                    {snippet && (
                      <div
                        style={{
                          fontFamily: 'DM Sans, sans-serif',
                          fontSize: 10.5,
                          color: colors.fgDim,
                          whiteSpace: 'nowrap',
                          overflow: 'hidden',
                          textOverflow: 'ellipsis',
                          marginTop: 2,
                        }}
                      >
                        {snippet}
                      </div>
                    )}
                  </div>

                  {/* Timestamp */}
                  {timestamp && (
                    <div
                      style={{
                        fontFamily: 'JetBrains Mono, monospace',
                        fontSize: 10,
                        color: colors.fgFaint,
                        whiteSpace: 'nowrap',
                        flexShrink: 0,
                        marginTop: 1,
                      }}
                    >
                      {timestamp}
                    </div>
                  )}
                </div>
              );
            })
          )}
        </div>
      </div>
    </div>
  );
}
