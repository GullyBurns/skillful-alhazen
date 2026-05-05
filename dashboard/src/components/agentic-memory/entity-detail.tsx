'use client';

import { useEffect, useState, useCallback } from 'react';
import {
  colors,
  getNamespace,
  getNamespaceColor,
  getNamespaceColorRgba,
  formatRelativeDate,
} from './tokens';
import AttributesTab from './attributes-tab';
import RelationsTab from './relations-tab';
import ClaimsTab from './claims-tab';
import EpisodesTab from './episodes-tab';
import MarkdownContent from './markdown';

interface EntityDetailProps {
  entityId: string;
  onSelectEntity: (id: string) => void;
  onBack: () => void;
}

interface EntityInfo {
  id: string;
  name: string;
  description?: string;
  'created-at'?: string;
}

interface NeighborNode {
  id: string;
  label: string;
  type: string;
}

interface NeighborEdge {
  source: string;
  target: string;
  relationType: string;
  sourceRole: string;
  targetRole: string;
}

interface Claim {
  id: string;
  content: string;
  'alh-fact-type'?: string;
  confidence?: number;
  'created-at'?: string;
}

type TabKey = 'data' | 'claims' | 'episodes';

export default function EntityDetail({ entityId, onSelectEntity, onBack }: EntityDetailProps) {
  const [entity, setEntity] = useState<EntityInfo | null>(null);
  const [entityType, setEntityType] = useState<string>('unknown');
  const [nodes, setNodes] = useState<NeighborNode[]>([]);
  const [edges, setEdges] = useState<NeighborEdge[]>([]);
  const [claims, setClaims] = useState<Claim[]>([]);
  const [loading, setLoading] = useState(true);
  const [neighborsLoading, setNeighborsLoading] = useState(true);
  const [activeTab, setActiveTab] = useState<TabKey>('data');

  const namespace = getNamespace(entityType);
  const nsColor = getNamespaceColor(namespace);

  const fetchData = useCallback(async () => {
    setLoading(true);
    setNeighborsLoading(true);
    try {
      // Fetch entity info and claims (fast), neighbors separately (slow — queries all relation types)
      const [entityRes, claimsRes] = await Promise.allSettled([
        fetch(`/api/agentic-memory/entity/${entityId}`),
        fetch(`/api/agentic-memory/facts?person=${entityId}`),
      ]);

      // Entity info
      if (entityRes.status === 'fulfilled' && entityRes.value.ok) {
        const data = await entityRes.value.json();
        if (data.success && data.entity) {
          setEntity(data.entity);
          if (data.entityType && data.entityType !== 'unknown') {
            setEntityType(data.entityType);
          } else if (data.entity._type && data.entity._type !== 'unknown') {
            setEntityType(data.entity._type);
          }
        }
      }

      // Claims
      if (claimsRes.status === 'fulfilled' && claimsRes.value.ok) {
        const data = await claimsRes.value.json();
        setClaims(Array.isArray(data.claims) ? data.claims : []);
      }

      // Context fetch is used by AttributesTab to show context domains if available
      // No type inference needed — entity API now returns the correct type
    } catch (err) {
      console.error('Failed to fetch entity detail:', err);
    } finally {
      setLoading(false);
    }

    // Fetch neighbors in background (can be slow with dynamic relation discovery)
    try {
      const neighborsRes = await fetch(`/api/agentic-memory/entity/${entityId}/neighbors`);
      if (neighborsRes.ok) {
        const data = await neighborsRes.json();
        setNodes(Array.isArray(data.nodes) ? data.nodes : []);
        setEdges(Array.isArray(data.edges) ? data.edges : []);
      }
    } catch {
      // neighbors are supplementary
    } finally {
      setNeighborsLoading(false);
    }
  }, [entityId, entityType]);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  const tabs: { key: TabKey; label: string; count?: number }[] = [
    { key: 'data', label: 'DATA' },
    { key: 'claims', label: 'CLAIMS', count: claims.length },
    { key: 'episodes', label: 'EPISODES' },
  ];

  if (loading) {
    return (
      <div style={{ padding: 32, color: colors.fgFaint, fontFamily: 'JetBrains Mono, monospace', fontSize: 12 }}>
        Loading entity...
      </div>
    );
  }

  if (!entity) {
    return (
      <div style={{ padding: 32, color: colors.fgFaint, fontFamily: 'JetBrains Mono, monospace', fontSize: 12 }}>
        Entity not found.
      </div>
    );
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100%', overflow: 'hidden' }}>
      {/* Breadcrumb bar */}
      <div
        style={{
          padding: '8px 16px',
          borderBottom: `1px solid ${colors.borderDim}`,
          background: getNamespaceColorRgba(namespace, 0.04),
          display: 'flex',
          alignItems: 'center',
          gap: 8,
          fontFamily: 'JetBrains Mono, monospace',
          fontSize: 11,
        }}
      >
        <span
          onClick={onBack}
          style={{
            color: colors.fgFaint,
            cursor: 'pointer',
            userSelect: 'none',
          }}
          onMouseEnter={(e) => (e.currentTarget.style.color = nsColor)}
          onMouseLeave={(e) => (e.currentTarget.style.color = colors.fgFaint)}
        >
          &larr; back
        </span>
        <span style={{ color: colors.fgFaint }}>/</span>
        <span style={{ color: nsColor }}>{namespace.toUpperCase()}</span>
        <span style={{ color: colors.fgFaint }}>/</span>
        <span style={{ color: colors.fg }}>{entity.name || entityId}</span>
      </div>

      {/* Header */}
      <div style={{ padding: '20px 24px 16px', borderBottom: `1px solid ${colors.borderDim}` }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: 8 }}>
          <h1
            style={{
              fontFamily: 'DM Serif Display, serif',
              fontSize: 24,
              fontWeight: 400,
              color: colors.fg,
              margin: 0,
              lineHeight: 1.2,
            }}
          >
            {entity.name || 'Unnamed'}
          </h1>
          <span
            style={{
              fontFamily: 'JetBrains Mono, monospace',
              fontSize: 9,
              fontWeight: 600,
              letterSpacing: '0.08em',
              color: nsColor,
              background: getNamespaceColorRgba(namespace, 0.12),
              border: `1px solid ${getNamespaceColorRgba(namespace, 0.25)}`,
              borderRadius: 3,
              padding: '2px 7px',
              textTransform: 'uppercase',
            }}
          >
            {entityType !== 'unknown' ? entityType : 'entity'}
          </span>
        </div>
        <div
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: 16,
            fontFamily: 'JetBrains Mono, monospace',
            fontSize: 10.5,
            color: colors.fgFaint,
          }}
        >
          <span style={{ userSelect: 'all' }}>{entityId}</span>
          {entity['created-at'] && (
            <>
              <span style={{ color: colors.borderDim }}>|</span>
              <span>created {formatRelativeDate(entity['created-at'])}</span>
            </>
          )}
        </div>
        {entity.description && (
          <div style={{ marginTop: 10 }}>
            <MarkdownContent>{String(entity.description)}</MarkdownContent>
          </div>
        )}
      </div>

      {/* Tab bar */}
      <div
        style={{
          display: 'flex',
          gap: 0,
          borderBottom: `1px solid ${colors.borderDim}`,
          padding: '0 24px',
        }}
      >
        {tabs.map((tab) => {
          const isActive = activeTab === tab.key;
          return (
            <button
              key={tab.key}
              onClick={() => setActiveTab(tab.key)}
              style={{
                fontFamily: 'JetBrains Mono, monospace',
                fontSize: 11,
                fontWeight: 500,
                letterSpacing: '0.06em',
                textTransform: 'uppercase',
                color: isActive ? colors.teal : colors.fgFaint,
                background: 'none',
                border: 'none',
                borderBottom: isActive ? `2px solid ${colors.teal}` : '2px solid transparent',
                padding: '10px 16px 8px',
                cursor: 'pointer',
                transition: 'color 0.15s, border-color 0.15s',
              }}
              onMouseEnter={(e) => {
                if (!isActive) e.currentTarget.style.color = colors.fgDim;
              }}
              onMouseLeave={(e) => {
                if (!isActive) e.currentTarget.style.color = colors.fgFaint;
              }}
            >
              {tab.label}
              {tab.count !== undefined && (
                <span
                  style={{
                    marginLeft: 6,
                    fontSize: 9,
                    color: isActive ? colors.teal : colors.fgFaint,
                    opacity: 0.7,
                  }}
                >
                  {tab.count}
                </span>
              )}
            </button>
          );
        })}
      </div>

      {/* Tab content */}
      <div style={{ flex: 1, overflow: 'auto', padding: '16px 24px' }}>
        {activeTab === 'data' && (
          <>
            <AttributesTab entityData={entity as unknown as Record<string, unknown>} />
            <div style={{ marginTop: 24 }}>
              <RelationsTab
                entityId={entityId}
                nodes={nodes}
                edges={edges}
                onSelectEntity={onSelectEntity}
              />
              {neighborsLoading && edges.length === 0 && (
                <div style={{ padding: 16, color: colors.fgFaint, fontFamily: 'JetBrains Mono, monospace', fontSize: 11 }}>
                  Loading relations...
                </div>
              )}
            </div>
          </>
        )}
        {activeTab === 'claims' && <ClaimsTab claims={claims} onSelectEntity={onSelectEntity} />}
        {activeTab === 'episodes' && (
          <EpisodesTab entityId={entityId} onSelectEntity={onSelectEntity} />
        )}
      </div>
    </div>
  );
}
