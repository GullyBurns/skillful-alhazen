// Mock data layer — shape-identical to the real CLI JSON output.
//
// Two endpoints, byte-compatible with `python jobhunt.py show-opportunity --json`
// and `python jobhunt.py list-attention --json` from the alhazen-jobhunt repo:
//
//   showOpportunity(id)  →  { type, opportunity, company, notes[], contacts[], tags[], background_reading[] }
//   listAttention()      →  [{ id, name, type, status, priority, deadline, company,
//                              latest_cc_brief, pending_feedback_count, days_since_last_touch }, …]
//
// Note `type` strings are the FULL TypeQL entity names (e.g. 'jobhunt-cc-brief-note',
// 'jobhunt-application-note') so the dashboard can dispatch on them directly.
//
// Three opportunities — one of each active kind — exercise the kind discriminator
// without inventing schema. Lead/lead-shape isn't dossier-worthy yet; deferred.

const TODAY = new Date('2026-04-30T12:00:00Z');
const daysAgo   = (n, h = 12) => { const d = new Date(TODAY); d.setUTCDate(d.getUTCDate() - n); d.setUTCHours(h, 0, 0, 0); return d.toISOString(); };
const daysAhead = (n, h = 12) => { const d = new Date(TODAY); d.setUTCDate(d.getUTCDate() + n); d.setUTCHours(h, 0, 0, 0); return d.toISOString(); };

