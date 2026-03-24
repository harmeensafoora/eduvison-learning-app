import base64
import json
import os
import re
from typing import List, Dict

from openai import AzureOpenAI, APIConnectionError
from .config import (
    AZURE_OPENAI_API_KEY,
    AZURE_OPENAI_ENDPOINT,
    AZURE_OPENAI_API_VERSION,
    AZURE_OPENAI_DEPLOYMENT,
)

def _ai_configured() -> bool:
    return bool(
        AZURE_OPENAI_API_KEY
        and AZURE_OPENAI_ENDPOINT
        and AZURE_OPENAI_DEPLOYMENT
    )


def _get_client() -> AzureOpenAI | None:
    if not _ai_configured():
        return None
    return AzureOpenAI(
        api_key=AZURE_OPENAI_API_KEY,
        api_version=AZURE_OPENAI_API_VERSION,
        azure_endpoint=AZURE_OPENAI_ENDPOINT,
    )


def _clean_text(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "")).strip()


def _split_sentences(text: str) -> List[str]:
    cleaned = _clean_text(text)
    if not cleaned:
        return []
    return [segment.strip() for segment in re.split(r"(?<=[.!?])\s+", cleaned) if segment.strip()]


def _fallback_topic_title(block: str, index: int) -> str:
    words = re.findall(r"[A-Za-z][A-Za-z0-9\-]*", block)
    if not words:
        return f"Topic {index + 1}"
    title_words = words[: min(4, len(words))]
    return " ".join(word.capitalize() for word in title_words)


def _fallback_summary(text: str) -> str:
    paragraphs = [part.strip() for part in re.split(r"\n\s*\n+", text or "") if part.strip()]
    blocks = paragraphs[:4] if paragraphs else [text]
    sections = []

    for index, block in enumerate(blocks):
        sentences = _split_sentences(block)[:3]
        if not sentences:
            continue
        title = _fallback_topic_title(block, index)
        section = [f"### {title}"]
        section.extend(f"- {sentence}" for sentence in sentences)
        sections.append("\n".join(section))

    if sections:
        return "\n\n".join(sections)

    return (
        "### Document Overview\n"
        "- The document was processed, but no structured summary could be generated from the extracted text.\n"
        "- Try a cleaner PDF or generate details after re-uploading if the source file is image-heavy."
    )


def _fallback_detailed_text(summary: str, full_text: str) -> str:
    sections = []
    current_title = None
    current_bullets: List[str] = []

    for raw_line in summary.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        if line.startswith("### "):
            if current_title:
                sections.append((current_title, current_bullets[:]))
            current_title = line[4:].strip()
            current_bullets = []
        elif line.startswith(("- ", "* ")):
            current_bullets.append(line[2:].strip())

    if current_title:
        sections.append((current_title, current_bullets[:]))

    if not sections:
        return _fallback_summary(full_text)

    rendered = []
    for title, bullets in sections[:6]:
        body = [
            f"### {title}",
            "**What to focus on**",
            f"- {bullets[0] if bullets else f'Review the main ideas connected to {title}.'}",
        ]
        if len(bullets) > 1:
            body.append("**Key points**")
            body.extend(f"- {bullet}" for bullet in bullets[1:4])
        rendered.append("\n".join(body))

    return "\n\n".join(rendered)


def _fallback_references(summary: str) -> Dict:
    topics = []
    for raw_line in summary.splitlines():
        line = raw_line.strip()
        if line.startswith("### "):
            topics.append(line[4:].strip())

    anchor = topics[0] if topics else "this topic"
    follow_up = topics[1:4]

    return {
        "before_topics": [
            {"title": "Key terminology", "why": f"Build the vocabulary needed to understand {anchor}."},
            {"title": "Foundational definitions", "why": "Clarify the core ideas before moving into mechanisms and detail."},
        ],
        "after_topics": (
            [{"title": topic, "why": "This appears adjacent to the current material and is a natural next step."} for topic in follow_up]
            or [{"title": "Applied problem solving", "why": "Use practice questions or worked examples to deepen retention."}]
        ),
        "references_by_level": {
            "beginner": [
                {"title": "Class notes or introductory chapter", "type": "course", "reason": "Best for a quick first pass in plain language."}
            ],
            "intermediate": [
                {"title": "Standard textbook chapter review", "type": "book", "reason": "Useful for connecting definitions with mechanisms and examples."}
            ],
            "expert": [
                {"title": "Subject-specific review articles", "type": "article", "reason": "Helpful once the fundamentals are already stable."}
            ],
        },
    }

