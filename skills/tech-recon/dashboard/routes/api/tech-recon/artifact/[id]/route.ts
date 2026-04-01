import { NextResponse } from 'next/server';
import { getArtifact } from '@/lib/tech-recon';

export async function GET(req: Request, { params }: { params: Promise<{ id: string }> }) {
  try {
    const { id } = await params;
    const data = await getArtifact(id);
    return NextResponse.json(data);
  } catch (error) {
    console.error('getArtifact error:', error);
    return NextResponse.json({ error: String(error) }, { status: 500 });
  }
}
