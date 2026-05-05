import { NextRequest, NextResponse } from 'next/server';
import { queryTypeQL, describeSchema } from '@/lib/agentic-memory';

interface NeighborNode {
  id: string;
  label: string;
  type: string;
}

interface NeighborEdge {
  source: string;
  target: string;
  relationType: string;
  sourceRole: string;
  targetRole: string;
}

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

    // Get the center entity info
    const centerResult = await queryTypeQL(
      `match $e isa alh-identifiable-entity, has id '${safeId}'; fetch { "id": $e.id, "name": $e.name };`
    );

    if (!centerResult.success || centerResult.count === 0) {
      return NextResponse.json({ error: `Entity not found: ${id}` }, { status: 404 });
    }

    const centerData = centerResult.results[0] as Record<string, string>;
    const center = {
      id: centerData.id ?? id,
      name: centerData.name ?? id,
      type: 'entity',
    };

    // Dynamically discover all relations from the schema
    const schema = await describeSchema(undefined, false);
    const allRelations = schema.relations ?? {};

    // Build query pairs: for each relation, for each pair of roles, try the entity in each role
    const queryPromises: Promise<{
      relationType: string;
      centerRole: string;
      neighborRole: string;
      result: { success: boolean; count: number; results: unknown[] } | null;
    }>[] = [];

    for (const [relName, relInfo] of Object.entries(allRelations)) {
      const roles = (relInfo.roles ?? []).map((r: string) => {
        // roles come as "relationType:roleName" — extract just the role name
        const parts = r.split(':');
        return parts.length > 1 ? parts[1] : r;
      });

      // For each pair of distinct roles, try the entity in each position
      for (let i = 0; i < roles.length; i++) {
        for (let j = 0; j < roles.length; j++) {
          if (i === j) continue;
          const centerRole = roles[i];
          const neighborRole = roles[j];
          const typeql = `match $e isa alh-identifiable-entity, has id '${safeId}'; (${centerRole}: $e, ${neighborRole}: $other) isa ${relName}; $other has id $oid, has name $oname; fetch { "id": $oid, "name": $oname };`;
          queryPromises.push(
            queryTypeQL(typeql)
              .then((result) => ({ relationType: relName, centerRole, neighborRole, result }))
              .catch(() => ({ relationType: relName, centerRole, neighborRole, result: null }))
          );
        }
      }
    }

    // Execute all queries in parallel (with concurrency — Promise.all is fine since
    // each query is lightweight and the TypeDB driver handles connection pooling)
    const relationResults = await Promise.all(queryPromises);

    // Deduplicate nodes by ID, collect edges
    const nodesMap = new Map<string, NeighborNode>();
    const edges: NeighborEdge[] = [];

    for (const { relationType, centerRole, neighborRole, result } of relationResults) {
      if (!result?.success || result.count === 0) continue;

      for (const row of result.results as Array<Record<string, string>>) {
        const neighborId = row.id;
        const neighborName = row.name ?? neighborId;

        if (!neighborId || neighborId === id) continue;

        if (!nodesMap.has(neighborId)) {
          nodesMap.set(neighborId, {
            id: neighborId,
            label: neighborName,
            type: 'entity',
          });
        }

        // Avoid duplicate edges (same relation + same neighbor)
        const edgeKey = `${relationType}:${centerRole}:${neighborRole}:${neighborId}`;
        const existing = edges.find(
          (e) =>
            e.relationType === relationType &&
            e.sourceRole === centerRole &&
            e.targetRole === neighborRole &&
            e.target === neighborId
        );
        if (!existing) {
          edges.push({
            source: id,
            target: neighborId,
            relationType,
            sourceRole: centerRole,
            targetRole: neighborRole,
          });
        }
      }
    }

    return NextResponse.json({
      center,
      nodes: Array.from(nodesMap.values()),
      edges,
    });
  } catch (error) {
    console.error('entity neighbors error:', error);
    return NextResponse.json({ error: String(error) }, { status: 500 });
  }
}
