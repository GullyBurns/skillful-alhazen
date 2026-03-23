import { NextResponse } from 'next/server';
import { getDomain } from '@/lib/skill-builder';

export async function GET(
  _req: Request,
  { params }: { params: Promise<{ id: string }> }
) {
  try {
    const { id } = await params;
    const data = await getDomain(id);
    return NextResponse.json(data);
  } catch (error) {
    console.error('skill-builder domain error:', error);
    return NextResponse.json({ error: String(error) }, { status: 500 });
  }
}
