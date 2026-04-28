import { NextRequest, NextResponse } from 'next/server';
import { listClaims, recallPerson } from '@/lib/agentic-memory';

export async function GET(request: NextRequest) {
  const factType = request.nextUrl.searchParams.get('fact_type') || undefined;
  const personId = request.nextUrl.searchParams.get('person') || undefined;
  const limit = parseInt(request.nextUrl.searchParams.get('limit') || '50', 10);
  try {
    if (personId) {
      const data = await recallPerson(personId);
      return NextResponse.json(data);
    }
    const data = await listClaims(factType, limit);
    return NextResponse.json(data);
  } catch (error) {
    console.error('listClaims error:', error);
    return NextResponse.json({ error: String(error) }, { status: 500 });
  }
}
