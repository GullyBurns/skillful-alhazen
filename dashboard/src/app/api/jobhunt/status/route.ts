import { NextRequest, NextResponse } from 'next/server';
import { updateStatus } from '@/lib/jobhunt';

export async function POST(request: NextRequest) {
  try {
    const body = await request.json();
    const { positionId, status, date } = body;

    if (!positionId || !status) {
      return NextResponse.json(
        { error: 'positionId and status are required' },
        { status: 400 }
      );
    }

    const result = await updateStatus(positionId, status, date);
    return NextResponse.json(result);
  } catch (error) {
    console.error('Status update error:', error);
    return NextResponse.json(
      { error: 'Failed to update status' },
      { status: 500 }
    );
  }
}
