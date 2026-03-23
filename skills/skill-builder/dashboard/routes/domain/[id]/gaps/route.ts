import { NextResponse } from 'next/server';
import { getDomainGaps } from '@/lib/skill-builder';

export async function GET(
  _req: Request,
  { params }: { params: Promise<{ id: string }> }
) {
  try {
    const { id } = await params;
    const data = await getDomainGaps(id);
    return NextResponse.json(data);
  } catch (error) {
    console.error('skill-builder gaps error:', error);
    return NextResponse.json({ error: String(error) }, { status: 500 });
  }
}
