'use client';

import { useState, useEffect, useRef, useCallback } from 'react';
import { colors, getNamespace, getNamespaceColor, stripPrefix } from './tokens';

interface GlobalSearchProps {
  onSelectEntity: (id: string) => void;
}

interface TextResult {
  id: string;
  name: string;
}

interface SemanticResult {
  collection: string;
  entity_type: string;
  skill: string;
  score: number;
  payload: { id: string; name: string; [key: string]: unknown };
}

type SearchMode = 'text' | 'semantic';

export default function GlobalSearch({ onSelectEntity }: GlobalSearchProps) {
  const [query, setQuery] = useState('');
  const [mode, setMode] = useState<SearchMode>('text');
  const [loading, setLoading] = useState(false);
  const [textResults, setTextResults] = useState<TextResult[]>([]);
  const [semanticResults, setSemanticResults] = useState<SemanticResult[]>([]);
  const [semanticError, setSemanticError] = useState(false);
  const [showDropdown, setShowDropdown] = useState(false);
  const containerRef = useRef<HTMLDivElement>(null);
  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const performSearch = useCallback(async (term: string, searchMode: SearchMode) => {
    if (!term.trim()) {
      setTextResults([]);
      setSemanticResults([]);
      setShowDropdown(false);
      return;
    }

    setLoading(true);
    setSemanticError(false);

    try {
      if (searchMode === 'text') {
        const escaped = term.replace(/'/g, "\\'");
        const typeql = `match $e isa alh-identifiable-entity, has id $id, has name $name; $name contains '${escaped}'; fetch { "id": $id, "name": $name };`;
        const res = await fetch('/api/agentic-memory/query', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ typeql, limit: 20 }),
        });
        const data = await res.json();
        if (data.success && Array.isArray(data.results)) {
          setTextResults(data.results.slice(0, 20));
        } else {
          setTextResults([]);
        }
        setShowDropdown(true);
      } else {
        const res = await fetch(`/api/agentic-memory/search?query=${encodeURIComponent(term)}&limit=10`);
        if (!res.ok) {
          setSemanticError(true);
          setSemanticResults([]);
          setShowDropdown(true);
          return;
        }
        const data = await res.json();
        if (data.success && Array.isArray(data.results)) {
          setSemanticResults(data.results);
        } else {
          setSemanticResults([]);
        }
        setShowDropdown(true);
      }
    } catch {
      if (searchMode === 'semantic') {
        setSemanticError(true);
      }
      setTextResults([]);
      setSemanticResults([]);
      setShowDropdown(true);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    if (debounceRef.current) clearTimeout(debounceRef.current);
    if (!query.trim()) {
      setTextResults([]);
      setSemanticResults([]);
      setShowDropdown(false);
      return;
    }
    debounceRef.current = setTimeout(() => {
      performSearch(query, mode);
    }, 300);
    return () => {
      if (debounceRef.current) clearTimeout(debounceRef.current);
    };
  }, [query, mode, performSearch]);

  // Close on outside click
  useEffect(() => {
    function handleClick(e: MouseEvent) {
      if (containerRef.current && !containerRef.current.contains(e.target as Node)) {
        setShowDropdown(false);
      }
    }
    document.addEventListener('mousedown', handleClick);
    return () => document.removeEventListener('mousedown', handleClick);
  }, []);

  // Close on Escape
  useEffect(() => {
    function handleKey(e: KeyboardEvent) {
      if (e.key === 'Escape') {
        setShowDropdown(false);
      }
    }
    document.addEventListener('keydown', handleKey);
    return () => document.removeEventListener('keydown', handleKey);
  }, []);

  function handleSelect(id: string) {
    onSelectEntity(id);
    setQuery('');
    setTextResults([]);
    setSemanticResults([]);
    setShowDropdown(false);
  }

  // Group semantic results by entity_type
  function groupByType(results: SemanticResult[]): Record<string, SemanticResult[]> {
    const groups: Record<string, SemanticResult[]> = {};
    for (const r of results) {
      const key = r.entity_type || 'unknown';
      if (!groups[key]) groups[key] = [];
      groups[key].push(r);
    }
    return groups;
  }

  // Group text results by inferring type from id prefix
  function groupTextByType(results: TextResult[]): Record<string, TextResult[]> {
    const groups: Record<string, TextResult[]> = {};
    for (const r of results) {
      const ns = getNamespace(r.id);
      const key = ns !== 'unknown' ? ns : 'entity';
      if (!groups[key]) groups[key] = [];
      groups[key].push(r);
    }
    return groups;
  }

  const modeButtonStyle = (active: boolean): React.CSSProperties => ({
    fontFamily: "'JetBrains Mono', monospace",
    fontSize: '9px',
    padding: '2px 6px',
    border: 'none',
    borderRadius: '2px',
    cursor: 'pointer',
    transition: 'all 0.15s ease',
    color: active ? colors.teal : colors.fgFaint,
    background: active ? 'rgba(90, 173, 175, 0.15)' : 'transparent',
  });

  const resultRowStyle: React.CSSProperties = {
    padding: '10px 14px',
    display: 'flex',
    flexDirection: 'row',
    alignItems: 'center',
    gap: '10px',
    cursor: 'pointer',
    transition: 'background 0.1s ease',
  };

  return (
    <div ref={containerRef} style={{ position: 'relative' }}>
      {/* Search bar */}
      <div
        style={{
          display: 'flex',
          flexDirection: 'row',
          alignItems: 'center',
          background: colors.panel,
          border: `1px solid ${colors.borderDim}`,
          borderRadius: '3px',
          padding: '8px 12px',
          gap: '8px',
        }}
      >
        {/* Search icon */}
        <svg
          width="14"
          height="14"
          viewBox="0 0 24 24"
          fill="none"
          stroke={colors.fgFaint}
          strokeWidth="2"
          strokeLinecap="round"
          strokeLinejoin="round"
        >
          <circle cx="11" cy="11" r="8" />
          <line x1="21" y1="21" x2="16.65" y2="16.65" />
        </svg>

        {/* Input */}
        <input
          type="text"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="Search entities..."
          style={{
            flex: 1,
            background: 'transparent',
            border: 'none',
            outline: 'none',
            fontSize: '13px',
            fontFamily: "'DM Sans', sans-serif",
            color: colors.fg,
          }}
        />

        {/* Mode toggles */}
        <div style={{ display: 'flex', gap: '2px' }}>
          <button
            onClick={() => setMode('text')}
            style={modeButtonStyle(mode === 'text')}
          >
            Text
          </button>
          <button
            onClick={() => setMode('semantic')}
            style={modeButtonStyle(mode === 'semantic')}
          >
            Semantic
          </button>
        </div>

        {/* Keyboard hint */}
        <span
          style={{
            fontFamily: "'JetBrains Mono', monospace",
            fontSize: '9px',
            color: colors.fgFaint,
          }}
        >
          Cmd+K
        </span>
      </div>

      {/* Results dropdown */}
      {showDropdown && (
        <div
          style={{
            position: 'absolute',
            top: '100%',
            left: 0,
            right: 0,
            marginTop: '4px',
            background: colors.bgRaised,
            border: `1px solid ${colors.borderDim}`,
            borderRadius: '3px',
            maxHeight: '400px',
            overflowY: 'auto',
            boxShadow: '0 8px 32px rgba(0, 0, 0, 0.4)',
            zIndex: 50,
          }}
        >
          {loading && (
            <div
              style={{
                padding: '20px',
                textAlign: 'center',
                color: colors.fgFaint,
                fontSize: '12px',
                fontFamily: "'DM Sans', sans-serif",
              }}
            >
              Searching...
            </div>
          )}

          {!loading && mode === 'semantic' && semanticError && (
            <div
              style={{
                padding: '20px',
                textAlign: 'center',
                color: colors.rust,
                fontSize: '12px',
                fontFamily: "'DM Sans', sans-serif",
              }}
            >
              Semantic search unavailable (Qdrant not running)
            </div>
          )}

          {!loading && mode === 'text' && textResults.length === 0 && query.trim() && !semanticError && (
            <div
              style={{
                padding: '20px',
                textAlign: 'center',
                color: colors.fgFaint,
                fontSize: '12px',
                fontFamily: "'DM Sans', sans-serif",
              }}
            >
              No results for &apos;{query}&apos;
            </div>
          )}

          {!loading && mode === 'semantic' && !semanticError && semanticResults.length === 0 && query.trim() && (
            <div
              style={{
                padding: '20px',
                textAlign: 'center',
                color: colors.fgFaint,
                fontSize: '12px',
                fontFamily: "'DM Sans', sans-serif",
              }}
            >
              No results for &apos;{query}&apos;
            </div>
          )}

          {/* Text mode results */}
          {!loading && mode === 'text' && textResults.length > 0 && (
            <>
              {Object.entries(groupTextByType(textResults)).map(([group, items]) => (
                <div key={group}>
                  <div
                    style={{
                      padding: '6px 14px 4px',
                      fontFamily: "'JetBrains Mono', monospace",
                      fontSize: '10px',
                      color: colors.fgFaint,
                      textTransform: 'uppercase',
                      letterSpacing: '0.5px',
                    }}
                  >
                    {group}
                  </div>
                  {items.map((r) => {
                    const ns = getNamespace(r.id);
                    return (
                      <div
                        key={r.id}
                        style={resultRowStyle}
                        onClick={() => handleSelect(r.id)}
                        onMouseEnter={(e) => {
                          (e.currentTarget as HTMLElement).style.background = 'rgba(90,173,175,0.06)';
                        }}
                        onMouseLeave={(e) => {
                          (e.currentTarget as HTMLElement).style.background = 'transparent';
                        }}
                      >
                        <span
                          style={{
                            width: '6px',
                            height: '6px',
                            borderRadius: '50%',
                            background: getNamespaceColor(ns),
                            flexShrink: 0,
                          }}
                        />
                        <span
                          style={{
                            fontSize: '12.5px',
                            color: colors.fg,
                            fontFamily: "'DM Sans', sans-serif",
                            flex: 1,
                            overflow: 'hidden',
                            textOverflow: 'ellipsis',
                            whiteSpace: 'nowrap',
                          }}
                        >
                          {r.name}
                        </span>
                        <span
                          style={{
                            fontFamily: "'JetBrains Mono', monospace",
                            fontSize: '10px',
                            color: colors.fgFaint,
                          }}
                        >
                          {stripPrefix(r.id.split('-').slice(0, 2).join('-') || ns)}
                        </span>
                      </div>
                    );
                  })}
                </div>
              ))}
            </>
          )}

          {/* Semantic mode results */}
          {!loading && mode === 'semantic' && !semanticError && semanticResults.length > 0 && (
            <>
              {Object.entries(groupByType(semanticResults)).map(([group, items]) => (
                <div key={group}>
                  <div
                    style={{
                      padding: '6px 14px 4px',
                      fontFamily: "'JetBrains Mono', monospace",
                      fontSize: '10px',
                      color: colors.fgFaint,
                      textTransform: 'uppercase',
                      letterSpacing: '0.5px',
                    }}
                  >
                    {stripPrefix(group)}
                  </div>
                  {items.map((r, idx) => {
                    const ns = getNamespace(r.entity_type);
                    const id = r.payload?.id ?? `sem-${idx}`;
                    return (
                      <div
                        key={id}
                        style={resultRowStyle}
                        onClick={() => handleSelect(id)}
                        onMouseEnter={(e) => {
                          (e.currentTarget as HTMLElement).style.background = 'rgba(90,173,175,0.06)';
                        }}
                        onMouseLeave={(e) => {
                          (e.currentTarget as HTMLElement).style.background = 'transparent';
                        }}
                      >
                        <span
                          style={{
                            width: '6px',
                            height: '6px',
                            borderRadius: '50%',
                            background: getNamespaceColor(ns),
                            flexShrink: 0,
                          }}
                        />
                        <span
                          style={{
                            fontSize: '12.5px',
                            color: colors.fg,
                            fontFamily: "'DM Sans', sans-serif",
                            flex: 1,
                            overflow: 'hidden',
                            textOverflow: 'ellipsis',
                            whiteSpace: 'nowrap',
                          }}
                        >
                          {r.payload?.name ?? 'Untitled'}
                        </span>
                        <span
                          style={{
                            fontFamily: "'JetBrains Mono', monospace",
                            fontSize: '10px',
                            color: colors.fgFaint,
                          }}
                        >
                          {stripPrefix(r.entity_type)}
                        </span>
                        <span
                          style={{
                            fontFamily: "'JetBrains Mono', monospace",
                            fontSize: '10px',
                            color: colors.fgFaint,
                            marginLeft: 'auto',
                          }}
                        >
                          {Math.round(r.score * 100)}%
                        </span>
                      </div>
                    );
                  })}
                </div>
              ))}
            </>
          )}
        </div>
      )}
    </div>
  );
}
