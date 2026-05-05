import { NextRequest, NextResponse } from 'next/server';
import { queryTypeQL, describeSchema } from '@/lib/agentic-memory';

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

    // Step 1: Get the schema so we know the type hierarchy
    const schema = await describeSchema(undefined, true);
    const allEntityTypes = new Set(Object.keys(schema.entities ?? {}));

    // Step 2: Get all types for this entity
    const typeResult = await queryTypeQL(
      `match $e has id '${safeId}'; $e isa $t; fetch { "type": $t };`
    );

    let entityType = 'unknown';
    const entityTypes: string[] = [];

    if (typeResult.success && typeResult.count > 0) {
      for (const row of typeResult.results as Array<Record<string, unknown>>) {
        const typeVal = row.type;
        let label = '';
        if (typeof typeVal === 'string') {
          label = typeVal;
        } else if (typeVal && typeof typeVal === 'object' && 'label' in typeVal) {
          label = String((typeVal as Record<string, unknown>).label);
        }
        if (label && label !== 'thing') {
          entityTypes.push(label);
        }
      }

      // Pick the most specific type: the one that has no subtypes that are also in entityTypes
      // i.e., no other type in the list is a subtype of it
      const typeSet = new Set(entityTypes);
      for (const t of entityTypes) {
        const info = schema.entities?.[t];
        const subtypes = info?.subtypes ?? [];
        const hasChildInList = subtypes.some((s: string) => typeSet.has(s));
        if (!hasChildInList) {
          entityType = t;
          break;
        }
      }
    }

    // Step 3: Get attributes this type owns
    const typeInfo = schema.entities?.[entityType];
    const ownedAttrs = typeInfo?.owns ?? ['id', 'name', 'description', 'created-at'];

    // Step 4: Fetch all attributes for this entity
    // Build fetch clause with all owned attributes
    const fetchFields = ownedAttrs.map((attr: string) => `"${attr}": $e.${attr}`);
    const entity: Record<string, unknown> = { _type: entityType };

    // Try fetching all at once
    try {
      const allResult = await queryTypeQL(
        `match $e isa ${entityType}, has id '${safeId}'; fetch { ${fetchFields.join(', ')} };`
      );
      if (allResult?.success && allResult.count > 0) {
        const row = allResult.results[0] as Record<string, unknown>;
        Object.assign(entity, row);
      }
    } catch {
      // Bulk fetch failed (some attributes may not exist on this instance)
      // Fallback: fetch each attribute individually
      const attrPromises = ownedAttrs.map(async (attr: string) => {
        try {
          const r = await queryTypeQL(
            `match $e isa alh-identifiable-entity, has id '${safeId}', has ${attr} $v; fetch { "${attr}": $v };`
          );
          if (r.success && r.count > 0) {
            const row = r.results[0] as Record<string, unknown>;
            return { [attr]: row[attr] };
          }
        } catch {
          // attribute not present on this instance
        }
        return null;
      });

      const attrResults = await Promise.all(attrPromises);
      for (const r of attrResults) {
        if (r) Object.assign(entity, r);
      }
    }

    return NextResponse.json({
      success: true,
      entity,
      entityType,
    });
  } catch (error) {
    console.error('entity detail error:', error);
    return NextResponse.json({ error: String(error) }, { status: 500 });
  }
}
