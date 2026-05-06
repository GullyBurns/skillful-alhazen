'use client';

import { useState, useEffect, useCallback } from 'react';
import Link from 'next/link';
import { EmbeddingMap, MapItem } from '@/components/jobhunt/embedding-map';
import { OpportunityList } from '@/components/jobhunt/opportunity-list';
// SchemaInspector removed — use Alhazen Notebook for schema browsing

export default function MissionControl() {
  const [items, setItems] = useState<MapItem[]>([]);
  const [excludeIds, setExcludeIds] = useState<Set<string>>(new Set());
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set());
  const [filteredIds, setFilteredIds] = useState<Set<string> | null>(null);
  const [expandedId, setExpandedId] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [resetKey, setResetKey] = useState(0);
  const [seekers, setSeekers] = useState<Array<{ role_id: string; role_name: string; status: string; person_id: string; person_name: string }>>([]);
  const [selectedSeeker, setSelectedSeeker] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState<'opportunities' | 'search' | 'learning'>('opportunities');

  const fetchItems = useCallback(async (exclude?: Set<string>) => {
    setLoading(true);
    try {
      let url = '/api/jobhunt/embedding-map';
      if (exclude && exclude.size > 0) {
        url += '?exclude=' + Array.from(exclude).join(',');
      }
      const res = await fetch(url);
      if (!res.ok) throw new Error('Failed to fetch embedding map');
      const data = await res.json();
      setItems(data.items || []);
      // Clear filteredIds so list re-applies its current toggle state to new data
      setFilteredIds(null);
    } catch (err) {
      console.error('Fetch error:', err);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchItems();
    // Fetch seeker profiles
    fetch('/api/jobhunt/seekers')
      .then(r => r.json())
      .then(data => {
        const list = data.seekers ?? [];
        setSeekers(list);
        // Auto-select first active seeker
        const active = list.find((s: { status: string }) => s.status === 'active');
        if (active && !selectedSeeker) setSelectedSeeker(active.person_id);
      })
      .catch(() => {});
  }, [fetchItems]); // eslint-disable-line react-hooks/exhaustive-deps

  // Terminal statuses hidden by default in "All" mode
  const TERMINAL_STATUSES: Record<string, Set<string>> = {
    position: new Set(['withdrawn', 'rejected']),
    engagement: new Set(['closed']),
    venture: new Set(['closed']),
    lead: new Set(['inactive', 'closed']),
  };

  // Visible items: if list has set filteredIds, use that; otherwise apply default filter
  const visibleIds = new Set(
    items
      .filter(item => !excludeIds.has(item.id))
      .filter(item => {
        if (filteredIds) return filteredIds.has(item.id);
        // No explicit filter yet — hide terminal statuses by default
        const terminal = TERMINAL_STATUSES[item.type];
        if (terminal && terminal.has(item.status || '')) return false;
        return true;
      })
      .map(item => item.id)
  );
  const visibleItems = items.filter(item => visibleIds.has(item.id));

  // Status counts
  const statusCounts: Record<string, number> = {};
  visibleItems.forEach(item => {
    statusCounts[item.status] = (statusCounts[item.status] || 0) + 1;
  });

  const handleMapSelect = useCallback((ids: string[]) => {
    setSelectedIds(new Set(ids));
  }, []);

  const handleCheckedChange = useCallback((ids: Set<string>) => {
    setSelectedIds(ids);
  }, []);

  const handleListSelect = useCallback((id: string) => {
    setExpandedId(prev => prev === id ? null : id);
  }, []);

  const handleFilterChange = useCallback((ids: Set<string>) => {
    // If the filter set matches all non-excluded items, treat as "no filter"
    const allNonExcluded = items.filter(i => !excludeIds.has(i.id));
    if (ids.size === allNonExcluded.length) {
      setFilteredIds(null);
    } else {
      setFilteredIds(ids);
    }
    setSelectedIds(new Set()); // clear selection when filter changes
  }, [items, excludeIds]);

  const handleReset = useCallback(() => {
    setExcludeIds(new Set());
    setSelectedIds(new Set());
    setResetKey(k => k + 1);
    fetchItems();
  }, [fetchItems]);

  const handleSelect = useCallback(() => {
    // Keep only selected items visible: exclude everything NOT in selectedIds
    const allIds = new Set(items.map(i => i.id));
    const newExclude = new Set<string>();
    allIds.forEach(id => {
      if (!selectedIds.has(id)) newExclude.add(id);
    });
    setExcludeIds(newExclude);
    setSelectedIds(new Set());
    fetchItems(newExclude);
  }, [items, selectedIds, fetchItems]);

  const handlePrune = useCallback(() => {
    // Add selected items to exclude set
    const newExclude = new Set(excludeIds);
    selectedIds.forEach(id => newExclude.add(id));
    setExcludeIds(newExclude);
    setSelectedIds(new Set());
    fetchItems(newExclude);
  }, [excludeIds, selectedIds, fetchItems]);

  const statusSummary = Object.entries(statusCounts)
    .sort(([, a], [, b]) => b - a)
    .map(([status, count]) => `${count} ${status}`)
    .join(' / ');

  const TAB_ITEMS: { key: typeof activeTab; label: string }[] = [
    { key: 'opportunities', label: 'Opportunities' },
    { key: 'search', label: 'Search for Jobs' },
    { key: 'learning', label: 'Learning Plan' },
  ];

  return (
    <div style={{
      width: '100vw',
      height: '100vh',
      backgroundColor: '#070d1c',
      display: 'flex',
      flexDirection: 'column',
      fontFamily: "'DM Sans', sans-serif",
      overflow: 'hidden',
    }}>
      {/* ── Global header ── */}
      <div style={{
        padding: '12px 16px 0 16px',
        flexShrink: 0,
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
          <Link href="/" style={{
            fontFamily: "'JetBrains Mono', monospace",
            fontSize: '11px',
            color: '#5e7387',
            textDecoration: 'none',
            transition: 'color 0.15s',
          }}
            onMouseEnter={(e) => { e.currentTarget.style.color = '#5aadaf'; }}
            onMouseLeave={(e) => { e.currentTarget.style.color = '#5e7387'; }}
          >
            &larr; hub
          </Link>
          <h1 style={{
            fontFamily: "'DM Serif Display', serif",
            fontSize: '24px',
            color: '#c8dde8',
            margin: 0,
            lineHeight: 1.2,
          }}>
            Jobhunt Mission Control
          </h1>

          {/* Person selector */}
          {seekers.length > 0 && (
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginLeft: 'auto' }}>
              <span style={{
                fontFamily: "'JetBrains Mono', monospace",
                fontSize: '10px',
                color: '#5e7387',
                textTransform: 'uppercase',
                letterSpacing: '0.8px',
              }}>
                Seeker
              </span>
              <select
                value={selectedSeeker ?? ''}
                onChange={(e) => setSelectedSeeker(e.target.value || null)}
                style={{
                  fontFamily: "'JetBrains Mono', monospace",
                  fontSize: '12px',
                  color: '#c8dde8',
                  background: 'rgba(12, 22, 40, 0.72)',
                  border: '1px solid rgba(90, 173, 175, 0.18)',
                  borderRadius: '3px',
                  padding: '4px 10px',
                  cursor: 'pointer',
                  outline: 'none',
                }}
              >
                <option value="" style={{ background: '#0c1628' }}>All seekers</option>
                {seekers.map(s => (
                  <option key={s.person_id} value={s.person_id} style={{ background: '#0c1628' }}>
                    {s.person_name} — {s.role_name} {s.status !== 'active' ? `(${s.status})` : ''}
                  </option>
                ))}
              </select>
            </div>
          )}
        </div>

        {/* ── Tab bar ── */}
        <div style={{
          display: 'flex',
          gap: '0',
          marginTop: '10px',
          borderBottom: '1px solid rgba(94, 115, 135, 0.2)',
        }}>
          {TAB_ITEMS.map(tab => (
            <button
              key={tab.key}
              onClick={() => setActiveTab(tab.key)}
              style={{
                fontFamily: "'JetBrains Mono', monospace",
                fontSize: '11px',
                letterSpacing: '0.5px',
                color: activeTab === tab.key ? '#c8dde8' : '#5e7387',
                backgroundColor: 'transparent',
                border: 'none',
                borderBottom: activeTab === tab.key ? '2px solid #5aadaf' : '2px solid transparent',
                padding: '8px 16px',
                cursor: 'pointer',
                transition: 'color 0.15s, border-color 0.15s',
              }}
              onMouseEnter={(e) => {
                if (activeTab !== tab.key) e.currentTarget.style.color = '#8ba4b8';
              }}
              onMouseLeave={(e) => {
                if (activeTab !== tab.key) e.currentTarget.style.color = '#5e7387';
              }}
            >
              {tab.label}
            </button>
          ))}
        </div>
      </div>

      {/* ── Tab content ── */}

      {/* Opportunities tab */}
      {activeTab === 'opportunities' && (
      <div style={{
        flex: 1,
        display: 'flex',
        flexDirection: 'row',
        overflow: 'hidden',
      }}>
      {/* Left panel: Map */}
      <div style={{
        width: '60%',
        height: '100%',
        display: 'flex',
        flexDirection: 'column',
        padding: '8px 16px 12px 16px',
        boxSizing: 'border-box',
      }}>
        {/* Subheader */}
        <div style={{ marginBottom: '8px' }}>
          <div style={{
            fontSize: '12px',
            color: '#5e7387',
          }}>
            {visibleItems.length} items{statusSummary ? ` \u2014 ${statusSummary}` : ''}
          </div>
        </div>

        {/* Map area */}
        <div style={{
          flex: 1,
          minHeight: 0,
          borderRadius: '6px',
          border: '1px solid rgba(94, 115, 135, 0.2)',
          overflow: 'hidden',
        }}>
          {loading ? (
            <div style={{
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              height: '100%',
              color: '#5e7387',
              fontSize: '13px',
            }}>
              Loading...
            </div>
          ) : (
            <EmbeddingMap
              items={visibleItems}
              selectedIds={selectedIds}
              onSelect={handleMapSelect}
            />
          )}
        </div>

        {/* Button bar */}
        <div style={{
          display: 'flex',
          gap: '8px',
          marginTop: '10px',
        }}>
          <button
            onClick={handleReset}
            style={{
              fontFamily: "'JetBrains Mono', monospace",
              fontSize: '11px',
              color: '#8ba4b8',
              backgroundColor: 'transparent',
              border: '1px solid rgba(139, 164, 184, 0.3)',
              borderRadius: '4px',
              padding: '5px 14px',
              cursor: 'pointer',
              letterSpacing: '0.5px',
              transition: 'border-color 0.15s, color 0.15s',
            }}
            onMouseEnter={(e) => {
              e.currentTarget.style.borderColor = '#8ba4b8';
              e.currentTarget.style.color = '#c8dde8';
            }}
            onMouseLeave={(e) => {
              e.currentTarget.style.borderColor = 'rgba(139, 164, 184, 0.3)';
              e.currentTarget.style.color = '#8ba4b8';
            }}
          >
            Reset
          </button>
          <button
            onClick={() => fetchItems(excludeIds.size > 0 ? excludeIds : undefined)}
            style={{
              fontFamily: "'JetBrains Mono', monospace",
              fontSize: '11px',
              color: '#5aadaf',
              backgroundColor: 'transparent',
              border: '1px solid rgba(90, 173, 175, 0.3)',
              borderRadius: '4px',
              padding: '5px 14px',
              cursor: 'pointer',
              letterSpacing: '0.5px',
              transition: 'border-color 0.15s, color 0.15s',
            }}
            onMouseEnter={(e) => {
              e.currentTarget.style.borderColor = '#5aadaf';
              e.currentTarget.style.color = '#c8dde8';
            }}
            onMouseLeave={(e) => {
              e.currentTarget.style.borderColor = 'rgba(90, 173, 175, 0.3)';
              e.currentTarget.style.color = '#5aadaf';
            }}
          >
            Reload
          </button>
          <button
            onClick={handleSelect}
            disabled={selectedIds.size === 0}
            style={{
              fontFamily: "'JetBrains Mono', monospace",
              fontSize: '11px',
              color: selectedIds.size > 0 ? '#b8c84a' : '#5e7387',
              backgroundColor: 'transparent',
              border: `1px solid ${selectedIds.size > 0 ? 'rgba(184, 200, 74, 0.4)' : 'rgba(94, 115, 135, 0.2)'}`,
              borderRadius: '4px',
              padding: '5px 14px',
              cursor: selectedIds.size > 0 ? 'pointer' : 'default',
              letterSpacing: '0.5px',
              transition: 'border-color 0.15s, color 0.15s',
              opacity: selectedIds.size > 0 ? 1 : 0.5,
            }}
            onMouseEnter={(e) => {
              if (selectedIds.size > 0) {
                e.currentTarget.style.borderColor = '#b8c84a';
                e.currentTarget.style.color = '#d4e066';
              }
            }}
            onMouseLeave={(e) => {
              if (selectedIds.size > 0) {
                e.currentTarget.style.borderColor = 'rgba(184, 200, 74, 0.4)';
                e.currentTarget.style.color = '#b8c84a';
              }
            }}
          >
            Select ({selectedIds.size})
          </button>
          <button
            onClick={handlePrune}
            disabled={selectedIds.size === 0}
            style={{
              fontFamily: "'JetBrains Mono', monospace",
              fontSize: '11px',
              color: selectedIds.size > 0 ? '#e05555' : '#5e7387',
              backgroundColor: 'transparent',
              border: `1px solid ${selectedIds.size > 0 ? 'rgba(224, 85, 85, 0.4)' : 'rgba(94, 115, 135, 0.2)'}`,
              borderRadius: '4px',
              padding: '5px 14px',
              cursor: selectedIds.size > 0 ? 'pointer' : 'default',
              letterSpacing: '0.5px',
              transition: 'border-color 0.15s, color 0.15s',
              opacity: selectedIds.size > 0 ? 1 : 0.5,
            }}
            onMouseEnter={(e) => {
              if (selectedIds.size > 0) {
                e.currentTarget.style.borderColor = '#e05555';
                e.currentTarget.style.color = '#f07070';
              }
            }}
            onMouseLeave={(e) => {
              if (selectedIds.size > 0) {
                e.currentTarget.style.borderColor = 'rgba(224, 85, 85, 0.4)';
                e.currentTarget.style.color = '#e05555';
              }
            }}
          >
            Prune ({selectedIds.size})
          </button>
        </div>
      </div>

      {/* Right panel: List */}
      <div style={{
        width: '40%',
        height: '100%',
        borderLeft: '1px solid rgba(94, 115, 135, 0.2)',
        display: 'flex',
        flexDirection: 'column',
      }}>
        <div style={{
          padding: '16px 12px 8px 12px',
          borderBottom: '1px solid rgba(94, 115, 135, 0.2)',
        }}>
          <span style={{
            fontFamily: "'JetBrains Mono', monospace",
            fontSize: '10px',
            color: '#5e7387',
            textTransform: 'uppercase',
            letterSpacing: '1px',
          }}>
            Opportunities ({visibleItems.length})
          </span>
        </div>
        <div style={{ flex: 1, minHeight: 0 }}>
          <OpportunityList
            items={items}
            visibleIds={new Set(items.filter(i => !excludeIds.has(i.id)).map(i => i.id))}
            selectedId={expandedId}
            onSelect={handleListSelect}
            onFilterChange={handleFilterChange}
            onCheckedChange={handleCheckedChange}
            resetKey={resetKey}
          />
        </div>
      </div>
      </div>
      )}

      {/* Search for Jobs tab */}
      {activeTab === 'search' && <SearchTab />}

      {/* Learning Plan tab */}
      {activeTab === 'learning' && <LearningTab />}

      {/* SchemaInspector removed — use Alhazen Notebook for schema browsing */}
    </div>
  );
}


