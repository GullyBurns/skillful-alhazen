import { NextRequest, NextResponse } from 'next/server';
import { getContext } from '@/lib/agentic-memory';

export async function GET(request: NextRequest) {
  const personId = request.nextUrl.searchParams.get('person');
  if (!personId) {
    return NextResponse.json({ error: 'person parameter required' }, { status: 400 });
  }
  try {
    const data = await getContext(personId);
    return NextResponse.json(data);
  } catch (error) {
    console.error('getContext error:', error);
    return NextResponse.json({ error: String(error) }, { status: 500 });
  }
}
