import { NextRequest, NextResponse } from 'next/server';
import { listInvestigations } from '@/lib/tech-recon';

export async function GET(request: NextRequest) {
  const searchParams = request.nextUrl.searchParams;
  const status = searchParams.get('status') || undefined;

  try {
    const data = await listInvestigations(status);
    return NextResponse.json(data);
  } catch (error) {
    console.error('listInvestigations error:', error);
    return NextResponse.json({ error: String(error) }, { status: 500 });
  }
}
