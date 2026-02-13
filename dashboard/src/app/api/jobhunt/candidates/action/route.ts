import { NextRequest, NextResponse } from 'next/server';
import { triageCandidate, promoteCandidate } from '@/lib/jobhunt';

export async function POST(request: NextRequest) {
  try {
    const body = await request.json();
    const { candidateId, action } = body;

    if (!candidateId || !action) {
      return NextResponse.json(
        { error: 'candidateId and action are required' },
        { status: 400 }
      );
    }

    if (action !== 'promote' && action !== 'dismiss') {
      return NextResponse.json(
        { error: 'action must be "promote" or "dismiss"' },
        { status: 400 }
      );
    }

    let result;
    if (action === 'promote') {
      result = await promoteCandidate(candidateId);
    } else {
      result = await triageCandidate(candidateId, 'dismissed');
    }

    return NextResponse.json(result);
  } catch (error) {
    console.error('Candidate action error:', error);
    return NextResponse.json(
      { error: 'Failed to perform candidate action' },
      { status: 500 }
    );
  }
}
