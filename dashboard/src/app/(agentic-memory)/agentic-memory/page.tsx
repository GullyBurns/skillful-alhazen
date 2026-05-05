'use client';

import { useState, useCallback, useEffect, useRef } from 'react';
import SchemaTree from '@/components/agentic-memory/schema-tree';
import OverviewPanel from '@/components/agentic-memory/overview-panel';
import TypeBrowser from '@/components/agentic-memory/type-browser';
import EntityDetail from '@/components/agentic-memory/entity-detail';
import GlobalSearch from '@/components/agentic-memory/global-search';
import { colors } from '@/components/agentic-memory/tokens';

interface NavState {
  type: string | null;
  entity: string | null;
  ns: string | null;
}

function stateFromParams(params: URLSearchParams): NavState {
  return {
    type: params.get('type'),
    entity: params.get('entity'),
    ns: params.get('ns'),
  };
}

function paramsFromState(state: NavState): string {
  const params = new URLSearchParams();
  if (state.type) params.set('type', state.type);
  if (state.entity) params.set('entity', state.entity);
  if (state.ns) params.set('ns', state.ns);
  const qs = params.toString();
  return qs ? `?${qs}` : '';
}

export default function AgenticMemoryPage() {
  // Initialize state from URL on first render
  const [selectedType, setSelectedType] = useState<string | null>(null);
  const [selectedEntityId, setSelectedEntityId] = useState<string | null>(null);
  const [expandNamespace, setExpandNamespace] = useState<string | null>(null);
  const isPopState = useRef(false);
  const initialized = useRef(false);

  // Read initial state from URL
  useEffect(() => {
    if (initialized.current) return;
    initialized.current = true;
    const params = new URLSearchParams(window.location.search);
    const initial = stateFromParams(params);
    if (initial.entity) setSelectedEntityId(initial.entity);
    if (initial.type) setSelectedType(initial.type);
    if (initial.ns) setExpandNamespace(initial.ns);
  }, []);

  // Push state to URL when navigation changes (but not on popstate)
  useEffect(() => {
    if (!initialized.current) return;
    if (isPopState.current) {
      isPopState.current = false;
      return;
    }
    const state: NavState = { type: selectedType, entity: selectedEntityId, ns: expandNamespace };
    const newUrl = `/agentic-memory${paramsFromState(state)}`;
    // Only push if URL actually changed
    if (window.location.pathname + window.location.search !== newUrl) {
      window.history.pushState(state, '', newUrl);
    }
  }, [selectedType, selectedEntityId, expandNamespace]);

  // Listen for browser back/forward
  useEffect(() => {
    const handlePopState = (event: PopStateEvent) => {
      isPopState.current = true;
      const state = event.state as NavState | null;
      if (state) {
        setSelectedType(state.type);
        setSelectedEntityId(state.entity);
        setExpandNamespace(state.ns);
      } else {
        // No state = initial page load URL
        const params = new URLSearchParams(window.location.search);
        const nav = stateFromParams(params);
        setSelectedType(nav.type);
        setSelectedEntityId(nav.entity);
        setExpandNamespace(nav.ns);
      }
    };
    window.addEventListener('popstate', handlePopState);
    return () => window.removeEventListener('popstate', handlePopState);
  }, []);

  const handleSelectType = useCallback((typeName: string) => {
    setSelectedType(typeName);
    setSelectedEntityId(null);
  }, []);

  const handleSelectNone = useCallback(() => {
    setSelectedType(null);
    setSelectedEntityId(null);
  }, []);

  const handleSelectEntity = useCallback((id: string) => {
    setSelectedEntityId(id);
  }, []);

  const handleSelectNamespace = useCallback((ns: string) => {
    setExpandNamespace(ns);
    setSelectedType(null);
    setSelectedEntityId(null);
  }, []);

  const handleBack = useCallback(() => {
    // Use browser history so back button stays consistent
    window.history.back();
  }, []);

  return (
    <div
      style={{
        display: 'flex',
        height: '100vh',
        background: colors.bg,
        fontFamily: 'var(--font-dm-sans), "DM Sans", sans-serif',
        color: colors.fg,
        overflow: 'hidden',
      }}
    >
      {/* Left Pane: Schema Tree */}
      <div
        style={{
          width: 280,
          flexShrink: 0,
          borderRight: `1px solid ${colors.border}`,
          background: colors.bgRaised,
          overflow: 'hidden',
          display: 'flex',
          flexDirection: 'column',
        }}
      >
        <SchemaTree
          onSelectType={handleSelectType}
          onSelectNone={handleSelectNone}
          selectedType={selectedType}
          expandNamespace={expandNamespace}
        />
      </div>

      {/* Right Pane: Adaptive Content */}
      <div
        style={{
          flex: 1,
          display: 'flex',
          flexDirection: 'column',
          overflow: 'hidden',
        }}
      >
        {/* Global Search */}
        <div
          style={{
            padding: '12px 20px',
            borderBottom: `1px solid ${colors.borderDim}`,
            flexShrink: 0,
          }}
        >
          <GlobalSearch onSelectEntity={handleSelectEntity} />
        </div>

        {/* Content Area */}
        <div
          style={{
            flex: 1,
            overflowY: 'auto',
            padding: '16px 24px',
          }}
        >
          {selectedEntityId ? (
            <EntityDetail
              entityId={selectedEntityId}
              onSelectEntity={handleSelectEntity}
              onBack={handleBack}
            />
          ) : selectedType ? (
            <TypeBrowser
              typeName={selectedType}
              onSelectEntity={handleSelectEntity}
              onSelectType={handleSelectType}
            />
          ) : (
            <OverviewPanel
              onSelectNamespace={handleSelectNamespace}
              onSelectEntity={handleSelectEntity}
            />
          )}
        </div>
      </div>
    </div>
  );
}
