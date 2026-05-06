'use client';

import React, { useEffect, useState } from 'react';
import MarkdownContent from './markdown';
import {
  colors,
  getNamespaceColor,
  getNamespaceColorRgba,
  formatShortDate,
  formatTime,
  formatMonthYear,
  formatRelativeDate,
} from './tokens';

interface EpisodesTabProps {
  entityId: string;
  onSelectEntity: (id: string) => void;
}

interface Episode {
  id: string;
  content: string;
  'created-at'?: string;
  'alh-source-skill'?: string;
  summary?: string;
  operation?: string;
}

const skillToNamespace: Record<string, string> = {
  'tech-recon': 'trec',
  'jobhunt': 'jhunt',
  'agentic-memory': 'nbmem',
  'scientific-literature': 'scilit',
  'web-search': 'alh',
  'typedb-notebook': 'alh',
};

function getSkillNamespace(skill?: string): string {
  if (!skill) return 'unknown';
  return skillToNamespace[skill] ?? 'unknown';
}

export default function EpisodesTab({ entityId, onSelectEntity }: EpisodesTabProps) {
  const [episodes, setEpisodes] = useState<Episode[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;

    async function fetchEpisodes() {
      setLoading(true);
      setError(null);

      try {
        // Try direct query for episodes mentioning this entity
        const query = `match $ep isa alh-episode, has id $eid, has content $ec; (mentioned-entity: $e, episode: $ep) isa alh-episode-mention; $e has id '${entityId}'; fetch { "id": $eid, "content": $ec };`;
        const res = await fetch('/api/agentic-memory/query', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ query }),
        });

        if (res.ok) {
          const data = await res.json();
          if (!cancelled && Array.isArray(data) && data.length > 0) {
            setEpisodes(data);
            setLoading(false);
            return;
          }
        }
      } catch {
        // Fall through to fallback
      }

      try {
        // Fallback: fetch all episodes and filter client-side
        const res = await fetch('/api/agentic-memory/episodes');
        if (res.ok) {
          const data = await res.json();
          if (!cancelled && Array.isArray(data)) {
            const filtered = data.filter((ep: Episode) =>
              ep.content?.includes(entityId)
            );
            setEpisodes(filtered);
          }
        } else if (!cancelled) {
          setError('Failed to fetch episodes');
        }
      } catch {
        if (!cancelled) setError('Failed to fetch episodes');
      }

      if (!cancelled) setLoading(false);
    }

    fetchEpisodes();
    return () => { cancelled = true; };
  }, [entityId]);

  if (loading) {
    return (
      <div style={{ textAlign: 'center', color: colors.fgFaint, padding: '40px 0', fontSize: 13 }}>
        Loading episodes...
      </div>
    );
  }

  if (error) {
    return (
      <div style={{ textAlign: 'center', color: colors.rust, padding: '40px 0', fontSize: 13 }}>
        {error}
      </div>
    );
  }

  if (episodes.length === 0) {
    return (
      <div style={{ textAlign: 'center', color: colors.fgFaint, padding: '40px 0', fontSize: 13 }}>
        No episodes reference this entity
      </div>
    );
  }

  // Sort by created-at descending
  const sorted = [...episodes].sort((a, b) => {
    const da = a['created-at'] ?? '';
    const db = b['created-at'] ?? '';
    return db.localeCompare(da);
  });

  // Group by month/year
  const groups: Array<{ label: string; episodes: Episode[] }> = [];
  let currentLabel = '';
  for (const ep of sorted) {
    const label = ep['created-at'] ? formatMonthYear(ep['created-at']) : 'Unknown Date';
    if (label !== currentLabel) {
      currentLabel = label;
      groups.push({ label, episodes: [] });
    }
    groups[groups.length - 1].episodes.push(ep);
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 24 }}>
      {groups.map((group, gi) => (
        <div key={gi}>
          {/* Month header */}
          <div style={{
            fontFamily: "'JetBrains Mono', monospace",
            fontSize: 10,
            textTransform: 'uppercase',
            color: colors.fgFaint,
            letterSpacing: '1.2px',
            marginBottom: 12,
          }}>
            {group.label}
          </div>

          {/* Timeline entries */}
          <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
            {group.episodes.map((ep, ei) => {
              const skill = ep['alh-source-skill'];
              const ns = getSkillNamespace(skill);
              const nsColor = getNamespaceColor(ns);
              const dateStr = ep['created-at'];

              return (
                <div
                  key={ep.id || ei}
                  style={{
                    position: 'relative',
                    paddingLeft: 24,
                  }}
                >
                  {/* Vertical rail line */}
                  <div style={{
                    position: 'absolute',
                    left: 7,
                    top: 0,
                    bottom: ei === group.episodes.length - 1 ? '50%' : 0,
                    width: 1,
                    backgroundColor: colors.borderDim,
                  }} />

                  {/* Date label */}
                  {dateStr && (
                    <div style={{
                      position: 'absolute',
                      left: -50,
                      top: 4,
                      fontFamily: "'JetBrains Mono', monospace",
                      fontSize: 9,
                      color: colors.fgFaint,
                      width: 48,
                      textAlign: 'right',
                      whiteSpace: 'nowrap',
                    }}>
                      {formatShortDate(dateStr)}
                    </div>
                  )}

                  {/* Dot on rail */}
                  <div style={{
                    position: 'absolute',
                    left: 3,
                    top: 6,
                    width: 9,
                    height: 9,
                    borderRadius: '50%',
                    backgroundColor: nsColor,
                    zIndex: 1,
                  }} />

                  {/* Card */}
                  <div style={{
                    background: colors.panel,
                    border: `1px solid ${colors.borderDim}`,
                    borderRadius: 3,
                    padding: '14px 16px',
                  }}>
                    {/* Header: skill badge + time */}
                    <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 6 }}>
                      {skill && (
                        <span style={{
                          fontFamily: "'JetBrains Mono', monospace",
                          fontSize: 10,
                          padding: '1px 5px',
                          borderRadius: 2,
                          backgroundColor: `${nsColor}26`,
                          color: nsColor,
                          whiteSpace: 'nowrap',
                        }}>
                          {skill}
                        </span>
                      )}
                      {dateStr && (
                        <span style={{
                          fontFamily: "'JetBrains Mono', monospace",
                          fontSize: 10,
                          color: colors.fgFaint,
                        }}>
                          {formatTime(dateStr)}
                        </span>
                      )}
                    </div>

                    {/* Summary / content */}
                    <div>
                      <MarkdownContent fontSize={13} color={colors.fg}>
                        {ep.summary || ep.content || ''}
                      </MarkdownContent>
                    </div>

                    {/* Operation box */}
                    {ep.operation && (
                      <div style={{
                        marginTop: 10,
                        background: getNamespaceColorRgba(ns, 0.06),
                        border: `1px solid ${getNamespaceColorRgba(ns, 0.12)}`,
                        borderRadius: 3,
                        padding: '8px 12px',
                      }}>
                        <span style={{
                          fontFamily: "'JetBrains Mono', monospace",
                          fontSize: 9,
                          textTransform: 'uppercase',
                          color: nsColor,
                          letterSpacing: '0.5px',
                        }}>
                          {ep.operation}
                        </span>
                      </div>
                    )}
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      ))}
    </div>
  );
}
