import { NextRequest, NextResponse } from 'next/server';
import { describeSchema } from '@/lib/agentic-memory';

export async function GET(request: NextRequest) {
  try {
    const { searchParams } = new URL(request.url);
    const skill = searchParams.get('skill') || undefined;
    const full = searchParams.get('full') === 'true';
    const data = await describeSchema(skill, full);
    return NextResponse.json(data);
  } catch (error) {
    console.error('describeSchema error:', error);
    return NextResponse.json({ error: String(error) }, { status: 500 });
  }
}
