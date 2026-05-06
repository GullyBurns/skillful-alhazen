import { NextRequest, NextResponse } from 'next/server';
import { searchSemantic } from '@/lib/agentic-memory';

export async function GET(request: NextRequest) {
  try {
    const { searchParams } = new URL(request.url);
    const query = searchParams.get('query');

    if (!query) {
      return NextResponse.json(
        { error: 'Missing required parameter: query' },
        { status: 400 }
      );
    }

    const collection = searchParams.get('collection') || undefined;
    const limitStr = searchParams.get('limit');
    const thresholdStr = searchParams.get('threshold');
    const limit = limitStr ? parseInt(limitStr, 10) : undefined;
    const threshold = thresholdStr ? parseFloat(thresholdStr) : undefined;

    const data = await searchSemantic(query, collection, limit, threshold);
    return NextResponse.json(data);
  } catch (error) {
    console.error('searchSemantic error:', error);
    return NextResponse.json({ error: String(error) }, { status: 500 });
  }
}
