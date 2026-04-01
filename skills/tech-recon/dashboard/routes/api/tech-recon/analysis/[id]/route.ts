import { NextResponse } from 'next/server';
import { getAnalysis } from '@/lib/tech-recon';

export async function GET(req: Request, { params }: { params: Promise<{ id: string }> }) {
  try {
    const { id } = await params;
    const data = await getAnalysis(id);
    return NextResponse.json(data);
  } catch (error) {
    console.error('getAnalysis error:', error);
    return NextResponse.json({ error: String(error) }, { status: 500 });
  }
}
