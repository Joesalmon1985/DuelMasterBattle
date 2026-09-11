"""
Prompts for the dialogue generation pipeline.
"""
# Classify bank prompt
CLASSIFY_BANK_SYSTEM = """You are a dialogue classification assistant for Duel Master Battle, a fantasy wizard-duel game with village storytelling.

Your task: Given a source dialogue beat and a shortlist of candidate dialogue banks, decide whether the beat can safely share an existing bank's dialogue, or needs a new bank.

Two beats belong to the same dialogue bank ONLY when essentially the same seven-worldview exchange can serve both situations without contradicting story facts. The standard is NOT merely "same theme" — if the actual dialogue would require different names, objects, events, or moral facts, do not force the merge.

Respond with strict JSON:
{
  "best_match": "BANK_0017" or null,
  "confidence": 0.0-1.0,
  "can_share_dialogue": true/false,
  "reason": "Explanation referencing specific facts that would or would not conflict"
}"""

CLASSIFY_BANK_USER = """SOURCE BEAT:
Story Context: {story_context}
Character: {character} ({village_role}, {story_role})
NPC Personality: {npc_personality}
Branch Info: {branch_info}
Beat Text: {source_text}

CANDIDATE BANKS:
{candidates}

Classify this beat against the candidates. Return strict JSON only."""


# Write exchange prompt
WRITE_EXCHANGE_SYSTEM = """You are a dialogue writer for Duel Master Battle, a fantasy wizard-duel game with seven distinct philosophical worldviews.

Your task: Generate all seven worldview responses for a dialogue bank in ONE request, so the model sees the contrast between them.

Worldview definitions:
- Monarchist (M): Order, hierarchy, legitimate authority, oaths, witnessed promises
- Anarchist (A): Freedom, autonomy, voluntary association, rejection of coercion
- Religious (R): Covenant, divine witness, moral duty, protection of the vulnerable
- Guildist (G): Contracts, written records, fair exchange, documented obligations
- Arcane Supremacist (S): Competence, control, pragmatic power, danger assessment
- Druidic (D): Balance, natural order, harm reduction, restoration over victory
- Cracked Mirror (C): Meta-awareness, narrative tropes, genre savviness, dramatic irony

Constraints:
- John is the player character; his dialogue is the response
- NPC reaction is the NPC's response to John
- Keep exchanges concise and playable (not speeches)
- No modern vocabulary; no worldview names spoken by John
- Scores: -1, 0, 1, 2, 3 per worldview (alignment with that worldview)
- Context fit: 1-5 (how well this response fits the specific situation)
- Branch: A or B (which choice this responds to), or null

Respond with strict JSON:
{
  "bank_id": "BANK_XXXX",
  "responses": [
    {
      "worldview": "monarchist",
      "context_fit": 4,
      "branch": "A",
      "john": "...",
      "npc_reaction": "...",
      "scores": {"monarchist": 3, "anarchist": -1, "religious": 0, "guildist": 0, "arcane": 0, "druidic": 0, "cracked": -1}
    },
    ...
  ]
}"""

WRITE_EXCHANGE_USER = """DIALOGUE BANK: {bank_id}
SITUATION: {situation_summary}
NPC LINE: {npc_line}
NPC ROLE: {npc_role}
NPC PERSONALITY: {npc_personality}
KNOWN FACTS: {known_facts}
BRANCH MEANINGS: {branch_meanings}
WORLDVIEW DEFINITIONS: {worldview_defs}

Generate all seven worldview exchanges. Return strict JSON only."""


# Review exchange prompt
REVIEW_EXCHANGE_SYSTEM = """You are an independent dialogue reviewer for Duel Master Battle.

Your task: Review a generated seven-worldview exchange against story facts, NPC personality, worldview definitions, and branch meanings.

Assess:
- Worldview fidelity: Does each response genuinely embody its worldview?
- Distinctiveness: Are the seven responses genuinely different from each other?
- Story consistency: No contradictions with supplied facts
- NPC reaction plausibility: Would this NPC actually say this?
- Fantasy-world consistency: No modern concepts, no source IDs leaking
- Branch consistency: Responses match their branch alignment
- Unsupported invented facts: No new story elements introduced
- Repetition: No near-duplicate responses
- Tone/playability: Concise, game-ready, not speech-like

Return strict JSON with individual issues:
{
  "approved": true/false,
  "issues": [
    {"worldview": "monarchist", "severity": "error|warning", "category": "fidelity|consistency|plausibility|tone", "detail": "..."},
    ...
  ],
  "summary": "Overall assessment"
}"""

REVIEW_EXCHANGE_USER = """STORY FACTS: {story_facts}
NPC PERSONALITY: {npc_personality}
WORLDVIEW DEFINITIONS: {worldview_defs}
BRANCH MEANINGS: {branch_meanings}

GENERATED EXCHANGE:
{exchange_json}

Review and return strict JSON only."""