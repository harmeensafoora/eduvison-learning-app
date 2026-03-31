from .azure_openai_utils import azure_json


def _fallback_question(difficulty: str, content: str, question_type: str | None) -> dict:
    head = (content or "this concept").split(".")[0][:120]
    qt = (question_type or "").strip().lower() or None

    if qt == "one_word":
        return {
            "question": f"In one word/term: {head}?",
            "format": "one_word",
            "options": [],
            "correct_answer": head.split(" ")[0] if head.split(" ") else head,
            "explanation": "Answer with a single key term from the concept.",
        }
    if qt == "one_sentence":
        return {
            "question": f"In one sentence: explain {head}.",
            "format": "one_sentence",
            "options": [],
            "correct_answer": head,
            "explanation": "Answer with exactly one sentence.",
        }
    if qt == "fill_blank":
        return {
            "question": f"Fill in the blank: {head} is ____.",
            "format": "fill_blank",
            "options": [],
            "correct_answer": head.split(" ")[0] if head.split(" ") else head,
            "explanation": "Complete the blank with the missing key term.",
        }
    if qt == "mcq":
        return {
            "question": f"Which option best matches {head}?",
            "format": "multiple_choice",
            "options": [head, "Unrelated claim", "Opposite claim", "Irrelevant detail"],
            "correct_answer": head,
            "explanation": "The first option aligns with the concept summary.",
        }
    if difficulty == "easy":
        return {
            "question": f"Which option best matches {head}?",
            "format": "multiple_choice",
            "options": [head, "Unrelated claim", "Opposite claim", "Irrelevant detail"],
            "correct_answer": head,
            "explanation": "The first option aligns with the concept summary.",
        }
    if difficulty == "hard":
        return {
            "question": f"Apply {head} to a new real-world scenario and explain your reasoning.",
            "format": "open_ended",
            "options": [],
            "correct_answer": head,
            "explanation": "A strong answer transfers the concept to unfamiliar context.",
        }
    return {
        "question": f"In 2-3 lines, explain how {head} works in practice.",
        "format": "short_answer",
        "options": [],
        "correct_answer": head,
        "explanation": "A good answer should correctly apply the concept.",
    }


async def generate_quiz_from_content(content: str, difficulty: str, question_type: str | None = None) -> dict:
    qt = (question_type or "").strip().lower() or None
    fallback = _fallback_question(difficulty, content, qt)

    type_rules = ""
    if qt == "one_word":
        type_rules = "Format: one_word. The correct_answer must be a single word/term.\n"
    elif qt == "one_sentence":
        type_rules = "Format: one_sentence. The correct_answer must be exactly one sentence.\n"
    elif qt == "fill_blank":
        type_rules = "Format: fill_blank. The question must contain exactly one blank like ____.\n"
    elif qt == "mcq":
        type_rules = "Format: multiple_choice. Provide exactly 4 options.\n"

    if qt:
        difficulty_guide = ""
    else:
        difficulty_guide = "easy: multiple choice, 4 options.\nmedium: short answer, application.\nhard: open-ended, unfamiliar context.\n"

    prompt = f"""Generate a {difficulty} recall question for this concept: {content}

{difficulty_guide}{type_rules}
Return JSON only:
{{"question":"", "format":"multiple_choice|short_answer|open_ended|one_word|one_sentence|fill_blank", "options":[], "correct_answer":"", "explanation":""}}"""
    return await azure_json(
        system="You produce strict JSON quiz payloads for adaptive learning.",
        prompt=prompt,
        fallback=fallback,
    )


async def evaluate_answer(question_payload: dict, user_answer: str) -> dict:
    correct = question_payload.get("correct_answer", "")
    fallback_score = 100 if user_answer.strip().lower() == str(correct).strip().lower() else 40
    fallback = {
        "score": fallback_score,
        "feedback": "Your answer is on track." if fallback_score >= 80 else "You are close. Focus on the core definition and one application.",
        "misconceptions": [] if fallback_score >= 80 else ["Core mechanism not clearly stated."],
    }
    prompt = f"""Evaluate a learner response.
Question: {question_payload.get('question','')}
Expected answer: {correct}
Learner answer: {user_answer}

Return JSON only: {{"score":0-100, "feedback":"first-person supportive feedback", "misconceptions":["..."]}}"""
    return await azure_json(
        system="You are a rigorous tutor. Score fairly and explain briefly.",
        prompt=prompt,
        fallback=fallback,
    )


def _fallback_check_questions(summary: str, n: int) -> list[dict]:
    lines = [ln.strip() for ln in (summary or "").splitlines() if ln.strip()]
    heads = [ln[4:].strip() for ln in lines if ln.startswith("### ")][: max(1, n)]
    out = []
    for i, h in enumerate(heads[:n]):
        out.append(
            {
                "id": f"q{i+1}",
                "question": f"What is the key idea of “{h}”?",
                "format": "short_answer",
                "options": [],
                "correct_answer": h,
                "explanation": "Explain the concept in your own words using one example.",
            }
        )
    if not out:
        out = [
            {
                "id": "q1",
                "question": "What is the main takeaway from the summary?",
                "format": "short_answer",
                "options": [],
                "correct_answer": "Main takeaway",
                "explanation": "Summarize in 2–3 lines.",
            }
        ]
    return out


async def generate_check_questions_from_summary(summary_markdown: str, n: int = 3) -> list[dict]:
    fallback = _fallback_check_questions(summary_markdown, n)
    prompt = f"""Create {n} short check questions based on this study summary.

Rules:
- Questions must be answerable from the summary.
- Mix formats: multiple_choice and short_answer.
- For multiple_choice, provide 4 options and mark the correct_answer exactly.
- Keep questions concise.

Return JSON only with shape:
{{"questions":[{{"id":"q1","question":"","format":"multiple_choice|short_answer","options":["","", "", ""],"correct_answer":"","explanation":""}}]}}

Summary:
{summary_markdown}
"""
    data = await azure_json(
        system="You generate quick comprehension checks for learning. Output strict JSON.",
        prompt=prompt,
        fallback={"questions": fallback},
    )
    qs = data.get("questions") if isinstance(data, dict) else None
    if isinstance(qs, list) and qs:
        return qs[: max(1, n)]
    return fallback
