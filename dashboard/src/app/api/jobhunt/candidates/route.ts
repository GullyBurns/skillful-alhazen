import { NextRequest, NextResponse } from 'next/server';
import { listCandidates } from '@/lib/jobhunt';

export async function GET(request: NextRequest) {
  const searchParams = request.nextUrl.searchParams;
  const status = searchParams.get('status') || undefined;

  try {
    const data = await listCandidates(status);
    return NextResponse.json(data);
  } catch (error) {
    console.error('Candidates error:', error);
    return NextResponse.json(
      { error: 'Failed to fetch candidates' },
      { status: 500 }
    );
  }
}
