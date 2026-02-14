---
name: goral-hagra
description: >
  Perform the Goral HaGra — randomly select a verse from the Torah or full Tanakh for guidance on a decision.
  Two modes: regular Goral HaGra (Torah only, 5 Books of Moses) and extended Goral HaGra (all of Tanakh).
  Uses Sefaria API for Hebrew text, English translation, and rabbinic commentary.
  Triggers on "goral hagra", "ask the gra", "ask the Vilna Gaon", "divine lot", "random verse guidance".
---

# Goral HaGra — Divine Lot of the Vilna Gaon

## 1. Trigger Detection

Activate this skill when the user says any of the following (case-insensitive):

- "goral hagra" / "גורל הגר״א" / "גורל הגרא"
- "ask the gra" / "ask the Vilna Gaon"
- "divine lot" / "cast the goral"
- "random verse for guidance"
- "what does the Torah say about..." (when combined with a decision context)

### Determine the Mode

- **Regular Goral HaGra** (default): Torah only (Genesis through Deuteronomy). Use this when the user says "Torah", "Chumash", "regular goral", or does not specify.
- **Extended Goral HaGra**: Full Tanakh (Torah + Nevi'im + Ketuvim). Use this when the user says "Tanakh", "extended goral", "full Tanakh", "all of Tanakh", "Nevi'im", or "Ketuvim".

If the user provides context about their decision or question, remember it — you will need it for the Reflection step.

## 2. Random Verse Selection

Run the PowerShell script to get a random verse:

```powershell
~/.claude/skills/goral-hagra/scripts/Get-GoralHaGra.ps1 -Action random-verse -Mode <torah|tanakh>
```

- Use `-Mode torah` for the regular Goral HaGra.
- Use `-Mode tanakh` for the extended Goral HaGra.

The script returns a verse reference (e.g., `Genesis 32:11` or `Psalms 27:4`). Capture this reference for subsequent steps.

## 3. First-Use Translation Setup

Check if `~/.claude/skills/goral-hagra/config.json` exists and contains a `preferredTranslation` field.

### If config does NOT exist or lacks `preferredTranslation` (first use):

1. Run the script to fetch available translations for this verse:
   ```powershell
   ~/.claude/skills/goral-hagra/scripts/Get-GoralHaGra.ps1 -Action get-translations -Reference "<the reference>"
   ```
2. Present the list of available English translations to the user and ask them to choose one.
3. Save their choice to `~/.claude/skills/goral-hagra/config.json`:
   ```json
   {
     "preferredTranslation": "The Koren Jerusalem Bible"
   }
   ```
4. Use this translation for the current and all future requests.

### If config exists and has `preferredTranslation`:

Read the value and use it. Do not ask the user again.

## 4. Fetch Verse Data from Sefaria

Run the script with the reference and preferred translation:

```powershell
~/.claude/skills/goral-hagra/scripts/Get-GoralHaGra.ps1 -Action get-verse-data -Reference "<ref>" -Translation "<preferred translation>"
```

This returns a clean JSON object with:
- `hebrew` — exact Hebrew text of the verse
- `english` — English translation
- `englishVersionTitle` — name of the translation used
- `commentary` — array of `{ commentator, text }` objects (HTML-stripped, max 6, deduplicated by commentator)

No further parsing is needed — use the fields directly.

## 5. Contextual Search (Optional Enhancement)

If the verse has clear thematic content (e.g., mentions a specific topic like trust, fear, justice, love), optionally run a related search to deepen your understanding:

```powershell
~/.claude/skills/goral-hagra/scripts/Get-GoralHaGra.ps1 -Action search-related -Query "<key phrase from the verse>" -Filters "Tanakh","Midrash","Talmud" -Size 3
```

Use the search results to enrich your contextual understanding and inform the Reflection step. Do **NOT** present raw search results to the user.

## 6. Clarification Step

**After collecting all the Sefaria data, do NOT immediately present the results.** Pause and consider:

- Review the verse, its context, and the commentary you received.
- If you feel that additional clarification from the user about their specific situation, question, or decision would help you provide a more relevant and meaningful interpretation, ask **1–2 targeted questions**. Keep them brief and focused.
- If the user already provided sufficient context about their decision or question when they triggered the skill, **skip this step entirely**.
- This is a spiritual moment — do not turn it into an interrogation. Be gentle and respectful.

## 7. Presentation Format

Present the result using this exact format:

---

**🎲 The Goral HaGra returned: [Reference in English] / [Reference in Hebrew]**

**📖 The Verse (Hebrew):**
> [Full Hebrew text of the verse — copied exactly from the API response]

**📖 The Verse (English — [Translation Name]):**
> [Full English text of the verse]

**📝 Context:**
[Brief explanation of where this verse falls in the narrative or textual context. What is the chapter about? What comes before and after this verse? 2–3 sentences maximum.]

**📚 From the Commentators:**
[Present 2–4 commentators, one bullet each. Format: **Name**: one-sentence distillation of their key insight on this verse. Do NOT elaborate per-commentator on how it relates to the user — save that for the Reflection. Keep the total commentator section to ~4–6 lines.]

**💡 Reflection:**
[Your synthesis connecting the verse and commentary to the user's specific situation or decision. This must be grounded entirely in the textual sources — not your own opinion. Frame it as "The verse and its commentators suggest..." rather than "I think..." or "In my opinion...". Be thoughtful, specific, and respectful.]

---

## 8. Important Guidelines

- **Ground everything in Sefaria data.** Do not invent, fabricate, or loosely paraphrase commentary. Only cite what the API actually returned.
- **Hebrew text must be exact.** Copy it directly from the API response. Do not transliterate, modify, or "fix" it.
- **If the API call fails**, inform the user that there was an error reaching Sefaria and suggest trying again. Do not attempt to generate verse text from memory.
- **Do not editorialize.** The Reflection section should synthesize the traditional sources. Do not add your own theological opinions, personal beliefs, or speculative interpretations.
- **Respect the practice.** The Goral HaGra is a meaningful Jewish tradition attributed to the Vilna Gaon. Present it with appropriate gravity, reverence, and respect.
- **One verse only.** The Goral HaGra returns exactly one verse. Do not suggest "trying again" or "getting another one" unless the user explicitly asks to do so.
- **Language sensitivity.** If the user communicates in Hebrew, present the non-verse portions of the response in Hebrew as well. Match the user's language.
