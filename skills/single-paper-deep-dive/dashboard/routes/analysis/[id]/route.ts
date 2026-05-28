import { NextRequest, NextResponse } from 'next/server';
import { getAnalysis } from '@/lib/single-paper-deep-dive';

export async function GET(
  request: NextRequest,
  { params }: { params: Promise<{ id: string }> }
) {
  const { id } = await params;
  const decoded = decodeURIComponent(id);
  try {
    const data = await getAnalysis(decoded);
    return NextResponse.json(data);
  } catch (error) {
    console.error('dive analysis error:', error);
    return NextResponse.json({ error: String(error) }, { status: 500 });
  }
}
