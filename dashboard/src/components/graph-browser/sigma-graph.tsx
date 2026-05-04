'use client';

import { useRef, useEffect, useCallback } from 'react';
import type { GraphNode, GraphEdge } from '@/lib/graph-browser';
import { typeToColor } from '@/lib/graph-browser';

interface SigmaGraphProps {
  nodes: GraphNode[];
  edges: GraphEdge[];
  onNodeClick?: (nodeId: string) => void;
  selectedNodeId?: string;
  className?: string;
}

export default function SigmaGraph({
  nodes,
  edges,
  onNodeClick,
  selectedNodeId,
  className,
}: SigmaGraphProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const sigmaRef = useRef<unknown>(null);
  const graphRef = useRef<unknown>(null);

  const onNodeClickRef = useRef(onNodeClick);
  onNodeClickRef.current = onNodeClick;

  const mount = useCallback(async () => {
    if (!containerRef.current || nodes.length === 0) return;

    // Clean up previous instance
    if (sigmaRef.current) {
      (sigmaRef.current as { kill: () => void }).kill();
      sigmaRef.current = null;
      graphRef.current = null;
    }

    const { default: Graph } = await import('graphology');
    const { default: Sigma } = await import('sigma');
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    const fa2: any = await import('graphology-layout-forceatlas2');

    const graph = new Graph();

    // Add nodes with random initial positions
    for (const node of nodes) {
      const isSelected = node.id === selectedNodeId;
      graph.addNode(node.id, {
        label: node.label || node.id,
        color: isSelected ? '#22d3ee' : typeToColor(node.type),
        size: isSelected ? 12 : 7,
        x: Math.random() * 100,
        y: Math.random() * 100,
      });
    }

    // Add edges (deduplicate by source+target+relationType)
    const edgeSet = new Set<string>();
    for (const edge of edges) {
      const key = `${edge.source}--${edge.target}--${edge.relationType}`;
      if (edgeSet.has(key)) continue;
      edgeSet.add(key);
      if (graph.hasNode(edge.source) && graph.hasNode(edge.target)) {
        graph.addEdge(edge.source, edge.target, {
          label: edge.relationType,
        });
      }
    }

    // Run ForceAtlas2 layout
    fa2.assign(graph, { iterations: 50 });

    // Mount Sigma
    const sigma = new Sigma(graph, containerRef.current, {
      renderLabels: true,
      labelColor: { color: '#e4e4e7' },
      labelSize: 12,
      defaultEdgeColor: '#52525b',
      defaultEdgeType: 'line',
      allowInvalidContainer: true,
    });

    sigma.on('clickNode', ({ node }: { node: string }) => {
      onNodeClickRef.current?.(node);
    });

    sigmaRef.current = sigma;
    graphRef.current = graph;
  }, [nodes, edges, selectedNodeId]);

  useEffect(() => {
    mount();

    return () => {
      if (sigmaRef.current) {
        (sigmaRef.current as { kill: () => void }).kill();
        sigmaRef.current = null;
        graphRef.current = null;
      }
    };
  }, [mount]);

  if (nodes.length === 0) {
    return (
      <div
        className={`flex items-center justify-center text-zinc-500 text-sm ${className ?? ''}`}
        style={{ minHeight: 300 }}
      >
        No graph data. Select an entity to view its neighborhood.
      </div>
    );
  }

  return (
    <div
      ref={containerRef}
      className={`relative ${className ?? ''}`}
      style={{ minHeight: 400, height: '100%' }}
    />
  );
}
