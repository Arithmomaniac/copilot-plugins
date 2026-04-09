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

- **Regular Goral HaGra**: Torah only (Genesis through Deuteronomy). Use this when the user says "Torah", "Chumash", or "regular goral".
- **Extended Goral HaGra**: Full Tanakh (Torah + Nevi'im + Ketuvim). Use this when the user says "Tanakh", "extended goral", "full Tanakh", "all of Tanakh", "Nevi'im", or "Ketuvim".
- **Default mode**: If the user does not specify a mode, read `defaultMode` from `~/.copilot/skills/goral-hagra/config.json`. The value is either `"torah"` or `"tanakh"`. If the config does not yet exist or lacks `defaultMode`, the user will be asked during first-use setup (see Step 3).

If the user provides context about their decision or question, remember it — you will need it for the Responsum step.

## 2. Random Verse Selection

Run the PowerShell script to get a random verse:

```powershell
~/.copilot/skills/goral-hagra/scripts/Get-GoralHaGra.ps1 -Action random-verse -Mode <torah|tanakh>
```

- Use `-Mode torah` for the regular Goral HaGra.
- Use `-Mode tanakh` for the extended Goral HaGra.

The script returns a verse reference (e.g., `Genesis 32:11` or `Psalms 27:4`). Capture this reference for subsequent steps.

## 3. First-Use Settings Setup

Check if `~/.copilot/skills/goral-hagra/config.json` exists and contains both `preferredTranslation` and `defaultMode`.

### If config does NOT exist or is missing either field (first use):

1. Run the script to fetch available translations for this verse:
   ```powershell
   ~/.copilot/skills/goral-hagra/scripts/Get-GoralHaGra.ps1 -Action get-translations -Reference "<the reference>"
   ```
2. Ask the user **two questions** (one at a time):
   - **Translation**: Present the list of available English translations and ask them to choose one.
   - **Default mode**: Ask whether they prefer **Torah only** (regular Goral HaGra) or **Full Tanakh** (extended Goral HaGra) as their default when they don't specify a mode.
3. Save both choices to `~/.copilot/skills/goral-hagra/config.json`:
   ```json
   {
     "preferredTranslation": "The Koren Jerusalem Bible",
     "defaultMode": "torah"
   }
   ```
4. Use these settings for the current and all future requests.

### If config exists and has both fields:

Read the values and use them. Do not ask the user again.

## 4. Fetch Verse Data from Sefaria

Run the script with the reference and preferred translation:

```powershell
~/.copilot/skills/goral-hagra/scripts/Get-GoralHaGra.ps1 -Action get-verse-data -Reference "<ref>" -Translation "<preferred translation>"
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
~/.copilot/skills/goral-hagra/scripts/Get-GoralHaGra.ps1 -Action search-related -Query "<key phrase from the verse>" -Filters "Tanakh","Midrash","Talmud" -Size 3
```

Use the search results to enrich your contextual understanding and inform the Responsum step. Do **NOT** present raw search results to the user.

## 6. Clarification Step

**After collecting all the Sefaria data, do NOT immediately present the results.** Pause and consider:

- Review the verse, its context, and the commentary you received.
- If you feel that additional clarification from the user about their specific situation, question, or decision would help you provide a more relevant and meaningful interpretation, ask **1–2 targeted questions**. Keep them brief and focused.
- If the user already provided sufficient context about their decision or question when they triggered the skill, **skip this step entirely**.
- This is a spiritual moment — do not turn it into an interrogation. Be gentle and respectful.

## 7. Presentation Format

Present the result in the style of a **rabbinical responsum (teshuvah)**. The tone should be warm but authoritative, as if a learned rabbi is carefully considering the question and drawing wisdom from the sources. Use formal yet accessible language. Address the questioner's situation directly, weaving the verse and commentary into a cohesive, deliberative answer — not a bulleted report.

Use this structure:

---

**🎲 The Goral HaGra has spoken: [Reference in English] / [Reference in Hebrew]**

**📖 The Verse:**

> [Full Hebrew text of the verse — copied exactly from the API response]

> [Full English text — [Translation Name]]

**📝 On the Matter at Hand (B'inyan HaNidon):**

[Open with a brief framing of the question or decision the user is facing, then introduce the verse and its place in the broader narrative. Where does it sit in the chapter? What is happening in the surrounding text? Transition naturally into the commentators' insights — do not list them as bullet points. Instead, weave them into flowing prose: "Rashi teaches us that..., and the Ramban adds a deeper layer, noting that..., while the Sforno draws our attention to...". Present the commentators as voices in a conversation, building upon one another.]

**💡 Responsum (Maskana):**

[This is the heart of the teshuvah. Synthesize the verse, its context, and the commentary into a direct, grounded response to the user's situation. Write as though rendering a considered opinion based on the sources: "In light of what the verse teaches and the commentators reveal, it would seem that..." or "The weight of the sources suggests...". Be specific to the user's situation. Do not hedge excessively or speak in vague generalities. Ground every claim in the textual sources — never in your own opinion. Close with a brief, encouraging or contemplative final sentence that honors the gravity of seeking guidance through this tradition.]

---

## 8. Important Guidelines

- **Ground everything in Sefaria data.** Do not invent, fabricate, or loosely paraphrase commentary. Only cite what the API actually returned.
- ⛔ **DO NOT generate Hebrew text, translations, or rabbinic commentary from memory/training data.** ✅ **ALWAYS fetch verse data from the Sefaria API via web_fetch.** The skill's accuracy depends on live API data.
- **Hebrew text must be exact.** Copy it directly from the API response. Do not transliterate, modify, or "fix" it.
- **If the API call fails**, inform the user that there was an error reaching Sefaria and suggest trying again. Do not attempt to generate verse text from memory.
- **Do not editorialize.** The Responsum section should synthesize the traditional sources in the style of a rabbinical teshuvah. Do not add your own theological opinions, personal beliefs, or speculative interpretations. Speak through the sources.
- **Respect the practice.** The Goral HaGra is a meaningful Jewish tradition attributed to the Vilna Gaon. Present it with appropriate gravity, reverence, and respect.
- **One verse only.** The Goral HaGra returns exactly one verse. Do not suggest "trying again" or "getting another one" unless the user explicitly asks to do so.
- **Language sensitivity.** If the user communicates in Hebrew, present the non-verse portions of the response in Hebrew as well. Match the user's language.
