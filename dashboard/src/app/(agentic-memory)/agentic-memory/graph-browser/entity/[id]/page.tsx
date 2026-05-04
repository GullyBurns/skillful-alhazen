'use client';

import { useState, useEffect, useCallback } from 'react';
import { useParams, useRouter } from 'next/navigation';
import Link from 'next/link';
import { ArrowLeft, Loader2 } from 'lucide-react';
import { Badge } from '@/components/ui/badge';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table';
import { Separator } from '@/components/ui/separator';
import SigmaGraph from '@/components/graph-browser/sigma-graph';
import GraphControls from '@/components/graph-browser/graph-controls';
import type { GraphNode, GraphEdge } from '@/lib/graph-browser';
import { typeToColor } from '@/lib/graph-browser';

const linkClass =
  'text-cyan-400 font-semibold underline underline-offset-2 hover:text-blue-400 transition-colors';

interface EntityData {
  id: string;
  name?: string;
  type?: string;
  description?: string;
  'created-at'?: string;
  [key: string]: unknown;
}

interface NeighborData {
  center: { id: string; name: string; type?: string };
  nodes: GraphNode[];
  edges: GraphEdge[];
}

export default function EntityDetailPage() {
  const params = useParams();
  const router = useRouter();
  const entityId = params.id as string;

  const [entity, setEntity] = useState<EntityData | null>(null);
  const [neighbors, setNeighbors] = useState<NeighborData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!entityId) return;

    let cancelled = false;
    setLoading(true);
    setError(null);

    const encodedId = encodeURIComponent(entityId);

    Promise.all([
      fetch(`/api/agentic-memory/entity/${encodedId}`).then((res) => {
        if (!res.ok) throw new Error(`Entity API ${res.status}`);
        return res.json();
      }),
      fetch(`/api/agentic-memory/entity/${encodedId}/neighbors`).then((res) => {
        if (!res.ok) throw new Error(`Neighbors API ${res.status}`);
        return res.json();
      }),
    ])
      .then(([entityRes, neighborsRes]) => {
        if (cancelled) return;
        if (entityRes.success && entityRes.entity) {
          setEntity(entityRes.entity as EntityData);
        } else {
          setError(entityRes.error || 'Entity not found');
        }
        if (neighborsRes.center) {
          setNeighbors(neighborsRes as NeighborData);
        }
      })
      .catch((err) => {
        if (!cancelled) setError(String(err));
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });

    return () => {
      cancelled = true;
    };
  }, [entityId]);

  const handleGraphNodeClick = useCallback(
    (nodeId: string) => {
      if (nodeId !== entityId) {
        router.push(
          `/agentic-memory/graph-browser/entity/${encodeURIComponent(nodeId)}`,
        );
      }
    },
    [entityId, router],
  );

  // Build the full graph (center + neighbors)
  const graphNodes: GraphNode[] = [];
  const graphEdges: GraphEdge[] = [];
  if (neighbors) {
    const centerNode: GraphNode = {
      id: neighbors.center.id,
      label: neighbors.center.name ?? neighbors.center.id,
      type: neighbors.center.type ?? 'entity',
    };
    graphNodes.push(centerNode, ...neighbors.nodes);
    graphEdges.push(...neighbors.edges);
  }

  // Attributes to display (non-null, non-id, non-type)
  const attrs: [string, unknown][] = entity
    ? Object.entries(entity).filter(
        ([k, v]) => v != null && k !== 'id' && k !== 'type' && k !== 'name',
      )
    : [];

  // Related entities from neighbors
  const relatedEntities: {
    id: string;
    label: string;
    type: string;
    relationType: string;
    role: string;
  }[] = [];
  if (neighbors) {
    for (const edge of neighbors.edges) {
      const neighborId =
        edge.source === entityId ? edge.target : edge.source;
      const neighborNode = neighbors.nodes.find((n) => n.id === neighborId);
      if (neighborNode) {
        const role =
          edge.source === entityId ? edge.targetRole : edge.sourceRole;
        relatedEntities.push({
          id: neighborNode.id,
          label: neighborNode.label,
          type: neighborNode.type,
          relationType: edge.relationType,
          role,
        });
      }
    }
  }

  if (loading) {
    return (
      <div className="min-h-screen bg-zinc-950 text-zinc-100 flex items-center justify-center">
        <div className="flex items-center gap-3 text-zinc-500">
          <Loader2 className="w-6 h-6 animate-spin" />
          <span className="text-sm">Loading entity...</span>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-zinc-950 text-zinc-100">
      {/* Header */}
      <header className="border-b border-zinc-800 bg-zinc-900/50 backdrop-blur-sm">
        <div className="container mx-auto px-4 py-4">
          <Link
            href="/agentic-memory/graph-browser"
            className={`inline-flex items-center gap-2 text-sm mb-3 ${linkClass}`}
          >
            <ArrowLeft className="w-4 h-4" />
            Back to Graph Browser
          </Link>

          {error && (
            <div className="bg-red-900/20 border border-red-800 text-red-300 px-4 py-3 rounded-lg mt-2">
              {error}
            </div>
          )}

          {entity && (
            <div className="flex items-start gap-4 mt-1">
              <div className="flex-1">
                <h1 className="text-2xl font-bold bg-gradient-to-r from-cyan-400 to-blue-500 bg-clip-text text-transparent">
                  {entity.name ?? entityId}
                </h1>
                <div className="flex items-center gap-3 mt-2">
                  {entity.type && (
                    <Badge
                      variant="secondary"
                      className="text-xs"
                      style={{
                        borderColor: typeToColor(entity.type),
                        color: typeToColor(entity.type),
                      }}
                    >
                      {entity.type}
                    </Badge>
                  )}
                  <span className="font-mono text-xs text-zinc-500">
                    {entityId}
                  </span>
                </div>
              </div>
            </div>
          )}
        </div>
      </header>

      <main className="container mx-auto px-4 py-6 space-y-6">
        {/* Two-column grid: Attributes + Connections graph */}
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          {/* Left: Attributes */}
          <Card className="bg-zinc-900 border-zinc-800">
            <CardHeader className="pb-3">
              <CardTitle className="text-sm font-semibold text-zinc-300 uppercase tracking-wide">
                Attributes
              </CardTitle>
            </CardHeader>
            <CardContent>
              {attrs.length === 0 ? (
                <p className="text-sm text-zinc-500 italic">
                  No additional attributes.
                </p>
              ) : (
                <Table>
                  <TableHeader>
                    <TableRow className="border-zinc-800">
                      <TableHead className="text-zinc-400 text-xs w-[160px]">
                        Key
                      </TableHead>
                      <TableHead className="text-zinc-400 text-xs">
                        Value
                      </TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {attrs.map(([key, value]) => (
                      <TableRow key={key} className="border-zinc-800">
                        <TableCell className="font-mono text-xs text-zinc-400 py-2">
                          {key}
                        </TableCell>
                        <TableCell className="text-xs text-zinc-300 py-2 break-words max-w-[300px]">
                          {formatValue(value)}
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              )}
            </CardContent>
          </Card>

          {/* Right: Connections graph */}
          <Card className="bg-zinc-900 border-zinc-800">
            <CardHeader className="pb-3">
              <CardTitle className="text-sm font-semibold text-zinc-300 uppercase tracking-wide">
                Connections
              </CardTitle>
            </CardHeader>
            <CardContent className="relative">
              {graphNodes.length === 0 ? (
                <p className="text-sm text-zinc-500 italic">
                  No connections found.
                </p>
              ) : (
                <div className="relative" style={{ minHeight: 400 }}>
                  <SigmaGraph
                    nodes={graphNodes}
                    edges={graphEdges}
                    onNodeClick={handleGraphNodeClick}
                    selectedNodeId={entityId}
                    className="h-full w-full"
                  />
                  <div className="absolute top-2 right-2 z-10">
                    <GraphControls />
                  </div>
                </div>
              )}
            </CardContent>
          </Card>
        </div>

        {/* Related Entities table */}
        {relatedEntities.length > 0 && (
          <Card className="bg-zinc-900 border-zinc-800">
            <CardHeader className="pb-3">
              <CardTitle className="text-sm font-semibold text-zinc-300 uppercase tracking-wide">
                Related Entities
              </CardTitle>
            </CardHeader>
            <CardContent>
              <Table>
                <TableHeader>
                  <TableRow className="border-zinc-800">
                    <TableHead className="text-zinc-400 text-xs">
                      Name
                    </TableHead>
                    <TableHead className="text-zinc-400 text-xs">
                      Type
                    </TableHead>
                    <TableHead className="text-zinc-400 text-xs">
                      Relation
                    </TableHead>
                    <TableHead className="text-zinc-400 text-xs">
                      Role
                    </TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {relatedEntities.map((rel, idx) => (
                    <TableRow key={`${rel.id}-${idx}`} className="border-zinc-800">
                      <TableCell className="py-2">
                        <Link
                          href={`/agentic-memory/graph-browser/entity/${encodeURIComponent(rel.id)}`}
                          className={`text-xs ${linkClass}`}
                        >
                          {rel.label}
                        </Link>
                      </TableCell>
                      <TableCell className="py-2">
                        <Badge
                          variant="outline"
                          className="text-xs"
                          style={{
                            borderColor: typeToColor(rel.type),
                            color: typeToColor(rel.type),
                          }}
                        >
                          {rel.type}
                        </Badge>
                      </TableCell>
                      <TableCell className="font-mono text-xs text-zinc-400 py-2">
                        {rel.relationType}
                      </TableCell>
                      <TableCell className="font-mono text-xs text-zinc-500 py-2">
                        {rel.role}
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </CardContent>
          </Card>
        )}

        <Separator className="bg-zinc-800" />

        {/* Description if long */}
        {entity?.description && (
          <Card className="bg-zinc-900 border-zinc-800">
            <CardHeader className="pb-3">
              <CardTitle className="text-sm font-semibold text-zinc-300 uppercase tracking-wide">
                Description
              </CardTitle>
            </CardHeader>
            <CardContent>
              <p className="text-sm text-zinc-300 whitespace-pre-wrap">
                {entity.description}
              </p>
            </CardContent>
          </Card>
        )}
      </main>
    </div>
  );
}

function formatValue(value: unknown): string {
  if (value == null) return '--';
  if (typeof value === 'string' && /^\d{4}-\d{2}-\d{2}T/.test(value)) {
    return new Date(value).toLocaleString();
  }
  if (typeof value === 'boolean') return value ? 'Yes' : 'No';
  if (typeof value === 'number') return String(value);
  const s = String(value);
  if (s.length > 300) return s.slice(0, 300) + '...';
  return s;
}