# -------------------------------------------------------------------
# 1) Summarize PDF text
# -------------------------------------------------------------------
def summarize_text(text: str) -> str:
    # Truncate very long text just to be safe with context limits
    if len(text) > 12000:
        text = text[:12000]

    prompt = (
    "You are an educational content summarization system.\n\n"

    "Your task is to analyze the text and identify ALL major topics discussed in it.\n\n"

    "CRITICAL RULES:\n"
    "- Detect separate topics or concepts in the text.\n"
    "- Create a separate summary section for EACH topic.\n"
    "- NEVER merge unrelated topics into one heading.\n"
    "- NEVER create combined titles like 'Sensory and Digestive Systems'.\n"
    "- If the text discusses Eye and Mouth separately, create TWO sections.\n"
    "- Each section must describe only that specific topic.\n\n"

    "OUTPUT FORMAT (Markdown):\n"
    "For EACH topic use the following structure:\n\n"
    "### <Topic Name>\n\n"
    "Create 3–5 sections depending on what the content actually includes.\n"
    "Section names must come from the material itself.\n\n"

    "Example section types (use only if relevant):\n"
    "- Overview\n"
    "- Structure\n"
    "- Components\n"
    "- Mechanism\n"
    "- Characteristics\n"
    "- Types\n"
    "- Examples\n"
    "- Importance\n\n"

    "IMPORTANT STRUCTURE RULES:\n"
    "- Do NOT force sections like 'Functions' or 'Advantages'.\n"
    "- Only create sections supported by the text.\n"
    "- Use bullet points under each section.\n"
    "- Do NOT mention other topics inside a section.\n\n"

    "TEXT:\n"
    f"{text}"
)

    client = _get_client()
    if client is None:
        return _fallback_summary(text)

    try:
        resp = client.chat.completions.create(
            model=AZURE_OPENAI_DEPLOYMENT,
            messages=[{"role": "user", "content": prompt}],
        )
        return resp.choices[0].message.content.strip()
    except APIConnectionError as e:
        print("Azure OpenAI connection error in summarize_text:", e)
        return _fallback_summary(text)
    except Exception as e:
        print("Unexpected error in summarize_text:", e)
        return _fallback_summary(text)


# -------------------------------------------------------------------
# 2) Translate summary to another language
# -------------------------------------------------------------------
def translate_summary(summary: str, language: str) -> str:
    client = _get_client()
    if client is None:
        if language.lower() == "english":
            return summary
        return f"_Translation unavailable. Showing the original English summary instead._\n\n{summary}"

    prompt = (
        f"You are an academic translator specializing in scholarly content. Translate the following "
        f"educational summary into {language} while maintaining the highest standards of academic "
        f"accuracy and intellectual rigor.\n\n"
        f"Translation Guidelines:\n"
        f"- Preserve all discipline-specific terminology using internationally recognized terms in {language}\n"
        f"- Maintain the professional academic tone and educational structure\n"
        f"- Ensure conceptual descriptions remain intellectually precise and theoretically sound\n"
        f"- Use formal academic register appropriate for university-level instruction\n"
        f"- Keep all theoretical frameworks and practical applications accurate\n"
        f"- Retain the original formatting and sectional organization\n\n"
        f"Educational summary to translate:\n\n"
        f"{summary}"
    )
    try:
        resp = client.chat.completions.create(
            model=AZURE_OPENAI_DEPLOYMENT,
            temperature=0.2,
            messages=[{"role": "user", "content": prompt}],
        )
        return resp.choices[0].message.content.strip()
    except APIConnectionError as e:
        print("Azure OpenAI connection error in translate_summary:", e)
        return f"_Translation unavailable. Showing the original English summary instead._\n\n{summary}"
    except Exception as e:
        print("Unexpected error in translate_summary:", e)
        return f"_Translation failed. Showing the original English summary instead._\n\n{summary}"