// ─── Opportunity 1: Position — Staff MLE @ Augura ───────────────
const AUGURA = {
  type: 'jobhunt-position',
  opportunity: {
    id: 'pos-augura-staff-mle',
    name: 'Staff ML Engineer, Biomedical AI',
    description: 'Production ML platform for foundation-model diagnostics. SF hybrid, 3d/wk SOMA. Owns training infra + inference for Augura Read.',
    status: 'phone-screen',
    priority: 'high',
    deadline: daysAhead(6),
    // position-specific extras (per cmd_show_position):
    application_status: 'phone-screen',
    applied_date: daysAgo(11),
    salary_range: '$240k–$310k + equity',
    location: 'San Francisco · hybrid',
  },
  company: { id: 'co-augura', name: 'Augura Health' },
  // Notes — the timeline. Sorted newest-first by created-at.
  notes: [
    { id: 'n-augura-cb3', type: 'jobhunt-cc-brief-note', name: 'Brief · phone screen prep window',
      content: 'You are 6 days out from the Allen Kim phone screen and the recruiter ping is 2 days stale. Two things move the needle this week: (1) reply to Priya tonight to lock logistics, (2) draft prep notes for Allen by Friday — focus on inference latency trade-offs since he owns that platform. The FSDP gap is real but not blocking for a phone screen; defer to onsite prep. Mission alignment is your strongest card here — lead with the Stanford Med work, not the caching project.',
      created_at: daysAgo(0, 9) },
    { id: 'n-augura-i1', type: 'jobhunt-interaction-note', name: 'Recruiter scheduled phone screen',
      content: 'Priya emailed: phone screen booked May 6, 2pm PT, with Allen Kim (Staff MLE, owns inference platform).',
      contact_name: 'Priya Shah', interaction_date: daysAgo(2),
      created_at: daysAgo(2, 16) },
    { id: 'n-augura-f1', type: 'jobhunt-cc-feedback-note', name: 'Feedback · Devon thank-you',
      content: 'Drafted a thank-you to Devon Aoki for the referral coffee. Keep it short — one line on Augura progress, one ask about whether anyone on the team has FSDP war stories. Don\'t make it transactional.',
      created_at: daysAgo(2, 18) },
    { id: 'n-augura-i2', type: 'jobhunt-interaction-note', name: 'LinkedIn DM to Bo Wang',
      content: 'Sent a short note to Bo on his foundation-model-for-radiology post. Asked one substantive question about evaluation loops in clinical settings. No reply yet.',
      contact_name: 'Bo Wang', interaction_date: daysAgo(4),
      created_at: daysAgo(4, 11) },
    { id: 'n-augura-cb2', type: 'jobhunt-cc-brief-note', name: 'Brief · post-application',
      content: 'Application went in via Devon\'s referral. Recruiter response within 3 days suggests the referral pulled weight. Now you wait — but not passively. Use this window to deepen the FSDP story; that\'s the one required skill where you read as "some" rather than "strong".',
      created_at: daysAgo(8, 10) },
    { id: 'n-augura-a1', type: 'jobhunt-application-note', name: 'Application submitted',
      content: 'Submitted via Greenhouse referral link. Resume v6, cover letter v2.',
      application_status: 'applied', applied_date: daysAgo(11),
      created_at: daysAgo(11, 14) },
    { id: 'n-augura-i3', type: 'jobhunt-interaction-note', name: 'Coffee with Devon Aoki',
      content: 'Devon (Staff Eng @ Augura) confirms team is shipping fast and that the gap they feel is distributed training depth. Said he\'d refer.',
      contact_name: 'Devon Aoki', interaction_date: daysAgo(14),
      created_at: daysAgo(14, 18) },
    { id: 'n-augura-fa1', type: 'jobhunt-fit-analysis-note', name: 'Fit analysis · v1',
      content: 'Mission alignment is unusually clean. Skills mostly green; distributed training is the one yellow. Comp band is at-or-above current. Logistics: 3d/wk SOMA is workable but tight.',
      fit_score: 0.82, axes: { skills: 0.78, mission: 0.94, leadership: 0.81, stage: 0.72, comp: 0.85, logistics: 0.65 },
      created_at: daysAgo(20, 11) },
    { id: 'n-augura-r1', type: 'jobhunt-research-note', name: 'Company background',
      content: 'Augura raised $112M Series C from a16z + GV in late 2025. Recent ship: Augura Read v2 (chest CT triage). CEO Lila Patel is ex-Verily; SVP Biomedical AI Bo Wang is the likely HM and active on LinkedIn re: foundation models for medical imaging.',
      created_at: daysAgo(22, 10) },
    { id: 'n-augura-s1', type: 'jobhunt-strategy-note', name: 'Talking points',
      content: 'Lead with Stanford Med (HIPAA, real PHI). Frame caching project as distributed-systems proxy. De-emphasize Rust learning, emphasize PyTorch production wins. Don\'t volunteer the FSDP gap — answer it honestly if asked.',
      created_at: daysAgo(22, 16) },
  ],
  contacts: [
    { id: 'c-bo',    name: 'Bo Wang',       contact_role: 'hiring-manager', contact_email: 'bo@augura.health' },
    { id: 'c-priya', name: 'Priya Shah',    contact_role: 'recruiter',      contact_email: 'priya@augura.health' },
    { id: 'c-devon', name: 'Devon Aoki',    contact_role: 'referral',       contact_email: null },
    { id: 'c-allen', name: 'Allen Kim',     contact_role: 'interviewer',    contact_email: null },
    { id: 'c-marta', name: 'Marta Vasquez', contact_role: 'jsc-member',     contact_email: null },
  ],
  // Position-specific: requirements with skill-level + your-level
  requirements: [
    { id: 'rq-1', skill: 'Python',                level: 'required',    your_level: 'strong' },
    { id: 'rq-2', skill: 'PyTorch',               level: 'required',    your_level: 'strong' },
    { id: 'rq-3', skill: 'Distributed training',  level: 'required',    your_level: 'some' },
    { id: 'rq-4', skill: 'Healthcare data (PHI)', level: 'preferred',   your_level: 'some' },
    { id: 'rq-5', skill: 'Kubernetes',            level: 'preferred',   your_level: 'strong' },
    { id: 'rq-6', skill: 'Causal inference',      level: 'nice-to-have', your_level: 'learning' },
  ],
  tags: ['ai', 'ml-platform', 'healthcare', 'mission-aligned'],
  background_reading: [
    { collection_id: 'col-fm-rad', collection_name: 'Foundation models for radiology', description: '12 papers · last updated 3d ago' },
    { collection_id: 'col-fsdp',   collection_name: 'FSDP & distributed training',     description: '7 papers · 2 unread' },
  ],
};

