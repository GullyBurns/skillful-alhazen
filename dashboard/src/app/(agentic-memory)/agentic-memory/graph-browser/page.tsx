'use client';

import { useState, useEffect, useCallback } from 'react';
import { ArrowLeft, Network } from 'lucide-react';
import Link from 'next/link';
import { Tabs, TabsList, TabsTrigger, TabsContent } from '@/components/ui/tabs';
import type { SchemaResult } from '@/lib/agentic-memory';
import type { GraphNode, GraphEdge } from '@/lib/graph-browser';

import SchemaTree from '@/components/graph-browser/schema-tree';
import InstanceSearch from '@/components/graph-browser/instance-search';
import SigmaGraph from '@/components/graph-browser/sigma-graph';
import EntityDetailPanel from '@/components/graph-browser/entity-detail-panel';

const linkClass =
  'text-cyan-400 font-semibold underline underline-offset-2 hover:text-blue-400 transition-colors';

export default function GraphBrowserPage() {
  const [schema, setSchema] = useState<SchemaResult | null>(null);
  const [selectedType, setSelectedType] = useState<string | undefined>();
  const [selectedEntityId, setSelectedEntityId] = useState<string | null>(null);
  const [graphNodes, setGraphNodes] = useState<GraphNode[]>([]);
  const [graphEdges, setGraphEdges] = useState<GraphEdge[]>([]);
  const [activeTab, setActiveTab] = useState('search');

  // Fetch schema on mount
  useEffect(() => {
    fetch('/api/agentic-memory/schema?full=true')
      .then((res) => res.json())
      .then((data) => setSchema(data as SchemaResult))
      .catch((err) => console.error('Failed to load schema:', err));
  }, []);

  // Fetch neighbors when entity is selected
  const fetchNeighbors = useCallback(async (entityId: string) => {
    try {
      const res = await fetch(
        `/api/agentic-memory/entity/${encodeURIComponent(entityId)}/neighbors`,
      );
      const data = await res.json();

      if (data.center && data.nodes) {
        const centerNode: GraphNode = {
          id: data.center.id,
          label: data.center.name ?? data.center.id,
          type: data.center.type ?? 'entity',
        };
        const neighborNodes: GraphNode[] = (
          data.nodes as Array<{ id: string; label: string; type: string }>
        ).map((n) => ({
          id: n.id,
          label: n.label ?? n.id,
          type: n.type ?? 'entity',
        }));

        setGraphNodes([centerNode, ...neighborNodes]);
        setGraphEdges(data.edges ?? []);
        setActiveTab('graph');
      }
    } catch (err) {
      console.error('Failed to fetch neighbors:', err);
    }
  }, []);

  const handleEntitySelect = useCallback(
    (entityId: string) => {
      setSelectedEntityId(entityId);
      fetchNeighbors(entityId);
    },
    [fetchNeighbors],
  );

  const handleTypeSelect = useCallback((typeName: string) => {
    setSelectedType((prev) => (prev === typeName ? undefined : typeName));
    setActiveTab('search');
  }, []);

  const handleGraphNodeClick = useCallback(
    (nodeId: string) => {
      setSelectedEntityId(nodeId);
      fetchNeighbors(nodeId);
    },
    [fetchNeighbors],
  );

  const handleDetailNavigate = useCallback(
    (entityId: string) => {
      setSelectedEntityId(entityId);
      fetchNeighbors(entityId);
    },
    [fetchNeighbors],
  );

  const handleDetailClose = useCallback(() => {
    setSelectedEntityId(null);
  }, []);

  return (
    <div className="flex flex-col h-screen bg-zinc-950 text-zinc-100">
      {/* Header */}
      <header className="border-b border-zinc-800 bg-zinc-900/50 backdrop-blur-sm shrink-0">
        <div className="flex items-center gap-6 px-4 py-3">
          <Link
            href="/agentic-memory"
            className={`flex items-center gap-2 text-sm ${linkClass}`}
          >
            <ArrowLeft className="w-4 h-4" />
            Agentic Memory
          </Link>
          <div className="flex items-center gap-3">
            <Network className="w-5 h-5 text-cyan-400" />
            <div>
              <h1 className="text-xl font-bold bg-gradient-to-r from-cyan-400 to-blue-400 bg-clip-text text-transparent">
                Knowledge Graph Browser
              </h1>
              <p className="text-xs text-zinc-500">
                Explore entities, relations, and schema
              </p>
            </div>
          </div>
        </div>
      </header>

      {/* Three-panel layout */}
      <div className="flex flex-1 overflow-hidden">
        {/* Left panel - Schema tree */}
        <aside className="w-72 border-r border-zinc-800 bg-zinc-950 overflow-hidden flex flex-col shrink-0">
          <SchemaTree
            schema={schema}
            onTypeSelect={handleTypeSelect}
            selectedType={selectedType}
          />
        </aside>

        {/* Center panel - Search + Graph tabs */}
        <main className="flex-1 flex flex-col overflow-hidden">
          <Tabs
            value={activeTab}
            onValueChange={setActiveTab}
            className="flex flex-col h-full"
          >
            <div className="border-b border-zinc-800 px-4">
              <TabsList className="bg-transparent h-10">
                <TabsTrigger
                  value="search"
                  className="data-[state=active]:bg-zinc-800 text-xs"
                >
                  Search
                </TabsTrigger>
                <TabsTrigger
                  value="graph"
                  className="data-[state=active]:bg-zinc-800 text-xs"
                >
                  Graph
                </TabsTrigger>
              </TabsList>
            </div>

            <TabsContent value="search" className="flex-1 overflow-hidden mt-0">
              <InstanceSearch
                selectedType={selectedType}
                onEntitySelect={handleEntitySelect}
              />
            </TabsContent>

            <TabsContent value="graph" className="flex-1 overflow-hidden mt-0">
              <SigmaGraph
                nodes={graphNodes}
                edges={graphEdges}
                onNodeClick={handleGraphNodeClick}
                selectedNodeId={selectedEntityId ?? undefined}
                className="h-full"
              />
            </TabsContent>
          </Tabs>
        </main>

        {/* Right panel - Entity detail (conditional) */}
        {selectedEntityId && (
          <aside className="w-80 border-l border-zinc-800 bg-zinc-950 overflow-hidden flex flex-col shrink-0">
            <EntityDetailPanel
              entityId={selectedEntityId}
              onClose={handleDetailClose}
              onNavigate={handleDetailNavigate}
            />
          </aside>
        )}
      </div>
    </div>
  );
}
