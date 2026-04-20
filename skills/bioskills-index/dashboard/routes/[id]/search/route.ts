import { NextRequest, NextResponse } from 'next/server';
import { search } from '@/lib/bioskills-index';

export async function GET(
  req: NextRequest,
  { params }: { params: Promise<{ id: string }> }
) {
  try {
    const { id } = await params;
    const q = req.nextUrl.searchParams.get('q') || '';
    const topK = parseInt(req.nextUrl.searchParams.get('top_k') || '10');
    if (!q) return NextResponse.json({ error: 'q parameter required' }, { status: 400 });
    const data = await search(id, q, topK);
    return NextResponse.json(data);
  } catch (error) {
    console.error('search error:', error);
    return NextResponse.json({ error: 'Search failed' }, { status: 500 });
  }
}
