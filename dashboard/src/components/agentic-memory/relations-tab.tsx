'use client';

import React from 'react';
import { colors, getNamespace, getNamespaceColor, getNamespaceColorRgba } from './tokens';

interface RelationsTabProps {
  nodes: Array<{ id: string; label: string; type: string }>;
  edges: Array<{ source: string; target: string; relationType: string; sourceRole: string; targetRole: string }>;
  entityId: string;
  onSelectEntity: (id: string) => void;
}

export default function RelationsTab({ nodes, edges, entityId, onSelectEntity }: RelationsTabProps) {
  // Group edges by relationType
  const grouped = edges.reduce<Record<string, typeof edges>>((acc, edge) => {
    if (!acc[edge.relationType]) acc[edge.relationType] = [];
    acc[edge.relationType].push(edge);
    return acc;
  }, {});

  const nodeMap = new Map(nodes.map(n => [n.id, n]));

  if (Object.keys(grouped).length === 0) {
    return (
      <div style={{ textAlign: 'center', color: colors.fgFaint, padding: '40px 0', fontSize: 13 }}>
        No relations found for this entity
      </div>
    );
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 24 }}>
      {Object.entries(grouped).map(([relationType, relEdges]) => {
        const ns = getNamespace(relationType);
        const nsColor = getNamespaceColor(ns);
        const sampleEdge = relEdges[0];

        return (
          <div key={relationType}>
            {/* Section header */}
            <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 10 }}>
              <div style={{ width: 14, height: 2, backgroundColor: nsColor, borderRadius: 1 }} />
              <span style={{
                fontFamily: "'JetBrains Mono', monospace",
                fontSize: 10,
                textTransform: 'uppercase',
                color: nsColor,
                letterSpacing: '0.8px',
              }}>
                {relationType}
              </span>
              <span style={{
                fontFamily: "'JetBrains Mono', monospace",
                fontSize: 9,
                color: colors.fgFaint,
              }}>
                {sampleEdge.sourceRole} &rarr; {sampleEdge.targetRole}
              </span>
              <div style={{ flex: 1, height: 1, backgroundColor: colors.borderDim }} />
              <span style={{
                fontFamily: "'JetBrains Mono', monospace",
                fontSize: 9,
                color: colors.fgFaint,
              }}>
                {relEdges.length}
              </span>
            </div>

            {/* Edge rows */}
            <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
              {relEdges.map((edge, idx) => {
                const neighborId = edge.source === entityId ? edge.target : edge.source;
                const neighbor = nodeMap.get(neighborId);
                if (!neighbor) return null;

                const neighborNs = getNamespace(neighbor.type);
                const neighborColor = getNamespaceColor(neighborNs);

                return (
                  <div
                    key={`${relationType}-${idx}`}
                    onClick={() => onSelectEntity(neighborId)}
                    style={{
                      background: colors.panel,
                      border: `1px solid ${colors.borderDim}`,
                      borderRadius: 3,
                      padding: '10px 14px',
                      display: 'flex',
                      flexDirection: 'row',
                      alignItems: 'center',
                      gap: 12,
                      cursor: 'pointer',
                      transition: 'border-color 0.15s ease',
                    }}
                    onMouseEnter={e => { (e.currentTarget as HTMLDivElement).style.borderColor = colors.borderHi; }}
                    onMouseLeave={e => { (e.currentTarget as HTMLDivElement).style.borderColor = colors.borderDim; }}
                  >
                    {/* Namespace dot */}
                    <div style={{
                      width: 8,
                      height: 8,
                      borderRadius: 1,
                      backgroundColor: neighborColor,
                      opacity: 0.6,
                      flexShrink: 0,
                    }} />

                    {/* Name + type */}
                    <div style={{ flex: 1, minWidth: 0 }}>
                      <div style={{ fontSize: 12.5, color: colors.fg, whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
                        {neighbor.label}
                      </div>
                      <div style={{
                        fontFamily: "'JetBrains Mono', monospace",
                        fontSize: 10,
                        color: colors.fgFaint,
                        marginTop: 2,
                      }}>
                        {neighbor.type}
                      </div>
                    </div>

                    {/* ID */}
                    <div style={{
                      fontFamily: "'JetBrains Mono', monospace",
                      fontSize: 10,
                      color: colors.fgFaint,
                      flexShrink: 0,
                      whiteSpace: 'nowrap',
                    }}>
                      {neighborId}
                    </div>

                    {/* Chevron */}
                    <div style={{ color: colors.fgFaint, fontSize: 12, flexShrink: 0 }}>
                      &gt;
                    </div>
                  </div>
                );
              })}
            </div>
          </div>
        );
      })}
    </div>
  );
}
