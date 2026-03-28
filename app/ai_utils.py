from .azure_openai_utils import azure_text


async def summarize_text(text: str, max_sections: int = 8) -> str:
    if not text or len(text.strip()) < 100:
        return "### Summary\n- No content to summarize."

    if len(text) > 28000:
        text = text[:28000]

    fallback_lines = [line.strip() for line in text.splitlines() if line.strip()][: max_sections * 3]
    fallback = []
    for idx in range(max_sections):
        start = idx * 3
        chunk = fallback_lines[start : start + 3]
        if not chunk:
            break
        fallback.append(f"### Concept {idx + 1}")
        for ln in chunk:
            fallback.append(f"- {ln[:180]}")
    fallback_text = "\n".join(fallback) if fallback else "### Summary\n- Summary unavailable."

    prompt = f"""Summarize this educational content into markdown for studying.
Use up to {max_sections} sections.
Format strictly like:
### <Concept title>
- bullet
- bullet

Make bullets specific (definitions, key mechanisms, examples, common mistakes).

Text:
{text}
"""
    return await azure_text(
        system="You create concise, pedagogy-first summaries.",
        prompt=prompt,
        fallback=fallback_text,
    )


async def detailed_summary_text(text: str) -> str:
    if not text or len(text.strip()) < 100:
        return "### Detailed Summary\n- No content to summarize."

    if len(text) > 32000:
        text = text[:32000]

    prompt = f"""Create a detailed, well-structured study note in markdown.

Requirements:
- Use clear section headings (###).
- Explain key ideas with definitions + mechanisms + examples.
- Include common misconceptions and a short "How to remember" tip where relevant.
- Keep it readable (Notion-style): short paragraphs and bullets.

Text:
{text}
"""
    fallback = await summarize_text(text, max_sections=10)
    return await azure_text(
        system="You write detailed, accurate study notes for learners.",
        prompt=prompt,
        fallback=fallback,
    )
