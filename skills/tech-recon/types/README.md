# Investigation Types

When starting a new investigation, classify it into one of these types after the first 2-3 interview questions. The type shapes how you conduct every subsequent phase.

| Type | Use when... | Unit of analysis |
|------|-------------|-----------------|
| **landscape** | "What exists that does X?" — mapping a space, comparing multiple candidates | System/product |
| **evaluation** | "Should we use X?" — deep assessment of one system against your requirements | Requirements gap |
| **question** | "How do people solve X?" — researching a specific technical question | Approach/solution |
| **survey** | "What's the state of field Y?" — building understanding of a domain | Paper/theme |
| **monitor** | "What's emerging in Z?" — tracking developments over time | Time period/delta |
| **brief** | "Explain T to audience A" — producing a document for a specific reader | Key points |

## How to use

1. After the user describes their goal, propose a type: *"This sounds like a **landscape** investigation. Does that fit?"*
2. Load the type prompt: `Read skills/tech-recon/types/<type>.md`
3. Follow the type prompt's guidance for interview adjustments, discovery, sensemaking, analysis, and outputs
4. Pass `--type <type>` when calling `start-investigation`

## When unsure

- If the user wants to compare things → **landscape**
- If the user already knows the tool and wants to assess fit → **evaluation**
- If the user has a "how do I...?" or "is there a way to...?" question → **question**
- If the user is writing a paper or building domain knowledge → **survey**
- If the user says "keep me updated on..." → **monitor**
- If the user needs to explain something to someone else → **brief**

Default to **landscape** if genuinely ambiguous — it's the most general.
