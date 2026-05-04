import { NextRequest, NextResponse } from 'next/server';
import { queryTypeQL } from '@/lib/agentic-memory';

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

// Each relation type definition: [relationType, role1, role2]
// role1 is the role the center entity plays; role2 is the neighbor's role
const RELATION_DEFS: [string, string, string][] = [
  ['aboutness', 'subject', 'note'],
  ['aboutness', 'note', 'subject'],
  ['works-at', 'employee', 'employer'],
  ['works-at', 'employer', 'employee'],
  ['collection-membership', 'member', 'collection'],
  ['collection-membership', 'collection', 'member'],
  ['episode-mention', 'mentioned-entity', 'episode'],
  ['episode-mention', 'episode', 'mentioned-entity'],
  ['authorship', 'author', 'authored-work'],
  ['authorship', 'authored-work', 'author'],
  ['affiliation', 'affiliated-person', 'affiliated-org'],
  ['affiliation', 'affiliated-org', 'affiliated-person'],
  ['entity-alias', 'primary-entity', 'aliased-entity'],
  ['entity-alias', 'aliased-entity', 'primary-entity'],
  ['relationship-context', 'context-subject', 'context-object'],
  ['relationship-context', 'context-object', 'context-subject'],
  ['project-involvement', 'involved-person', 'project'],
  ['project-involvement', 'project', 'involved-person'],
  ['tool-familiarity', 'tool-user', 'tool'],
  ['tool-familiarity', 'tool', 'tool-user'],
];

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

    // First, get the center entity info
    const centerResult = await queryTypeQL(
      `match $e isa identifiable-entity, has id '${safeId}'; fetch { "id": $e.id, "name": $e.name };`
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

    // Query each relation type in parallel
    const queryPromises = RELATION_DEFS.map(([relationType, centerRole, neighborRole]) => {
      const typeql = `match $e isa identifiable-entity, has id '${safeId}'; (${centerRole}: $e, ${neighborRole}: $other) isa ${relationType}; $other has id $oid, has name $oname; fetch { "id": $oid, "name": $oname };`;
      return queryTypeQL(typeql)
        .then((result) => ({ relationType, centerRole, neighborRole, result }))
        .catch(() => ({ relationType, centerRole, neighborRole, result: null }));
    });

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

        edges.push({
          source: id,
          target: neighborId,
          relationType,
          sourceRole: centerRole,
          targetRole: neighborRole,
        });
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