// ─── Opportunity 2: Engagement — consulting w/ Reseda Bio ───────
const RESEDA = {
  type: 'jobhunt-engagement',
  opportunity: {
    id: 'eng-reseda-q2',
    name: 'ML platform audit — Reseda Bio',
    description: '6-week paid engagement. Audit their training infra, deliver a roadmap, optionally run a workshop. Roadmap due end of Q2.',
    status: 'scoping',
    priority: 'medium',
    deadline: daysAhead(11),
    // engagement extras
    engagement_type: 'consulting',
    rate: '$285/hr · est. 60 hrs',
    start_date: daysAhead(14),
  },
  company: { id: 'co-reseda', name: 'Reseda Bio' },
  notes: [
    { id: 'n-reseda-cb1', type: 'jobhunt-cc-brief-note', name: 'Brief · scope or walk',
      content: 'You are at the scope-or-walk fork. The conversation has been pleasant for two weeks but there is no signed SOW and no deliverable definition. Two outcomes are bad here: (a) you sign vague and bleed weekend hours on scope creep, (b) you defer too long and they hire someone else. Send the scoping memo this week. Either they push back with specifics — useful — or they sign — also useful.',
      created_at: daysAgo(1, 14) },
    { id: 'n-reseda-i1', type: 'jobhunt-interaction-note', name: 'Call with Aanya — scope discussion',
      content: 'Aanya wants the audit to cover "training, eval, AND deployment" but the budget caps at 60 hrs. Need to push back on scope or push up on rate. She mentioned a workshop format would be valued by their team.',
      contact_name: 'Aanya Mehta', interaction_date: daysAgo(3),
      created_at: daysAgo(3, 16) },
    { id: 'n-reseda-s1', type: 'jobhunt-strategy-note', name: 'Engagement framing',
      content: 'Frame this as a roadmap engagement, not a code engagement. Deliverable is a written audit + 90-min workshop. If they want code, that\'s a separate SOW.',
      created_at: daysAgo(7, 11) },
    { id: 'n-reseda-cb0', type: 'jobhunt-cc-brief-note', name: 'Brief · entry',
      content: 'Inbound from Aanya at Reseda — they read your distributed-training writeup. Strong signal. Engagements like this fund the gap year and seed the venture network. Do not reflexively deprioritize for the Augura process; the two are not competing.',
      created_at: daysAgo(13, 9) },
    { id: 'n-reseda-r1', type: 'jobhunt-research-note', name: 'Reseda — what they ship',
      content: 'Reseda is a 35-person bio platform out of Cambridge. They train protein-language models in-house. Last raised $40M Series B in early 2025.',
      created_at: daysAgo(13, 15) },
  ],
  contacts: [
    { id: 'c-aanya', name: 'Aanya Mehta', contact_role: 'principal',  contact_email: 'aanya@reseda.bio' },
    { id: 'c-jonas', name: 'Jonas Lindqvist', contact_role: 'technical-lead', contact_email: 'jonas@reseda.bio' },
  ],
  tags: ['consulting', 'paid', 'biotech', 'short-term'],
  background_reading: [
    { collection_id: 'col-plm', collection_name: 'Protein language models', description: '4 papers' },
  ],
};

// ─── Opportunity 3: Venture — drafting an idea ──────────────────
const PROJECT_KILN = {
  type: 'jobhunt-venture',
  opportunity: {
    id: 'ven-kiln',
    name: 'Project Kiln — eval tooling for clinical ML',
    description: 'Open-source eval harness for clinical-deployment ML. Hypothesis: every healthcare ML team rebuilds this badly; a good shared tool wins on community + trust.',
    status: 'exploring',
    priority: 'medium',
    deadline: daysAhead(28),
    // venture extras
    venture_type: 'open-source',
    stage: 'pre-seed exploration',
  },
  company: { id: 'co-self', name: '— self-driven —' },
  notes: [
    { id: 'n-kiln-cb1', type: 'jobhunt-cc-brief-note', name: 'Brief · narrow before you build',
      content: 'You are in the dangerous middle: enthusiastic enough to start coding, not committed enough to have validated. Spend the next two weeks on three diligence calls — Augura\'s Bo, Reseda\'s Jonas, one Stanford Med contact. If two of three say "yes, we\'d use this," start. If not, it goes in the parking lot. No partial commitment.',
      created_at: daysAgo(0, 16) },
    { id: 'n-kiln-f1', type: 'jobhunt-cc-feedback-note', name: 'Feedback · stop scope-creeping',
      content: 'I keep widening this from "eval harness" to "eval + deployment + monitoring". Pull me back to eval. The whole point is winning on a narrow, sharp tool.',
      created_at: daysAgo(1, 20) },
    { id: 'n-kiln-s1', type: 'jobhunt-strategy-note', name: 'Wedge & GTM',
      content: 'Wedge: clinical-ML teams currently use ad-hoc Jupyter notebooks for eval. GTM: open-source first, build credibility at FDA/regulatory venues, then layer paid managed-cloud version.',
      created_at: daysAgo(4, 13) },
    { id: 'n-kiln-r1', type: 'jobhunt-research-note', name: 'Adjacent tools',
      content: 'Closest analogues: Weights & Biases (general, not clinical), MLflow (general), Truera (was clinical-adjacent, acquired). Nothing clinical-native open-source.',
      created_at: daysAgo(9, 11) },
  ],
  contacts: [
    { id: 'c-marta-2', name: 'Marta Vasquez', contact_role: 'jsc-member', contact_email: null },
  ],
  tags: ['venture', 'open-source', 'clinical-ml', 'exploring'],
  background_reading: [],
};

