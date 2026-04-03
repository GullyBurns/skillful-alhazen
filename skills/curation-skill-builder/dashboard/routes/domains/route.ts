import { NextResponse } from 'next/server';
import { listDomains } from '@/lib/skill-builder';

export async function GET() {
  try {
    const data = await listDomains();
    return NextResponse.json(data);
  } catch (error) {
    console.error('skill-builder domains error:', error);
    return NextResponse.json({ error: String(error) }, { status: 500 });
  }
}
