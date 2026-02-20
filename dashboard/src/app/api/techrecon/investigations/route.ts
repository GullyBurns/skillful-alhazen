import { NextRequest, NextResponse } from 'next/server';
import { listInvestigations } from '@/lib/techrecon';

export async function GET(request: NextRequest) {
  const status = request.nextUrl.searchParams.get('status') || undefined;

  try {
    const data = await listInvestigations(status);
    return NextResponse.json(data);
  } catch (error) {
    console.error('Investigations error:', error);
    return NextResponse.json(
      { error: 'Failed to fetch investigations' },
      { status: 500 }
    );
  }
}
