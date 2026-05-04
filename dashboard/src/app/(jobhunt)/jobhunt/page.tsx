'use client';

import { useState, useEffect, useCallback } from 'react';
import Link from 'next/link';
import { EmbeddingMap, MapItem } from '@/components/jobhunt/embedding-map';
import { OpportunityList } from '@/components/jobhunt/opportunity-list';
import { SchemaTag, SchemaInspector } from '@/components/jobhunt/schema-inspector';

export default function MissionControl() {
  const [items, setItems] = useState<MapItem[]>([]);
  const [excludeIds, setExcludeIds] = useState<Set<string>>(new Set());
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set());
  const [filteredIds, setFilteredIds] = useState<Set<string> | null>(null);
  const [expandedId, setExpandedId] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [schemaOpen, setSchemaOpen] = useState(false);
  const [schemaFocus, setSchemaFocus] = useState<string | null>(null);
  const [resetKey, setResetKey] = useState(0);
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
  }, [fetchItems]);

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
            Mission Control
          </h1>
          <SchemaTag type="jobhunt" onOpen={() => { setSchemaFocus(null); setSchemaOpen(true); }} />
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
      {activeTab === 'search' && (
        <div style={{
          flex: 1,
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          color: '#5e7387',
          fontFamily: "'JetBrains Mono', monospace",
          fontSize: '13px',
        }}>
          Search missions will appear here. Use Claude to create a search mission.
        </div>
      )}

      {/* Learning Plan tab */}
      {activeTab === 'learning' && (
        <div style={{
          flex: 1,
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          color: '#5e7387',
          fontFamily: "'JetBrains Mono', monospace",
          fontSize: '13px',
        }}>
          Skill profile, gap analysis, and learning plan will appear here.
        </div>
      )}

      <SchemaInspector open={schemaOpen} onClose={() => setSchemaOpen(false)} focus={schemaFocus} />
    </div>
  );
}