# -------------------------------------------------------------------
# 3) Extra detailed explanation
# -------------------------------------------------------------------
def generate_detailed_text(summary: str, full_text: str) -> str:
    if len(full_text) > 12000:
        full_text = full_text[:12000]

    prompt = (
    "You are generating detailed educational explanations from the provided summary and text.\n\n"

    "TASK:\n"
    "Expand the material while keeping each topic completely separate.\n\n"

    "STRICT RULES:\n"
    "- Identify each topic from the summary.\n"
    "- Write a detailed explanation for EACH topic separately.\n"
    "- Do NOT merge or connect unrelated topics.\n"
    "- Do NOT create interdisciplinary explanations unless the text explicitly describes them.\n\n"

    "OUTPUT STRUCTURE:\n"
    "For EACH topic use:\n\n"
    "### <Topic Name>\n\n"
    "Create 5–8 sections depending on the content.\n"
    "Use **bold headings** for sections.\n\n"

    "Possible section types (use only if relevant):\n"
    "- Background\n"
    "- Structure\n"
    "- Components\n"
    "- Mechanism\n"
    "- Characteristics\n"
    "- Types\n"
    "- Examples\n"
    "- Significance\n\n"

    "IMPORTANT:\n"
    "- Only include sections supported by the text.\n"
    "- Do NOT force sections.\n"
    "- Do NOT connect separate topics together.\n"
    "- Each topic explanation should stand alone.\n\n"

    f"SUMMARY:\n{summary}\n\n"
    f"FULL TEXT:\n{full_text}"
)
    client = _get_client()
    if client is None:
        return _fallback_detailed_text(summary, full_text)

    try:
        resp = client.chat.completions.create(
            model=AZURE_OPENAI_DEPLOYMENT,
            temperature=0.2,
            messages=[{"role": "user", "content": prompt}],
        )
        return resp.choices[0].message.content.strip()
    except APIConnectionError as e:
        print("Azure OpenAI connection error in generate_detailed_text:", e)
        return _fallback_detailed_text(summary, full_text)
    except Exception as e:
        print("Unexpected error in generate_detailed_text:", e)
        return _fallback_detailed_text(summary, full_text)


