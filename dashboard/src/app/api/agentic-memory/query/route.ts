import { NextRequest, NextResponse } from 'next/server';
import { queryTypeQL } from '@/lib/agentic-memory';

export async function POST(request: NextRequest) {
  try {
    const body = await request.json();
    const { typeql, limit } = body as { typeql?: string; limit?: number };

    if (!typeql || typeof typeql !== 'string') {
      return NextResponse.json(
        { error: 'Missing required field: typeql' },
        { status: 400 }
      );
    }

    // Block write operations — only allow read-only queries
    const normalized = typeql.trim().toLowerCase();
    if (
      normalized.startsWith('insert') ||
      normalized.startsWith('delete') ||
      normalized.startsWith('define') ||
      normalized.startsWith('undefine') ||
      normalized.startsWith('redefine')
    ) {
      return NextResponse.json(
        { error: 'Only read-only queries (match/fetch) are allowed' },
        { status: 403 }
      );
    }

    const data = await queryTypeQL(typeql, limit);
    return NextResponse.json(data);
  } catch (error) {
    console.error('queryTypeQL error:', error);
    return NextResponse.json({ error: String(error) }, { status: 500 });
  }
}
