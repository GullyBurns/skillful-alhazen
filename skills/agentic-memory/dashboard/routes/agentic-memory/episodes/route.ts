import { NextRequest, NextResponse } from 'next/server';
import { listEpisodes } from '@/lib/agentic-memory';

export async function GET(request: NextRequest) {
  const skill = request.nextUrl.searchParams.get('skill') || undefined;
  const limit = parseInt(request.nextUrl.searchParams.get('limit') || '20', 10);
  try {
    const data = await listEpisodes(skill, limit);
    return NextResponse.json(data);
  } catch (error) {
    console.error('listEpisodes error:', error);
    return NextResponse.json({ error: String(error) }, { status: 500 });
  }
}