# -------------------------------------------------------------------
# 4) Suggest prerequisite topics
# -------------------------------------------------------------------
def generate_references(summary: str) -> Dict:
    client = _get_client()
    if client is None:
        return _fallback_references(summary)

    prompt = (
        "You are an educational curriculum planner.\n\n"
        "Analyze the topic summary and return a clear learning path in valid JSON.\n\n"
        "Your response must help a learner answer three questions:\n"
        "1. What should I study before this topic?\n"
        "2. What should I study after this topic if I want to go deeper?\n"
        "3. Which references are best for beginner, intermediate, and expert levels?\n\n"
        "Return ONLY valid JSON with this exact schema:\n"
        "{\n"
        '  "before_topics": [\n'
        '    {"title": "topic name", "why": "one-sentence reason"}\n'
        "  ],\n"
        '  "after_topics": [\n'
        '    {"title": "topic name", "why": "one-sentence reason"}\n'
        "  ],\n"
        '  "references_by_level": {\n'
        '    "beginner": [\n'
        '      {"title": "resource title", "type": "book/article/course/video/website", "reason": "why it fits beginners"}\n'
        "    ],\n"
        '    "intermediate": [\n'
        '      {"title": "resource title", "type": "book/article/course/video/website", "reason": "why it fits intermediate learners"}\n'
        "    ],\n"
        '    "expert": [\n'
        '      {"title": "resource title", "type": "book/article/course/video/website", "reason": "why it fits advanced learners"}\n'
        "    ]\n"
        "  }\n"
        "}\n\n"
        "Rules:\n"
        "- Keep each reason concise and specific.\n"
        "- Prioritize foundational prerequisites in before_topics.\n"
        "- Prioritize adjacent advanced topics in after_topics.\n"
        "- Return 3-5 items for before_topics.\n"
        "- Return 3-5 items for after_topics.\n"
        "- Return 2-4 items per reference level.\n"
        "- Do not include markdown or commentary outside the JSON.\n\n"
        "SUMMARY:\n"
        f"{summary}"
    )
    try:
        resp = client.chat.completions.create(
            model=AZURE_OPENAI_DEPLOYMENT,
            temperature=0.2,
            messages=[{"role": "user", "content": prompt}],
        )
        text = resp.choices[0].message.content.strip()
        return json.loads(_extract_json_object(text))
    except APIConnectionError as e:
        print("Azure OpenAI connection error in generate_references:", e)
        return _fallback_references(summary)
    except Exception as e:
        print("Unexpected error in generate_references:", e)
        return _fallback_references(summary)


# -------------------------------------------------------------------
# Helper: safely extract JSON object from model output
# -------------------------------------------------------------------
def _extract_json_object(text: str) -> str:
    """
    Try to pull out the first {...} JSON object from a string.
    This lets us handle responses like ```json { ... } ``` or
    explanations around the JSON.
    """
    if not text:
        return text

    text = text.strip()

    # Remove leading/trailing markdown code fences
    if text.startswith("```"):
        parts = text.split("```", 2)
        if len(parts) >= 2:
            text = parts[1].strip()
    if text.endswith("```"):
        text = text[:-3].strip()

    start = text.find("{")
    end = text.rfind("}")

    if start != -1 and end != -1 and end > start:
        return text[start : end + 1]

    return text


# -------------------------------------------------------------------
# 5) Identify organ from image using vision (chat with image input)
# -------------------------------------------------------------------
def identify_organ(image_path: str) -> Dict:
    client = _get_client()
    if client is None:
        return {"organ": "unknown", "labels": []}

    try:
        with open(image_path, "rb") as f:
            b64 = base64.b64encode(f.read()).decode("utf-8")
    except Exception as e:
        print("Error reading image in identify_organ:", e)
        return {"organ": "unknown", "labels": []}

    messages = [
        {
            "role": "user",
            "content": [
                {
                    "type": "text",
                    "text": (
                        "You are an expert analyst examining visual content from educational materials. "
                        "Analyze this image and provide a detailed academic assessment.\n\n"
                        "Task Requirements:\n"
                        "1. Identify the primary subject, concept, or system depicted in this educational image\n"
                        "2. List key components, elements, or features visible (maximum 10 most significant items)\n"
                        "3. Use precise terminology appropriate for university-level education\n"
                        "4. Prioritize academically relevant and pedagogically significant elements\n\n"
                        "Response Format:\n"
                        "Respond ONLY as pure JSON (no markdown, no code blocks, no additional text) "
                        "in exactly this format:\n"
                        "{\"organ\": \"primary subject or system name\", "
                        "\"labels\": [\"component 1\", \"component 2\", ...]}\n\n"
                        "Note: The field name 'organ' is maintained for technical compatibility, but should contain "
                        "the main subject of the image (e.g., 'solar system', 'cell structure', 'circuit diagram', "
                        "'heart', 'economic model', etc.)\n\n"
                        "Example: {\"organ\": \"photosynthesis process\", "
                        "\"labels\": [\"chloroplast\", \"sunlight\", \"carbon dioxide\", \"glucose\", \"oxygen\"]}"
                    ),
                },
                {
                    "type": "image_url",
                    "image_url": {"url": f"data:image/png;base64,{b64}"},
                },
            ],
        }
    ]

    try:
        resp = client.chat.completions.create(
            model=AZURE_OPENAI_DEPLOYMENT,
            temperature=0.2,
            messages=messages,
        )

        content = resp.choices[0].message.content

        if isinstance(content, list):
            content_text = "".join(
                part.get("text", "")
                for part in content
                if isinstance(part, dict) and "text" in part
            )
        else:
            content_text = content or ""

        content_text = _extract_json_object(content_text)

        try:
            data = json.loads(content_text)
        except Exception as e:
            print("JSON parse error in identify_organ, content was:", repr(content_text))
            print("Error:", e)
            return {"organ": "unknown", "labels": []}

        if "organ" not in data:
            data["organ"] = "unknown"
        if "labels" not in data:
            data["labels"] = []

        return data

    except APIConnectionError as e:
        print("Azure OpenAI connection error in identify_organ:", e)
        return {"organ": "unknown", "labels": []}
    except Exception as e:
        print("Unexpected error in identify_organ:", e)
        return {"organ": "unknown", "labels": []}