const ALL_OPPORTUNITIES = { [AUGURA.opportunity.id]: AUGURA, [RESEDA.opportunity.id]: RESEDA, [PROJECT_KILN.opportunity.id]: PROJECT_KILN };

// ─── list-attention output ──────────────────────────────────────
// Per the CLI: pre-sorted by priority then staleness, with brief/feedback metrics.
// Includes a couple of opportunities NOT in ALL_OPPORTUNITIES — they exist in the
// graph but aren't surfaced here as full dossiers; the inbox shows everything.
const ATTENTION = [
  { id: 'pos-augura-staff-mle', name: 'Staff ML Engineer, Biomedical AI', type: 'jobhunt-position',
    status: 'phone-screen', priority: 'high', deadline: daysAhead(6),
    company: { id: 'co-augura', name: 'Augura Health' },
    latest_cc_brief: daysAgo(0, 9), pending_feedback_count: 0, days_since_last_touch: 0 },

  { id: 'pos-celastra', name: 'Principal Researcher — Clinical Foundations', type: 'jobhunt-position',
    status: 'applied', priority: 'high', deadline: daysAhead(14),
    company: { id: 'co-cel', name: 'Celastra' },
    latest_cc_brief: daysAgo(5, 10), pending_feedback_count: 2, days_since_last_touch: 5 },

  { id: 'eng-reseda-q2', name: 'ML platform audit — Reseda Bio', type: 'jobhunt-engagement',
    status: 'scoping', priority: 'medium', deadline: daysAhead(11),
    company: { id: 'co-reseda', name: 'Reseda Bio' },
    latest_cc_brief: daysAgo(1, 14), pending_feedback_count: 0, days_since_last_touch: 1 },

  { id: 'pos-northstar', name: 'ML Lead — Imaging', type: 'jobhunt-position',
    status: 'researching', priority: 'medium', deadline: null,
    company: { id: 'co-ns', name: 'Northstar Health' },
    latest_cc_brief: null, pending_feedback_count: 0, days_since_last_touch: 9 },

  { id: 'ven-kiln', name: 'Project Kiln — eval tooling for clinical ML', type: 'jobhunt-venture',
    status: 'exploring', priority: 'medium', deadline: daysAhead(28),
    company: { id: 'co-self', name: '— self-driven —' },
    latest_cc_brief: daysAgo(0, 16), pending_feedback_count: 1, days_since_last_touch: 0 },

  { id: 'pos-helio', name: 'Senior MLE — Cardiology imaging', type: 'jobhunt-position',
    status: 'researching', priority: 'low', deadline: null,
    company: { id: 'co-helio', name: 'Helio Cardio' },
    latest_cc_brief: daysAgo(11, 9), pending_feedback_count: 3, days_since_last_touch: 11 },

  { id: 'lead-stanford-med', name: 'Stanford Med — informal lead', type: 'jobhunt-lead',
    status: 'researching', priority: 'low', deadline: null,
    company: { id: 'co-stan', name: 'Stanford Medicine' },
    latest_cc_brief: null, pending_feedback_count: 0, days_since_last_touch: 21 },
];

// ─── API ────────────────────────────────────────────────────────
window.api = {
  showOpportunity: (id) => ALL_OPPORTUNITIES[id],
  listAttention: () => ATTENTION,
};

window.OPP_IDS = { position: 'pos-augura-staff-mle', engagement: 'eng-reseda-q2', venture: 'ven-kiln' };
window.daysAgo = daysAgo;
window.daysAhead = daysAhead;
window.TODAY = TODAY;
