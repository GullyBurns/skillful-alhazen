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
    // Escape single quotes in ID to prevent injection
    const safeId = id.replace(/'/g, "\\'");

    const result = await queryTypeQL(
      `match $e isa alh-identifiable-entity, has id '${safeId}'; fetch { "id": $e.id, "name": $e.name, "description": $e.description, "created-at": $e.created-at };`
    );

    if (!result.success || result.count === 0) {
      return NextResponse.json({ error: `Entity not found: ${id}` }, { status: 404 });
    }

    return NextResponse.json({
      success: true,
      entity: result.results[0],
    });
  } catch (error) {
    console.error('entity detail error:', error);
    return NextResponse.json({ error: String(error) }, { status: 500 });
  }
}