// =============================================================================
// Search Tab — shows configured sources and discovered candidates
// =============================================================================

interface Source {
  id: string;
  name: string;
  platform: string;
  board_token: string | null;
  search_query: string | null;
  search_location: string | null;
  company_url: string | null;
}

interface Candidate {
  id: string;
  title: string;
  url: string;
  location: string | null;
  relevance: number;
  status: string;
  discovered_at: string | null;
  triage_reason: string | null;  // agent's fit rationale
}

const PLATFORM_COLORS: Record<string, string> = {
  greenhouse: '#5aadaf',
  lever: '#5b8ab8',
  ashby: '#5b8ab8',
  linkedin: '#5b8ab8',
  remotive: '#b8c84a',
  adzuna: '#62c4bc',
  website: '#b8c84a',
};

function SearchTab() {
  const [sources, setSources] = useState<Source[]>([]);
  const [candidates, setCandidates] = useState<Candidate[]>([]);
  const [loadingSources, setLoadingSources] = useState(true);
  const [loadingCandidates, setLoadingCandidates] = useState(true);

  useEffect(() => {
    fetch('/api/jobhunt/sources')
      .then(r => r.json())
      .then(data => setSources(data.sources ?? []))
      .catch(() => {})
      .finally(() => setLoadingSources(false));

    fetch('/api/jobhunt/candidates')
      .then(r => r.json())
      .then(data => setCandidates(data.candidates ?? []))
      .catch(() => {})
      .finally(() => setLoadingCandidates(false));
  }, []);

  return (
    <div style={{ flex: 1, overflow: 'auto', padding: '20px 24px', display: 'flex', flexDirection: 'column', gap: '24px' }}>

      {/* Sources section */}
      <div>
        <div style={{
          fontFamily: "'JetBrains Mono', monospace",
          fontSize: '10px',
          color: '#5e7387',
          textTransform: 'uppercase',
          letterSpacing: '1.4px',
          marginBottom: '10px',
        }}>
          Search Sources ({sources.length})
        </div>

        {loadingSources ? (
          <div style={{ color: '#5e7387', fontFamily: "'JetBrains Mono', monospace", fontSize: '11px' }}>Loading...</div>
        ) : sources.length === 0 ? (
          <div style={{ color: '#5e7387', fontFamily: "'JetBrains Mono', monospace", fontSize: '12px', padding: '16px' }}>
            No sources configured. Use <code style={{ color: '#5aadaf' }}>job_forager.py add-source</code> to add company boards or aggregators.
          </div>
        ) : (
          <SourceGroups sources={sources} />
        )}
      </div>

      {/* Candidates section */}
      <div>
        <div style={{
          fontFamily: "'JetBrains Mono', monospace",
          fontSize: '10px',
          color: '#5e7387',
          textTransform: 'uppercase',
          letterSpacing: '1.4px',
          marginBottom: '10px',
        }}>
          Discovered Candidates ({candidates.length})
        </div>

        {loadingCandidates ? (
          <div style={{ color: '#5e7387', fontFamily: "'JetBrains Mono', monospace", fontSize: '11px' }}>Loading...</div>
        ) : candidates.length === 0 ? (
          <div style={{ color: '#5e7387', fontFamily: "'JetBrains Mono', monospace", fontSize: '12px', padding: '16px' }}>
            No candidates discovered yet. Run <code style={{ color: '#5aadaf' }}>job_forager.py heartbeat</code> to search all sources.
          </div>
        ) : (
          <div style={{
            border: '1px solid rgba(200, 221, 232, 0.08)',
            borderRadius: '3px',
            overflow: 'hidden',
          }}>
            {/* Table header */}
            <div style={{
              display: 'grid',
              gridTemplateColumns: '2fr 1fr 80px 80px',
              padding: '6px 12px',
              background: 'rgba(12, 22, 40, 0.72)',
              fontFamily: "'JetBrains Mono', monospace",
              fontSize: '10px',
              textTransform: 'uppercase',
              color: '#5e7387',
              letterSpacing: '0.5px',
            }}>
              <span>Title</span>
              <span>Location</span>
              <span>Relevance</span>
              <span>Status</span>
            </div>

            {candidates.map(c => (
              <div key={c.id} style={{
                borderTop: '1px solid rgba(200, 221, 232, 0.08)',
              }}>
                <div style={{
                  display: 'grid',
                  gridTemplateColumns: '2fr 1fr 80px 80px',
                  padding: '8px 12px',
                  fontSize: '12px',
                  alignItems: 'baseline',
                }}>
                  <div>
                    {c.url ? (
                      <a href={c.url} target="_blank" rel="noopener noreferrer" style={{
                        color: '#5aadaf',
                        textDecoration: 'underline',
                        textUnderlineOffset: '2px',
                      }}>{c.title}</a>
                    ) : (
                      <span style={{ color: '#c8dde8' }}>{c.title}</span>
                    )}
                  </div>
                  <span style={{ color: '#8ba4b8', fontSize: '11px' }}>{c.location ?? ''}</span>
                  <span style={{
                    fontFamily: "'JetBrains Mono', monospace",
                    fontSize: '10px',
                    color: c.relevance >= 0.5 ? '#b8c84a' : c.relevance >= 0.2 ? '#8ba4b8' : '#5e7387',
                  }}>
                    {(c.relevance * 100).toFixed(0)}%
                  </span>
                  <span style={{
                    fontFamily: "'JetBrains Mono', monospace",
                    fontSize: '9px',
                    color: c.status === 'new' ? '#62c4bc' : c.status === 'reviewed' ? '#b8c84a' : '#5e7387',
                    textTransform: 'uppercase',
                  }}>
                    {c.status}
                  </span>
                </div>
                {c.triage_reason && (
                  <div style={{
                    padding: '0 12px 8px',
                    fontSize: '11px',
                    color: '#8ba4b8',
                    lineHeight: 1.4,
                    fontStyle: 'italic',
                  }}>
                    {c.triage_reason}
                  </div>
                )}
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

const COMPANY_BOARDS = new Set(['greenhouse', 'lever', 'ashby']);
const WEBSITE_PLATFORMS = new Set(['website']);

function SourceGroups({ sources }: { sources: Source[] }) {
  const companyBoards = sources.filter(s => COMPANY_BOARDS.has(s.platform));
  const websites = sources.filter(s => WEBSITE_PLATFORMS.has(s.platform));
  const aggregators = sources.filter(s => !COMPANY_BOARDS.has(s.platform) && !WEBSITE_PLATFORMS.has(s.platform));

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
      {companyBoards.length > 0 && (
        <div>
          <div style={{
            fontFamily: "'JetBrains Mono', monospace",
            fontSize: '9px',
            color: '#8ba4b8',
            textTransform: 'uppercase',
            letterSpacing: '1px',
            marginBottom: '6px',
          }}>
            Company Recruiting Pages
          </div>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(260px, 1fr))', gap: '8px' }}>
            {companyBoards.map(source => <SourceCard key={source.id} source={source} />)}
          </div>
        </div>
      )}
      {websites.length > 0 && (
        <div>
          <div style={{
            fontFamily: "'JetBrains Mono', monospace",
            fontSize: '9px',
            color: '#8ba4b8',
            textTransform: 'uppercase',
            letterSpacing: '1px',
            marginBottom: '6px',
          }}>
            Job Websites (Browser Search)
          </div>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(260px, 1fr))', gap: '8px' }}>
            {websites.map(source => <SourceCard key={source.id} source={source} />)}
          </div>
        </div>
      )}
      {aggregators.length > 0 && (
        <div>
          <div style={{
            fontFamily: "'JetBrains Mono', monospace",
            fontSize: '9px',
            color: '#8ba4b8',
            textTransform: 'uppercase',
            letterSpacing: '1px',
            marginBottom: '6px',
          }}>
            Job Board Aggregators
          </div>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(260px, 1fr))', gap: '8px' }}>
            {aggregators.map(source => <SourceCard key={source.id} source={source} />)}
          </div>
        </div>
      )}
    </div>
  );
}

function SourceCard({ source }: { source: Source }) {
  const color = PLATFORM_COLORS[source.platform] ?? '#8ba4b8';
  const isBoard = COMPANY_BOARDS.has(source.platform);
  const isWebsite = WEBSITE_PLATFORMS.has(source.platform);

  return (
    <div style={{
      background: 'rgba(12, 22, 40, 0.72)',
      border: '1px solid rgba(200, 221, 232, 0.08)',
      borderRadius: '3px',
      padding: '12px 14px',
    }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '6px' }}>
        <span style={{
          fontFamily: "'JetBrains Mono', monospace",
          fontSize: '9px',
          color,
          background: `${color}15`,
          borderRadius: '2px',
          padding: '1px 6px',
          textTransform: 'uppercase',
          letterSpacing: '0.5px',
        }}>
          {source.platform}
        </span>
        <span style={{ fontSize: '13px', color: '#c8dde8' }}>{source.name}</span>
      </div>
      <div style={{ fontFamily: "'JetBrains Mono', monospace", fontSize: '10px', color: '#5e7387' }}>
        {isBoard && source.board_token && (
          <div>
            <a
              href={`https://boards.${source.platform}.io/${source.board_token}`}
              target="_blank"
              rel="noopener noreferrer"
              style={{ color: '#5aadaf', textDecoration: 'underline', textUnderlineOffset: '2px' }}
            >
              boards.{source.platform}.io/{source.board_token}
            </a>
          </div>
        )}
        {isWebsite && source.company_url && (
          <div>
            <a
              href={source.company_url}
              target="_blank"
              rel="noopener noreferrer"
              style={{ color: '#5aadaf', textDecoration: 'underline', textUnderlineOffset: '2px' }}
            >
              {source.company_url.replace(/^https?:\/\//, '')}
            </a>
          </div>
        )}
        {source.search_query && <div>query: {source.search_query}</div>}
        {source.search_location && <div>location: {source.search_location}</div>}
        {isWebsite && (
          <div style={{ marginTop: '4px', fontSize: '9px', color: '#62c4bc', fontStyle: 'italic' }}>
            Requires Playwright MCP browser automation
          </div>
        )}
      </div>
    </div>
  );
}


// =============================================================================
// Learning Tab — Skills, Gaps, Learning Resources
// =============================================================================

interface Skill {
  name: string;
  level: string;
  evidence: string | null;
  recency: string | null;
  description: string | null;
}

interface SkillGap {
  skill: string;
  level: string;
  your_level: string;
  positions: Array<{ id: string; title: string }>;
}

interface LearningResource {
  id: string;
  name: string;
  type: string;
  url: string | null;
  hours: number | null;
  status: string;
}

const LEVEL_COLORS: Record<string, string> = {
  expert: '#5aadaf', strong: '#5aadaf',
  practiced: '#5b8ab8', some: '#5b8ab8',
  aware: '#b8c84a', learning: '#b8c84a',
  none: '#c87a4a',
};

const LEVEL_LABELS: Record<string, string> = {
  expert: 'EXPERT', strong: 'EXPERT',
  practiced: 'PRACTICED', some: 'PRACTICED',
  aware: 'AWARE', learning: 'AWARE',
  none: 'NONE',
};

const RESOURCE_TYPE_COLORS: Record<string, string> = {
  course: '#5b8ab8', book: '#b8c84a', tutorial: '#62c4bc',
  project: '#5aadaf', video: '#8ba4b8',
};

interface PositionFit {
  id: string;
  name: string;
  fit_score: number;
  total_requirements: number;
  covered: number;
  gaps: number;
}

interface LearningPriority {
  skill: string;
  current_level: string;
  gap_impact: number;
  needed_for: number;
  positions: string[];
}

function LearningTab() {
  const [skills, setSkills] = useState<Skill[]>([]);
  const [gaps, setGaps] = useState<SkillGap[]>([]);
  const [resources, setResources] = useState<LearningResource[]>([]);
  const [positionFits, setPositionFits] = useState<PositionFit[]>([]);
  const [learningPriorities, setLearningPriorities] = useState<LearningPriority[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    Promise.all([
      fetch('/api/jobhunt/skills').then(r => r.json()),
      fetch('/api/jobhunt/fit').then(r => r.json()),
      fetch('/api/jobhunt/learning').then(r => r.json()),
    ]).then(([skillsData, fitData, resourcesData]) => {
      setSkills(skillsData.skills ?? []);
      setPositionFits(fitData.positions ?? []);
      setLearningPriorities(fitData.learning_priorities ?? []);
      setGaps(fitData.skill_gaps ?? []);
      setResources(resourcesData.learning_plan ?? []);
    }).catch(() => {}).finally(() => setLoading(false));
  }, []);

  if (loading) {
    return (
      <div style={{ flex: 1, display: 'flex', alignItems: 'center', justifyContent: 'center', color: '#5e7387', fontFamily: "'JetBrains Mono', monospace", fontSize: '11px' }}>
        Loading...
      </div>
    );
  }

  return (
    <div style={{ flex: 1, overflow: 'auto', padding: '20px 24px', display: 'flex', flexDirection: 'column', gap: '24px' }}>

      {/* Position Skill Coverage */}
      {positionFits.length > 0 && (
        <div>
          <div style={{ fontFamily: "'JetBrains Mono', monospace", fontSize: '10px', color: '#5e7387', textTransform: 'uppercase', letterSpacing: '1.4px', marginBottom: '10px' }}>
            Position Skill Coverage ({positionFits.length} positions)
          </div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
            {positionFits.map(pf => (
              <div key={pf.id} style={{
                background: 'rgba(12, 22, 40, 0.72)',
                border: `1px solid ${pf.gaps === 0 ? 'rgba(90,173,175,0.3)' : 'rgba(200,221,232,0.08)'}`,
                borderRadius: '3px', padding: '10px 14px',
              }}>
                <div style={{ display: 'flex', alignItems: 'baseline', gap: '8px', marginBottom: '6px' }}>
                  <span style={{ fontSize: '12px', color: '#c8dde8' }}>{pf.name.substring(0, 50)}</span>
                  <span style={{ fontFamily: "'JetBrains Mono', monospace", fontSize: '9px', color: pf.gaps === 0 ? '#5aadaf' : '#c87a4a', marginLeft: 'auto' }}>
                    {pf.gaps === 0 ? 'ALL MET' : `${pf.gaps} GAP${pf.gaps > 1 ? 'S' : ''}`}
                  </span>
                </div>
                <div style={{ display: 'flex', flexWrap: 'wrap', gap: '4px' }}>
                  {(pf as unknown as { requirements: Array<{ skill: string; required_level: string; my_level: string; coverage: number }> }).requirements?.map((req: { skill: string; required_level: string; my_level: string; coverage: number }) => {
                    const met = req.coverage >= 1.0;
                    const color = met ? '#5aadaf' : '#c87a4a';
                    return (
                      <span key={req.skill} style={{
                        fontFamily: "'JetBrains Mono', monospace", fontSize: '9px',
                        color, background: `${color}10`,
                        border: `1px solid ${color}30`,
                        borderRadius: '2px', padding: '1px 6px',
                      }}>
                        {met ? '\u2713' : '\u2717'} {req.skill} ({req.required_level})
                      </span>
                    );
                  })}
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Learning Priorities */}
      {learningPriorities.length > 0 && (
        <div>
          <div style={{ fontFamily: "'JetBrains Mono', monospace", fontSize: '10px', color: '#5e7387', textTransform: 'uppercase', letterSpacing: '1.4px', marginBottom: '10px' }}>
            Learning Priorities (by gap impact)
          </div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
            {learningPriorities.map(lp => {
              const levelColor = LEVEL_COLORS[lp.current_level] ?? '#c87a4a';
              return (
                <div key={lp.skill} style={{
                  display: 'flex', alignItems: 'center', gap: '10px',
                  padding: '6px 12px',
                  background: 'rgba(12, 22, 40, 0.72)',
                  border: '1px solid rgba(200, 221, 232, 0.08)',
                  borderLeft: `3px solid ${levelColor}`,
                  borderRadius: '3px',
                }}>
                  <span style={{ fontSize: '12px', color: '#c8dde8', flex: '1' }}>{lp.skill}</span>
                  <span style={{ fontFamily: "'JetBrains Mono', monospace", fontSize: '9px', color: levelColor }}>
                    {(LEVEL_LABELS[lp.current_level] ?? 'NONE')}
                  </span>
                  <span style={{ fontFamily: "'JetBrains Mono', monospace", fontSize: '9px', color: '#5e7387' }}>
                    impact: {lp.gap_impact} | {lp.needed_for} positions
                  </span>
                </div>
              );
            })}
          </div>
        </div>
      )}

      {/* Your Skills */}
      <div>
        <div style={{ fontFamily: "'JetBrains Mono', monospace", fontSize: '10px', color: '#5e7387', textTransform: 'uppercase', letterSpacing: '1.4px', marginBottom: '10px' }}>
          Your Skills ({skills.length})
        </div>

        {skills.length === 0 ? (
          <div style={{ color: '#5e7387', fontFamily: "'JetBrains Mono', monospace", fontSize: '12px', padding: '16px' }}>
            No skills defined yet. Ingest your LinkedIn profile and run skill extraction.
          </div>
        ) : (
          <div style={{ border: '1px solid rgba(200, 221, 232, 0.08)', borderRadius: '3px', overflow: 'hidden' }}>
            <div style={{
              display: 'grid', gridTemplateColumns: '1.2fr 80px 2fr 100px',
              padding: '6px 12px', background: 'rgba(12, 22, 40, 0.72)',
              fontFamily: "'JetBrains Mono', monospace", fontSize: '10px', textTransform: 'uppercase', color: '#5e7387', letterSpacing: '0.5px',
            }}>
              <span>Skill</span><span>Level</span><span>Evidence</span><span>Recency</span>
            </div>
            {skills.map(skill => {
              const color = LEVEL_COLORS[skill.level] ?? '#5e7387';
              const label = LEVEL_LABELS[skill.level] ?? skill.level.toUpperCase();
              return (
                <div key={skill.name} style={{
                  display: 'grid', gridTemplateColumns: '1.2fr 80px 2fr 100px',
                  padding: '7px 12px', borderTop: '1px solid rgba(200, 221, 232, 0.08)', fontSize: '12px', alignItems: 'baseline',
                }}>
                  <span style={{ color: '#c8dde8' }}>{skill.name}</span>
                  <span style={{ fontFamily: "'JetBrains Mono', monospace", fontSize: '9px', color, background: `${color}15`, borderRadius: '2px', padding: '1px 6px', textAlign: 'center' }}>
                    {label}
                  </span>
                  <span style={{ color: '#8ba4b8', fontSize: '11px', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                    {skill.evidence ?? skill.description ?? ''}
                  </span>
                  <span style={{ fontFamily: "'JetBrains Mono', monospace", fontSize: '9px', color: '#5e7387' }}>
                    {skill.recency ?? ''}
                  </span>
                </div>
              );
            })}
          </div>
        )}
      </div>

      {/* Skill Gaps */}
      <div>
        <div style={{ fontFamily: "'JetBrains Mono', monospace", fontSize: '10px', color: '#5e7387', textTransform: 'uppercase', letterSpacing: '1.4px', marginBottom: '10px' }}>
          Skill Gaps ({gaps.length})
        </div>

        {gaps.length === 0 ? (
          <div style={{ color: '#62c4bc', fontFamily: "'JetBrains Mono', monospace", fontSize: '12px', padding: '16px' }}>
            No skill gaps detected.
          </div>
        ) : (
          <div style={{ border: '1px solid rgba(200, 221, 232, 0.08)', borderRadius: '3px', overflow: 'hidden' }}>
            <div style={{
              display: 'grid', gridTemplateColumns: '1.2fr 80px 80px 2fr',
              padding: '6px 12px', background: 'rgba(12, 22, 40, 0.72)',
              fontFamily: "'JetBrains Mono', monospace", fontSize: '10px', textTransform: 'uppercase', color: '#5e7387', letterSpacing: '0.5px',
            }}>
              <span>Skill</span><span>Your Level</span><span>Required</span><span>Positions</span>
            </div>
            {gaps.map(gap => {
              const yourColor = LEVEL_COLORS[gap.your_level] ?? '#c87a4a';
              const yourLabel = LEVEL_LABELS[gap.your_level] ?? gap.your_level.toUpperCase();
              const isLargeGap = gap.your_level === 'none' && gap.level === 'required';
              return (
                <div key={gap.skill} style={{
                  display: 'grid', gridTemplateColumns: '1.2fr 80px 80px 2fr',
                  padding: '7px 12px', borderTop: '1px solid rgba(200, 221, 232, 0.08)',
                  borderLeft: isLargeGap ? '3px solid #c87a4a' : '3px solid transparent',
                  fontSize: '12px', alignItems: 'baseline',
                }}>
                  <span style={{ color: '#c8dde8' }}>{gap.skill}</span>
                  <span style={{ fontFamily: "'JetBrains Mono', monospace", fontSize: '9px', color: yourColor, background: `${yourColor}15`, borderRadius: '2px', padding: '1px 6px', textAlign: 'center' }}>
                    {yourLabel}
                  </span>
                  <span style={{ fontFamily: "'JetBrains Mono', monospace", fontSize: '9px', color: '#c8dde8', textTransform: 'uppercase' }}>
                    {gap.level}
                  </span>
                  <span style={{ color: '#8ba4b8', fontSize: '11px', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                    {gap.positions.map(p => p.title.substring(0, 40)).join(', ')}
                  </span>
                </div>
              );
            })}
          </div>
        )}
      </div>

      {/* Learning Resources */}
      <div>
        <div style={{ fontFamily: "'JetBrains Mono', monospace", fontSize: '10px', color: '#5e7387', textTransform: 'uppercase', letterSpacing: '1.4px', marginBottom: '10px' }}>
          Learning Resources ({resources.length})
        </div>

        {resources.length === 0 ? (
          <div style={{ color: '#5e7387', fontFamily: "'JetBrains Mono', monospace", fontSize: '12px', padding: '16px' }}>
            No learning resources yet.
          </div>
        ) : (
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(320px, 1fr))', gap: '8px' }}>
            {resources.map(resource => {
              const typeColor = RESOURCE_TYPE_COLORS[resource.type] ?? '#8ba4b8';
              return (
                <div key={resource.id} style={{
                  background: 'rgba(12, 22, 40, 0.72)', border: '1px solid rgba(200, 221, 232, 0.08)',
                  borderRadius: '3px', padding: '10px 14px',
                }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '4px' }}>
                    <span style={{ fontFamily: "'JetBrains Mono', monospace", fontSize: '9px', color: typeColor, background: `${typeColor}15`, borderRadius: '2px', padding: '1px 6px', textTransform: 'uppercase', letterSpacing: '0.5px' }}>
                      {resource.type}
                    </span>
                    {resource.hours != null && (
                      <span style={{ fontFamily: "'JetBrains Mono', monospace", fontSize: '9px', color: '#5e7387' }}>{resource.hours}h</span>
                    )}
                    <span style={{
                      fontFamily: "'JetBrains Mono', monospace", fontSize: '8px', marginLeft: 'auto', textTransform: 'uppercase',
                      color: resource.status === 'completed' ? '#5aadaf' : resource.status === 'in-progress' ? '#b8c84a' : '#5e7387',
                    }}>
                      {resource.status}
                    </span>
                  </div>
                  <div style={{ fontSize: '12px' }}>
                    {resource.url ? (
                      <a href={resource.url} target="_blank" rel="noopener noreferrer" style={{ color: '#c8dde8', textDecoration: 'underline', textUnderlineOffset: '2px' }}>
                        {resource.name}
                      </a>
                    ) : (
                      <span style={{ color: '#c8dde8' }}>{resource.name}</span>
                    )}
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
}