# -------------------------------------------------------------------
# 6) Use static organ images from /static/organs
# -------------------------------------------------------------------
def get_static_organ_image(organ: str) -> str | None:
    if not organ:
        return None

    name = organ.lower().strip()

    mapping = {
        # --- Heart & Circulatory ---
        "heart": "Heart.jpg",
        "left ventricle": "Heart.jpg",
        "right ventricle": "Heart.jpg",
        "left atrium": "Heart.jpg",
        "right atrium": "Heart.jpg",
        "aorta": "Heart.jpg",
        "myocardium": "Heart.jpg",
        "valve": "Heart.jpg",
        "pulmonary artery": "Heart.jpg",

        # --- Lungs & Respiratory ---
        "lung": "lungs.jpg",
        "lungs": "lungs.jpg",
        "alveoli": "lungs.jpg",
        "bronchus": "lungs.jpg",
        "bronchi": "lungs.jpg",
        "bronchiole": "lungs.jpg",
        "trachea": "lungs.jpg",
        "pleura": "lungs.jpg",

        # --- Brain & Nervous System ---
        "brain": "Brain.jpg",
        "cerebrum": "Brain.jpg",
        "cerebellum": "Brain.jpg",
        "brainstem": "Brain.jpg",
        "frontal lobe": "Brain.jpg",
        "medulla": "Brain.jpg",
        "pons": "Brain.jpg",

        # --- Eye ---
        "eye": "eye.jpg",
        "eyes": "eye.jpg",
        "retina": "eye.jpg",
        "cornea": "eye.jpg",
        "iris": "eye.jpg",
        "pupil": "eye.jpg",
        "optic nerve": "eye.jpg",
        "sclera": "eye.jpg",

        # --- Mouth & Oral ---
        "mouth": "mouth.jpg",
        "teeth": "mouth.jpg",
        "tooth": "mouth.jpg",
        "tongue": "mouth.jpg",
        "palate": "mouth.jpg",
        "gum": "mouth.jpg",

    }
    

    filename = None

    if name in mapping:
        filename = mapping[name]
    else:
        for key, value in mapping.items():
            if key in name:
                filename = value
                break

    if not filename:
        return None

    from .config import ORGAN_IMAGE_DIR

    path = os.path.join(ORGAN_IMAGE_DIR, filename)
    return path if os.path.exists(path) else None


# -------------------------------------------------------------------
# 7) Convenience: identify organ AND get static detailed image
# -------------------------------------------------------------------
def identify_organ_with_static_image(image_path: str) -> Dict:
    organ_info = identify_organ(image_path)
    organ = organ_info.get("organ", "unknown")
    labels = organ_info.get("labels", [])

    static_image_path = get_static_organ_image(organ)

    return {
        "organ": organ,
        "labels": labels,
        "static_image_path": static_image_path,
    }
