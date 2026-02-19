import { NextRequest, NextResponse } from 'next/server';
import { listArtifacts } from '@/lib/techrecon';

export async function GET(request: NextRequest) {
  const system = request.nextUrl.searchParams.get('system') || undefined;
  const type = request.nextUrl.searchParams.get('type') || undefined;

  try {
    const data = await listArtifacts(system, type);
    return NextResponse.json(data);
  } catch (error) {
    console.error('Artifacts error:', error);
    return NextResponse.json(
      { error: 'Failed to fetch artifacts' },
      { status: 500 }
    );
  }
}
