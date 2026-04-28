import { NextRequest, NextResponse } from 'next/server';
import { listPersons } from '@/lib/agentic-memory';

export async function GET(_request: NextRequest) {
  try {
    const data = await listPersons();
    return NextResponse.json(data);
  } catch (error) {
    console.error('listPersons error:', error);
    return NextResponse.json({ error: String(error) }, { status: 500 });
  }
}
