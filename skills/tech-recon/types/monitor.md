---
type: monitor
label: Monitor
short: MON
icon: clock
color: rust
---

# Monitor Investigation

## When to use

The user wants to track an evolving area over time — "keep me updated on X", "track developments in Y", "alert me when Z changes." This is an ongoing investigation with periodic check-ins, not a one-shot analysis. Each iteration is a temporal snapshot, and the value is in the deltas between snapshots.

## Interview adjustments

Replace the 8-question interview with monitoring setup:
1. What area are you tracking?
2. What signals matter? (new papers, releases, funding rounds, regulatory changes, benchmark results?)
3. What sources should be checked? (specific repos, conferences, companies, RSS feeds?)
4. How often should check-ins happen? (weekly, monthly, quarterly?)
5. What would be worth alerting on immediately vs. summarizing at check-in?
6. Is there a specific decision this monitoring supports, or is it general awareness?

After Q6, define the monitoring scope, signal list, and check-in cadence.

## Discovery phase

Initial discovery establishes the baseline — what's the current state of the area? This is similar to a lightweight landscape or survey. On subsequent iterations, discovery becomes: "what's new since last check-in?"

Sources to monitor:
- GitHub repos (new releases, major PRs, stars trajectory)
- arXiv/PubMed (new papers matching keywords)
- Company blogs and announcements
- Conference proceedings
- Social signals (HN, Twitter/X, Reddit threads)

Use `add-system` to represent monitored entities (repos, companies, projects). These persist across iterations.

## Sensemaking strategy

Each iteration produces a delta summary. Notes are timestamped and iteration-tagged:

### Expected note topics
- `delta-summary` — What changed since last check-in? Key developments.
- `new-entries` — New systems, papers, or tools that appeared
- `signal-alert` — Specific signals that crossed a threshold (e.g., "Mem0 released v2.0 with breaking API changes")
- `trend-observation` — Emerging patterns or trajectory shifts
- `monitoring-checklist` — Updated list of what to check next time

The first iteration's `delta-summary` is the baseline state. Subsequent iterations compare to the previous.

## Analysis phase

Visualizations should show change over time:
- Trend lines (stars, downloads, citations over time)
- Activity heatmaps (commits, papers by month)
- New entrant timeline (when did each system appear?)
- Signal log (alerts and observations, chronological)

## Output expectations

**Synthesis report** (per iteration) should contain:
1. Check-in date and period covered
2. Key developments since last check-in (bulleted)
3. Trend observations (what's accelerating, what's stalling)
4. Alerts triggered (if any)
5. Updated monitoring checklist for next check-in

The synthesis report is cumulative — each iteration adds to the history, it doesn't replace it.

**Completion assessment** is replaced by a **monitoring health check**: are the sources still relevant? Is the cadence right? Should the scope be narrowed or expanded?

## Completion criteria

Monitor investigations don't "complete" in the normal sense. They can be:
- **Active** — check-ins happening on schedule
- **Paused** — temporarily suspended (user is busy, area is quiet)
- **Archived** — area is no longer relevant or a decision has been made

Close the investigation when the user says the monitoring is no longer needed, or when it feeds into a different investigation type (e.g., a landscape survey triggered by monitoring signals).
