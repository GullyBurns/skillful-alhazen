import { NextRequest, NextResponse } from 'next/server';
import { listCandidates } from '@/lib/jobhunt';

export async function GET(request: NextRequest) {
  const searchParams = request.nextUrl.searchParams;
  const status = searchParams.get('status') || undefined;
  const allTriaged = searchParams.get('all_triaged') === 'true';
  const limitParam = searchParams.get('limit');
  const offsetParam = searchParams.get('offset');

  const limit = limitParam ? parseInt(limitParam, 10) : undefined;
  const offset = offsetParam ? parseInt(offsetParam, 10) : undefined;

  try {
    // When all_triaged is true, fetch without status filter (returns all statuses)
    const filterStatus = allTriaged ? undefined : status;
    const data = await listCandidates(filterStatus, limit, offset);
    return NextResponse.json(data);
  } catch (error) {
    console.error('Candidates error:', error);
    return NextResponse.json(
      { error: 'Failed to fetch candidates' },
      { status: 500 }
    );
  }
}
