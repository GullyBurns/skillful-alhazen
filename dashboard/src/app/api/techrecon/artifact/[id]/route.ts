import { NextResponse } from 'next/server';
import { getArtifact } from '@/lib/techrecon';

export async function GET(
  _request: Request,
  { params }: { params: Promise<{ id: string }> }
) {
  const { id } = await params;

  try {
    const data = await getArtifact(id);
    return NextResponse.json(data);
  } catch (error) {
    console.error('Artifact error:', error);
    return NextResponse.json(
      { error: 'Failed to fetch artifact' },
      { status: 500 }
    );
  }
}
