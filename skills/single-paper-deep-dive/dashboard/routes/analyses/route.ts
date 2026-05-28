import { NextResponse } from 'next/server';
import { listAnalyses } from '@/lib/single-paper-deep-dive';

export async function GET() {
  try {
    const data = await listAnalyses();
    return NextResponse.json(data);
  } catch (error) {
    console.error('dive analyses error:', error);
    return NextResponse.json({ error: String(error) }, { status: 500 });
  }
}
