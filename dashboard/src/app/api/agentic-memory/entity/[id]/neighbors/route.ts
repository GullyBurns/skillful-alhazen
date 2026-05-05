import { NextRequest, NextResponse } from 'next/server';
import { queryTypeQL } from '@/lib/agentic-memory';

export async function GET(
  _request: NextRequest,
  { params }: { params: Promise<{ id: string }> }
) {
  const { id } = await params;

  if (!id) {
    return NextResponse.json({ error: 'Entity ID is required' }, { status: 400 });
  }

  try {
    const safeId = id.replace(/'/g, "\\'");

    // Single query: find ALL relations this entity participates in
    const result = await queryTypeQL(
      `match $e has id '${safeId}'; ($role: $e, $other_role: $other) isa $rel; $other has id $oid, has name $oname; fetch { "id": $oid, "name": $oname, "rel": $rel };`,
      200
    );

    if (!result.success) {
      return NextResponse.json({ center: { id, name: id, type: 'entity' }, nodes: [], edges: [] });
    }

    // Build nodes and edges from results
    const nodesMap = new Map<string, { id: string; label: string; type: string }>();
    const edgeSet = new Set<string>();
    const edges: { source: string; target: string; relationType: string; sourceRole: string; targetRole: string }[] = [];

    for (const row of result.results as Array<Record<string, unknown>>) {
      const neighborId = row.id as string;
      const neighborName = (row.name as string) ?? neighborId;
      const relInfo = row.rel as { label?: string; kind?: string } | string;
      const relType = typeof relInfo === 'string' ? relInfo : relInfo?.label ?? 'unknown';

      if (!neighborId || neighborId === id) continue;

      if (!nodesMap.has(neighborId)) {
        nodesMap.set(neighborId, { id: neighborId, label: neighborName, type: 'entity' });
      }

      // Deduplicate edges
      const edgeKey = `${relType}:${neighborId}`;
      if (!edgeSet.has(edgeKey)) {
        edgeSet.add(edgeKey);
        edges.push({
          source: id,
          target: neighborId,
          relationType: relType,
          sourceRole: 'participant',
          targetRole: 'participant',
        });
      }
    }

    return NextResponse.json({
      center: { id, name: id, type: 'entity' },
      nodes: Array.from(nodesMap.values()),
      edges,
    });
  } catch (error) {
    console.error('entity neighbors error:', error);
    return NextResponse.json({ error: String(error) }, { status: 500 });
  }
}
