import { NextRequest, NextResponse } from 'next/server';
import { queryTypeQL, describeSchema } from '@/lib/agentic-memory';

// Common attributes present on most entities — always try to fetch these
const COMMON_ATTRS = [
  'id', 'name', 'description', 'created-at', 'updated-at',
  'provenance', 'source-uri', 'iri',
];

// Attributes to skip (inherited but rarely useful for display)
const SKIP_ATTRS = new Set([
  'license', 'valid-from', 'valid-until',
  'content-hash', 'mime-type', 'file-size', 'token-count',
]);

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

    // Step 1: Get the schema
    const schema = await describeSchema(undefined, true);

    // Step 2: Get entity type
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

      const typeSet = new Set(entityTypes);
      for (const t of entityTypes) {
        const info = schema.entities?.[t];
        const subtypes = info?.subtypes ?? [];
        if (!subtypes.some((s: string) => typeSet.has(s))) {
          entityType = t;
          break;
        }
      }
    }

    // Step 3: Build a focused attribute list
    // Start with common attrs, add type-specific ones (skip noise)
    const typeInfo = schema.entities?.[entityType];
    const ownedAttrs = typeInfo?.owns ?? COMMON_ATTRS;
    const attrsToFetch = ownedAttrs.filter((a: string) => !SKIP_ATTRS.has(a));

    // Step 4: Fetch in a SINGLE query using $e.attr syntax
    // Build small batches to avoid query failures from missing optional attrs
    const entity: Record<string, unknown> = { _type: entityType };

    // Try the full fetch first (fast path — works if entity has all attrs)
    const fetchFields = attrsToFetch.map((attr: string) => `"${attr}": $e.${attr}`);
    try {
      const result = await queryTypeQL(
        `match $e isa ${entityType}, has id '${safeId}'; fetch { ${fetchFields.join(', ')} };`
      );
      if (result?.success && result.count > 0) {
        Object.assign(entity, result.results[0] as Record<string, unknown>);
        return NextResponse.json({ success: true, entity, entityType });
      }
    } catch {
      // Full fetch failed — some attrs don't exist on this instance
    }

    // Fallback: fetch in small batches of 5 (much faster than 1-by-1)
    const BATCH_SIZE = 5;
    const batches: string[][] = [];
    for (let i = 0; i < attrsToFetch.length; i += BATCH_SIZE) {
      batches.push(attrsToFetch.slice(i, i + BATCH_SIZE));
    }

    await Promise.all(batches.map(async (batch) => {
      const fields = batch.map((attr: string) => `"${attr}": $e.${attr}`);
      try {
        const r = await queryTypeQL(
          `match $e isa alh-identifiable-entity, has id '${safeId}'; fetch { ${fields.join(', ')} };`
        );
        if (r?.success && r.count > 0) {
          Object.assign(entity, r.results[0] as Record<string, unknown>);
        }
      } catch {
        // Batch failed — try individual attrs from this batch
        for (const attr of batch) {
          try {
            const r = await queryTypeQL(
              `match $e isa alh-identifiable-entity, has id '${safeId}'; fetch { "${attr}": $e.${attr} };`
            );
            if (r?.success && r.count > 0) {
              Object.assign(entity, r.results[0] as Record<string, unknown>);
            }
          } catch {
            // attr doesn't exist on this instance
          }
        }
      }
    }));

    return NextResponse.json({ success: true, entity, entityType });
  } catch (error) {
    console.error('entity detail error:', error);
    return NextResponse.json({ error: String(error) }, { status: 500 });
  }
}
