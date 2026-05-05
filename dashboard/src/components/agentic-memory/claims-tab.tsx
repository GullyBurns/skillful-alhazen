'use client';

import React, { useState } from 'react';
import { colors, formatRelativeDate } from './tokens';
import MarkdownContent from './markdown';

interface ClaimsTabProps {
  claims: Array<{
    id: string;
    content: string;
    'alh-fact-type'?: string;
    confidence?: number;
    'created-at'?: string;
    'valid-until'?: string;
  }>;
  onSelectEntity: (id: string) => void;
}

const factTypeColors: Record<string, string> = {
  knowledge: '#b8c84a',
  decision: '#5aadaf',
  goal: '#5b8ab8',
  preference: '#5b8ab8',
  'schema-gap': '#c87a4a',
  'slog-schema-gap': '#c87a4a',
};

function getFactTypeColor(factType?: string): string {
  if (!factType) return colors.fgFaint;
  return factTypeColors[factType] ?? colors.fgFaint;
}

export default function ClaimsTab({ claims, onSelectEntity }: ClaimsTabProps) {
  const [expandedId, setExpandedId] = useState<string | null>(null);

  if (claims.length === 0) {
    return (
      <div style={{ textAlign: 'center', color: colors.fgFaint, padding: '40px 0', fontSize: 13 }}>
        No memory claims for this entity
      </div>
    );
  }

  return (
    <div>
      {claims.map(claim => {
        const isExpanded = expandedId === claim.id;
        const firstLine = claim.content.split('\n')[0];
        const hasMore = claim.content.includes('\n') || claim.content.length > 120;
        const factType = claim['alh-fact-type'];
        const ftColor = getFactTypeColor(factType);

        return (
          <div
            key={claim.id}
            style={{
              background: colors.panel,
              border: `1px solid ${colors.borderDim}`,
              borderRadius: 3,
              padding: '12px 14px',
              marginBottom: 8,
              cursor: hasMore ? 'pointer' : 'default',
            }}
            onClick={() => {
              if (hasMore) setExpandedId(isExpanded ? null : claim.id);
            }}
          >
            {/* Top row: title + timestamp */}
            <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', gap: 12 }}>
              <div style={{
                fontSize: 12.5,
                color: colors.fg,
                flex: 1,
                minWidth: 0,
                overflow: 'hidden',
                textOverflow: 'ellipsis',
                whiteSpace: isExpanded ? 'normal' : 'nowrap',
              }}>
                {isExpanded ? undefined : firstLine}
              </div>
              {claim['created-at'] && (
                <div style={{
                  fontFamily: "'JetBrains Mono', monospace",
                  fontSize: 10,
                  color: colors.fgFaint,
                  flexShrink: 0,
                  whiteSpace: 'nowrap',
                }}>
                  {formatRelativeDate(claim['created-at'])}
                </div>
              )}
            </div>

            {/* Second row: fact-type badge + confidence */}
            <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginTop: 6 }}>
              {factType && (
                <span style={{
                  fontFamily: "'JetBrains Mono', monospace",
                  fontSize: 9,
                  padding: '1px 5px',
                  borderRadius: 2,
                  backgroundColor: `${ftColor}26`,
                  color: ftColor,
                  whiteSpace: 'nowrap',
                }}>
                  {factType}
                </span>
              )}
              {claim.confidence !== undefined && claim.confidence !== null && (
                <span style={{
                  fontSize: 10,
                  color: colors.fgFaint,
                }}>
                  {claim.confidence.toFixed(1)}
                </span>
              )}
            </div>

            {/* Expanded content */}
            {isExpanded && (
              <div style={{ marginTop: 10 }}>
                <MarkdownContent>{claim.content}</MarkdownContent>
              </div>
            )}
          </div>
        );
      })}
    </div>
  );
}
