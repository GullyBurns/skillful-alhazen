import { NextRequest, NextResponse } from 'next/server';
import { listPipeline } from '@/lib/jobhunt';

export async function GET(request: NextRequest) {
  const searchParams = request.nextUrl.searchParams;
  const status = searchParams.get('status') || undefined;
  const priority = searchParams.get('priority') || undefined;
  const tag = searchParams.get('tag') || undefined;

  try {
    const data = await listPipeline({ status, priority, tag });
    return NextResponse.json(data);
  } catch (error) {
    console.error('Pipeline error:', error);
    return NextResponse.json(
      { error: 'Failed to fetch pipeline' },
      { status: 500 }
    );
  }
}
