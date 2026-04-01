import { NextRequest, NextResponse } from 'next/server';
import { listPapers } from '@/lib/techrecon';

export async function GET(req: NextRequest) {
  const systemId = req.nextUrl.searchParams.get('system');
  if (!systemId) {
    return NextResponse.json({ error: 'system parameter required' }, { status: 400 });
  }
  try {
    const data = await listPapers(systemId);
    return NextResponse.json(data);
  } catch (error) {
    console.error('Papers error:', error);
    return NextResponse.json({ error: 'Failed to fetch papers' }, { status: 500 });
  }
}
