from fastapi import FastAPI, UploadFile, File, Body, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles

import uuid
import os
import re
from datetime import datetime
from pydantic import BaseModel
from typing import Optional, List, Dict

from .config import BASE_UPLOAD_DIR, IMAGE_OUTPUT_DIR, ORGAN_IMAGE_DIR
from .pdf_utils import save_upload, extract_text, extract_images
from .ai_utils import (
    summarize_text,
    translate_summary,
    generate_detailed_text,
    generate_references,
    identify_organ,
    get_static_organ_image,
    identify_organ_with_static_image,
)
from .ai.concept_extractor import extract_concepts as ai_extract_concepts
from .ai.confusion_detector import detect_confusion_points as ai_detect_confusion_points
from .ai.explanation_generator import generate_explanations as ai_generate_explanations
from .ai.quiz_generator import create_quiz as ai_create_quiz
from .analytics.user_tracking import EVENT_LOG, track_event as analytics_track_event
from .analytics.engagement_metrics import summarize_engagement
from .models import (
    Topic, TopicProgress, LearnerProfile, QuizQuestion, QuizAttempt,
    DifficultyLevel, QuestionType
)
from .quiz_engine import generate_quiz_from_content, generate_knowledge_gap_assessment, evaluate_answer
from .learning_analytics import LearningAnalytics

# Initialize FastAPI with enhanced learning features
app = FastAPI(title="EduVision - Medical Learning Platform")

# Setup CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount static file directories
app.mount("/files", StaticFiles(directory=BASE_UPLOAD_DIR), name="files")
app.mount("/diagrams", StaticFiles(directory=IMAGE_OUTPUT_DIR), name="diagrams")
app.mount("/organs", StaticFiles(directory=ORGAN_IMAGE_DIR), name="organs")

PROJECT_ROOT = os.path.dirname(os.path.dirname(__file__))
INDEX_HTML_PATH = os.path.join(PROJECT_ROOT, "index.html")
STATIC_DIR = os.path.join(PROJECT_ROOT, "static")

app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


# --- Pydantic Models for API Request Bodies ---
class QuizAnswerSubmission(BaseModel):
    question_id: str
    answer: str
    time_taken_seconds: int = 0


class NoteData(BaseModel):
    topic_id: str
    text: str
    position: Optional[int] = None


class BookmarkData(BaseModel):
    topic_id: str
    content: str
    position: int = 0


class SessionRequest(BaseModel):
    session_id: str


class GraphRequest(BaseModel):
    session_id: Optional[str] = None
    concepts: Optional[List[Dict]] = None


class ConfusionRequest(BaseModel):
    session_id: Optional[str] = None
    concepts: Optional[List[Dict]] = None


class ExplanationRequest(BaseModel):
    session_id: Optional[str] = None
    concept: Dict
    modes: List[str] = []


class QuizCreateRequest(BaseModel):
    session_id: str
    difficulty: str = "intermediate"
    question_count: int = 8


class AnalyticsEventRequest(BaseModel):
    type: str
    session_id: Optional[str] = None
    metadata: Dict = {}


# --- Global data stores ---
LEARNER_PROFILES: Dict[str, LearnerProfile] = {}
SESSION_DATA: dict[str, dict] = {}


# --- Helper functions for URL generation ---
def to_original_url(path: str) -> str:
    """Convert file path to /files URL."""
    rel = os.path.relpath(path, BASE_UPLOAD_DIR).replace("\\", "/")
    return f"/files/{rel}"


def to_diagram_url(path: str | None) -> str | None:
    """Convert file path to /diagrams URL."""
    if not path:
        return None
    rel = os.path.relpath(path, IMAGE_OUTPUT_DIR).replace("\\", "/")
    return f"/diagrams/{rel}"


def to_organ_url(path: str | None) -> str | None:
    """Convert file path to /organs URL."""
    if not path:
        return None
    rel = os.path.relpath(path, ORGAN_IMAGE_DIR).replace("\\", "/")
    return f"/organs/{rel}"


def extract_learning_objectives(summary: str) -> List[str]:
    """Extract key learning objectives from summary."""
    objectives = []
    lines = summary.split("\n")
    for line in lines[:5]:
        if line.strip().startswith("#"):
            obj = line.replace("#", "").strip()
            if obj:
                objectives.append(f"Understand {obj}")
    return objectives[:5]


def slugify(value: str) -> str:
    """Create a simple stable id from a string."""
    cleaned = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return cleaned or str(uuid.uuid4())[:8]


def extract_concepts_from_summary(summary: str) -> List[Dict]:
    """Derive concept cards from markdown summary headings and bullets."""
    concepts: List[Dict] = []
    current: Dict | None = None

    for raw_line in summary.splitlines():
        line = raw_line.strip()
        if not line:
            continue

        if line.startswith("### "):
            title = line[4:].strip()
            current = {
                "id": slugify(title),
                "name": title,
                "summary": "",
                "bullets": [],
                "type": "core",
                "importance": 1,
            }
            concepts.append(current)
            continue

        if current and line.startswith(("- ", "* ")):
            bullet = line[2:].strip()
            if bullet:
                current["bullets"].append(bullet)

    if not concepts:
        fallback_lines = [
            line.strip("-*# ").strip()
            for line in summary.splitlines()
            if line.strip()
        ]
        fallback_text = fallback_lines[:4]
        for idx, line in enumerate(fallback_text):
            concepts.append(
                {
                    "id": f"concept-{idx + 1}",
                    "name": line[:80],
                    "summary": line,
                    "bullets": [line],
                    "type": "core",
                    "importance": 1,
                }
            )

    for index, concept in enumerate(concepts):
        bullets = concept.get("bullets", [])
        concept["summary"] = bullets[0] if bullets else f"Key idea from {concept['name']}."
        concept["importance"] = max(1, min(5, len(bullets) or (len(concepts) - index)))
        concept["type"] = "foundation" if index == 0 else ("bridge" if index < 3 else "detail")

    return concepts[:10]


def build_knowledge_graph(concepts: List[Dict]) -> Dict:
    """Create a lightweight graph model for the frontend."""
    nodes = [
        {
            "id": concept["id"],
            "name": concept["name"],
            "group": concept.get("type", "core"),
            "importance": concept.get("importance", 1),
        }
        for concept in concepts
    ]

    links: List[Dict] = []
    for index in range(max(0, len(nodes) - 1)):
        links.append(
            {
                "source": nodes[index]["id"],
                "target": nodes[index + 1]["id"],
                "strength": max(1, 4 - min(index, 3)),
            }
        )

    if len(nodes) > 2:
        links.append(
            {
                "source": nodes[0]["id"],
                "target": nodes[-1]["id"],
                "strength": 1,
            }
        )

    return {"nodes": nodes, "links": links}


def detect_confusion_points(concepts: List[Dict]) -> List[Dict]:
    """Flag denser concepts that likely need extra explanation."""
    confusion_points: List[Dict] = []
    for concept in concepts:
        bullets = concept.get("bullets", [])
        if len(bullets) >= 3 or any(len(item.split()) > 12 for item in bullets):
            confusion_points.append(
                {
                    "concept": concept["name"],
                    "reason": "Dense concept cluster detected from the source summary.",
                    "tip": "Review the details tab and quiz this concept after the summary pass.",
                }
            )
    return confusion_points[:3]


def estimate_study_time_minutes(text: str, concepts: List[Dict]) -> int:
    """Estimate study time from text length and concept count."""
    word_count = len(text.split())
    baseline = max(8, word_count // 180)
    return min(90, baseline + len(concepts) * 4)


def compute_complexity_score(text: str, concepts: List[Dict]) -> int:
    """Approximate content complexity for the status panel."""
    word_count = len(text.split())
    score = 25 + min(45, word_count // 120) + min(30, len(concepts) * 3)
    return max(10, min(100, score))


def build_session_overview(
    session_id: str,
    filename: str,
    text: str,
    summary: str,
    image_count: int,
    intent: str | None = None,
) -> Dict:
    """Build structured metadata used by the upgraded frontend."""
    concepts = extract_concepts_from_summary(summary)
    graph = build_knowledge_graph(concepts)
    confusion_points = detect_confusion_points(concepts)
    learning_objectives = extract_learning_objectives(summary)
    main_topic = concepts[0]["name"] if concepts else os.path.splitext(filename)[0]
    study_time_minutes = estimate_study_time_minutes(text, concepts)
    complexity = compute_complexity_score(text, concepts)

    return {
        "session_id": session_id,
        "file_name": filename,
        "intent": intent or "Understand the chapter",
        "main_topic": main_topic,
        "learning_objectives": learning_objectives,
        "concepts": concepts,
        "graph": graph,
        "confusion_points": confusion_points,
        "estimated_study_time_minutes": study_time_minutes,
        "estimated_study_time_label": f"{study_time_minutes} min",
        "complexity": complexity,
        "visuals_count": image_count,
        "share_card": {
            "headline": f"{len(concepts)} concepts mapped from {filename}",
            "stats": {
                "concepts": len(concepts),
                "visuals": image_count,
                "study_time_minutes": study_time_minutes,
                "confusion_points": len(confusion_points),
            },
            "top_concepts": [concept["name"] for concept in concepts[:5]],
        },
    }


# ============================================================================
# CORE ENDPOINTS - PDF Upload & Content Extraction
# ============================================================================

@app.get("/")
async def serve_index():
    """Serve the single-page frontend."""
    html_path = INDEX_HTML_PATH
    new_frontend_path = os.path.join(PROJECT_ROOT, "eduvision-progressive.html")
    if os.path.exists(new_frontend_path):
        html_path = new_frontend_path
    with open(html_path, "r", encoding="utf-8") as f:
        content = f.read()
    return HTMLResponse(content=content)

@app.post("/upload")
async def upload_pdf(
    file: UploadFile = File(...),
    intent: Optional[str] = Form(None),
):
    """
    Upload a medical PDF and initialize learning session.
    Extracts text, images, and generates initial summary.
    """
    contents = await file.read()
    session_id = str(uuid.uuid4())

    # Save and extract content
    pdf_path = save_upload(file.filename, contents)
    text = extract_text(pdf_path)
    summary = summarize_text(text)
    image_paths = extract_images(pdf_path, session_id)

    # Filter images by size
    large_image_paths: list[str] = []
    for path in image_paths:
        try:
            if os.path.getsize(path) > 1024:  # Keep only > 1KB
                large_image_paths.append(path)
            else:
                os.remove(path)
        except OSError:
            continue

    # Store session data
    SESSION_DATA[session_id] = {
        "pdf_path": pdf_path,
        "text": text,
        "summary": summary,
        "intent": intent or "Understand the chapter",
        "images": large_image_paths,
        "translations": {},
        "details": None,
        "references": None,
        "labeled": [],
    }
    SESSION_DATA[session_id]["overview"] = build_session_overview(
        session_id=session_id,
        filename=file.filename,
        text=text,
        summary=summary,
        image_count=len(large_image_paths),
        intent=intent,
    )

    # Initialize learner profile
    learner = LearnerProfile(
        session_id=session_id,
        created_at=datetime.now(),
    )

    main_topic = Topic(
        id=session_id,
        name=os.path.splitext(file.filename)[0],
        summary=summary,
        prerequisites=[],
        difficulty=DifficultyLevel.INTERMEDIATE,
        estimated_time_minutes=45,
    )

    learner.add_topic(main_topic)
    LEARNER_PROFILES[session_id] = learner

    overview = SESSION_DATA[session_id]["overview"]

    return {
        "session_id": session_id,
        "summary": summary,
        "image_count": len(large_image_paths),
        "learning_objectives": overview["learning_objectives"],
        "intent": overview["intent"],
        "overview": overview,
    }


@app.post("/api/process-pdf")
async def process_pdf_api(
    file: UploadFile = File(...),
    intent: Optional[str] = Form(None),
):
    """Guide-aligned alias for document processing."""
    return await upload_pdf(file, intent)


# ============================================================================
# NEW FRONTEND ENDPOINTS - For eduvision-progressive.html
# ============================================================================

@app.get("/app.js")
async def serve_app_js():
    """Serve the frontend JavaScript (legacy route)."""
    from fastapi.responses import Response
    app_js_path = os.path.join(STATIC_DIR, "app.js")
    if os.path.exists(app_js_path):
        with open(app_js_path, "r", encoding="utf-8") as f:
            content = f.read()
        return Response(content=content, media_type="application/javascript")
    return JSONResponse(status_code=404, content={"error": "app.js not found"})


@app.get("/favicon.ico")
async def favicon():
    """Return empty 204 for favicon — no body allowed on 204."""
    from fastapi.responses import Response
    return Response(status_code=204)


@app.post("/api/process")
async def process_document_new_frontend(
    file: UploadFile = File(...),
    learningIntent: str = Form(...),
    sessionId: Optional[str] = Form(None)
):
    """
    Process document endpoint compatible with new frontend.
    Maps to existing upload_pdf endpoint.
    """
    # Use existing upload logic
    result = await upload_pdf(file, learningIntent)
    
    # Extract data for new frontend format
    session_id = result["session_id"]
    data = SESSION_DATA.get(session_id)
    overview = data.get("overview", {})
    
    # Return in format expected by new frontend
    return {
        "sessionId": session_id,
        "status": "complete",
        "mainTopic": overview.get("main_topic", "Unknown"),
        "complexity": f"{overview.get('complexity', 50)}/100",
        "studyTime": overview.get("estimated_study_time_label", "10 min"),
        "visuals": overview.get("visuals_count", 0),
        "concepts": overview.get("concepts", []),
        "confusionPoints": overview.get("confusion_points", []),
        "summary": result["summary"],
        "stages": [
            {"id": "extract", "label": "Extracting text and structure", "status": "complete"},
            {"id": "concepts", "label": "Identifying core concepts", "status": "complete"},
            {"id": "relationships", "label": "Mapping relationships", "status": "complete"},
            {"id": "visuals", "label": "Preparing visuals", "status": "complete"},
            {"id": "hooks", "label": "Generating study hooks", "status": "complete"}
        ]
    }


@app.post("/api/generate-details")
async def generate_details_new_frontend(sessionId: str = Form(...)):
    """Generate detailed explanation - new frontend compatible."""
    data = SESSION_DATA.get(sessionId)
    if not data:
        return JSONResponse(status_code=404, content={"error": "Session not found"})
    
    if not data["details"]:
        data["details"] = generate_detailed_text(data["summary"], data["text"])
    
    return {
        "sessionId": sessionId,
        "content": data["details"]
    }


@app.post("/api/translate")
async def translate_new_frontend(
    sessionId: str = Form(...),
    language: str = Form(...)
):
    """Translate content - new frontend compatible."""
    data = SESSION_DATA.get(sessionId)
    if not data:
        return JSONResponse(status_code=404, content={"error": "Session not found"})
    
    if language not in data["translations"]:
        data["translations"][language] = translate_summary(data["summary"], language)
    
    return {
        "sessionId": sessionId,
        "language": language,
        "content": data["translations"][language]
    }


@app.post("/api/generate-quiz")
async def generate_quiz_new_frontend(
    sessionId: str = Form(...),
    difficulty: str = Form(...)
):
    """Generate quiz - new frontend compatible."""
    data = SESSION_DATA.get(sessionId)
    learner = LEARNER_PROFILES.get(sessionId)
    
    if not data or not learner:
        return JSONResponse(status_code=404, content={"error": "Invalid session"})
    
    try:
        difficulty_level = DifficultyLevel(difficulty)
    except ValueError:
        difficulty_level = DifficultyLevel.INTERMEDIATE
    
    questions = generate_quiz_from_content(
        topic_name=list(learner.topics.values())[0].name if learner.topics else "Topic",
        summary=data["summary"],
        detailed_text=data.get("details", ""),
        difficulty=difficulty_level,
        num_questions=8
    )
    
    quiz_id = str(uuid.uuid4())
    learner.quizzes[quiz_id] = questions
    
    # Format for new frontend
    formatted_questions = []
    for q in questions:
        formatted_q = {
            "id": q.id,
            "question": q.question,
            "type": q.type.value,
            "options": [],
            "correctAnswer": q.correct_answer,
        }

        if q.type in (QuestionType.MULTIPLE_CHOICE, QuestionType.TRUE_FALSE) and q.options:
            formatted_q["options"] = [
                {"id": chr(97 + i), "text": opt}
                for i, opt in enumerate(q.options)
            ]

        formatted_questions.append(formatted_q)

    return {
        "sessionId": sessionId,
        "difficulty": difficulty,
        "questions": formatted_questions,
    }


@app.post("/api/submit-quiz")
async def submit_quiz_new_frontend(
    sessionId: str = Form(...),
    answers: str = Form(...)
):
    """Submit quiz answers - new frontend compatible."""
    import json
    
    learner = LEARNER_PROFILES.get(sessionId)
    if not learner:
        return JSONResponse(status_code=404, content={"error": "Session not found"})
    
    user_answers = json.loads(answers)
    
    # Find the most recent quiz
    if not learner.quizzes:
        return JSONResponse(status_code=404, content={"error": "No quiz found"})
    
    quiz_id = list(learner.quizzes.keys())[-1]
    questions = learner.quizzes[quiz_id]
    
    total_questions = len(questions)
    correct_count = 0
    results = []
    
    for question in questions:
        user_answer_id = user_answers.get(str(question.id), "")
        
        # Convert letter answer to actual text if multiple choice
        if question.type == QuestionType.MULTIPLE_CHOICE and question.options:
            try:
                answer_idx = ord(user_answer_id) - 97  # Convert 'a' to 0, 'b' to 1, etc.
                user_answer_text = question.options[answer_idx] if 0 <= answer_idx < len(question.options) else ""
            except:
                user_answer_text = user_answer_id
        else:
            user_answer_text = user_answer_id

        evaluation = evaluate_answer(question, user_answer_text)

        if evaluation["is_correct"]:
            correct_count += 1

        results.append({
            "questionId": str(question.id),
            "userAnswer": user_answer_id,
            "correctAnswer": question.correct_answer,
            "isCorrect": evaluation["is_correct"],
        })

    percentage = round((correct_count / total_questions) * 100) if total_questions > 0 else 0

    # Persist quiz attempt so dashboard analytics update
    topic_id = list(learner.topics.keys())[0] if learner.topics else None
    if topic_id and topic_id in learner.topic_progress:
        attempt = QuizAttempt(
            quiz_id=quiz_id,
            timestamp=datetime.now(),
            answers=user_answers,
            score=percentage,
            time_taken=0,
            topics_covered=[topic_id],
        )
        learner.topic_progress[topic_id].quiz_attempts.append(attempt)
        learner.topic_progress[topic_id].best_quiz_score = max(
            learner.topic_progress[topic_id].best_quiz_score, percentage
        )
        learner.topic_progress[topic_id].completion_percentage = min(
            learner.topic_progress[topic_id].completion_percentage + 20, 100
        )

    return {
        "sessionId": sessionId,
        "score": correct_count,
        "total": total_questions,
        "percentage": percentage,
        "results": results,
    }


@app.post("/api/generate-roadmap")
async def generate_roadmap_new_frontend(sessionId: str = Form(...)):
    """Generate study roadmap - new frontend compatible."""
    data = SESSION_DATA.get(sessionId)
    if not data:
        return JSONResponse(status_code=404, content={"error": "Session not found"})
    
    if not data["references"]:
        data["references"] = generate_references(data["summary"])
    
    refs = data["references"]

    before = []
    after = []
    by_level = {"beginner": [], "intermediate": [], "expert": []}

    if isinstance(refs, dict):
        for item in refs.get("before_topics", []):
            before.append({"title": item.get("title", ""), "subtitle": item.get("why", "")})
        for item in refs.get("after_topics", []):
            after.append({"title": item.get("title", ""), "subtitle": item.get("why", "")})
        raw_levels = refs.get("references_by_level", {})
        for level in ("beginner", "intermediate", "expert"):
            by_level[level] = raw_levels.get(level, [])

    if not before:
        before = [
            {"title": "Basic Biology", "subtitle": "Foundational concepts"},
            {"title": "Introduction to the Topic", "subtitle": "Overview and context"},
        ]
    if not after:
        after = [
            {"title": "Advanced Topics", "subtitle": "Building on fundamentals"},
            {"title": "Practical Applications", "subtitle": "Real-world scenarios"},
        ]

    return {
        "sessionId": sessionId,
        "roadmap": {
            "before": before[:5],
            "after": after[:5],
            "byLevel": by_level,
        },
    }


@app.post("/api/load-dashboard")
async def load_dashboard_new_frontend(sessionId: str = Form(...)):
    """Load analytics dashboard - new frontend compatible."""
    learner = LEARNER_PROFILES.get(sessionId)
    if not learner:
        return JSONResponse(status_code=404, content={"error": "Session not found"})
    
    learner.calculate_overall_progress()
    stats = learner.get_dashboard_stats()
    recommendations = LearningAnalytics.get_study_recommendations(learner)

    # Build per-topic performance for strengths / practice lists
    topic_names = {tid: t.name for tid, t in learner.topics.items()}
    strengths: List[str] = []
    needs_practice: List[str] = []
    for topic_id, progress in learner.topic_progress.items():
        name = topic_names.get(topic_id, topic_id)
        if progress.quiz_attempts:
            if progress.best_quiz_score >= 70:
                strengths.append(name)
            else:
                needs_practice.append(name)
    # If no quiz attempts yet, list all topics as needing practice
    if not strengths and not needs_practice:
        needs_practice = list(topic_names.values())[:5]

    analytics = {
        "progress": round(learner.overall_completion_percentage),
        "quizzesTaken": stats.get("total_quizzes_taken", 0),
        "accuracy": round(stats.get("average_quiz_score", 0)),
        "recommendations": [
            {
                "type": "focus",
                "title": recommendations[0].get("title", "💡 Recommendation") if recommendations else "💡 Recommendation",
                "message": recommendations[0].get("description", "Keep up the great work!") if recommendations else "Keep up the great work!",
            },
            {
                "type": "next",
                "title": recommendations[1].get("title", "🎯 Next Steps") if len(recommendations) > 1 else "🎯 Next Steps",
                "message": recommendations[1].get("description", "Continue your learning journey") if len(recommendations) > 1 else "Continue your learning journey",
            },
        ],
        "strengths": strengths[:5],
        "needsPractice": needs_practice[:5],
    }
    
    return {
        "sessionId": sessionId,
        "analytics": analytics
    }


@app.post("/api/load-images")
async def load_images_new_frontend(sessionId: str = Form(...)):
    """Load extracted images - new frontend compatible."""
    data = SESSION_DATA.get(sessionId)
    if not data:
        return JSONResponse(status_code=404, content={"error": "Session not found"})
    
    images = []
    for path in data["images"]:
        images.append({
            "url": to_original_url(path),
            "title": f"Image {len(images) + 1}",
            "description": "Extracted diagram"
        })
    
    return {
        "sessionId": sessionId,
        "images": images
    }


# ============================================================================
# ORIGINAL ENDPOINTS - Maintained for compatibility
# ============================================================================

@app.get("/summary/{session_id}")
async def get_summary(session_id: str):
    """Get the PDF summary."""
    data = SESSION_DATA.get(session_id)
    if not data:
        return JSONResponse(status_code=404, content={"error": "Invalid session_id"})
    return {"summary": data["summary"]}


@app.get("/session/{session_id}/overview")
async def get_session_overview(session_id: str):
    """Get derived metadata for the transformed workspace."""
    data = SESSION_DATA.get(session_id)
    if not data:
        return JSONResponse(status_code=404, content={"error": "Invalid session_id"})
    return data.get("overview", {})


@app.get("/translate/{session_id}")
async def get_translation(session_id: str, language: str):
    """Translate the summary to another language."""
    data = SESSION_DATA.get(session_id)
    if not data:
        return JSONResponse(status_code=404, content={"error": "Invalid session_id"})

    if language not in data["translations"]:
        data["translations"][language] = translate_summary(data["summary"], language)
    return {"language": language, "summary": data["translations"][language]}


@app.get("/details/{session_id}")
async def get_details(session_id: str):
    """Get detailed explanation of the content."""
    data = SESSION_DATA.get(session_id)
    if not data:
        return JSONResponse(status_code=404, content={"error": "Invalid session_id"})

    if not data["details"]:
        data["details"] = generate_detailed_text(data["summary"], data["text"])
    return {"details": data["details"]}


@app.get("/references/{session_id}")
async def get_refs(session_id: str):
    """Get prerequisite topics and references."""
    data = SESSION_DATA.get(session_id)
    if not data:
        return JSONResponse(status_code=404, content={"error": "Invalid session_id"})

    if not data["references"]:
        data["references"] = generate_references(data["summary"])
    return {"references": data["references"]}


@app.get("/images/{session_id}")
async def get_images(session_id: str):
    """Get extracted images from PDF."""
    data = SESSION_DATA.get(session_id)
    if not data:
        return JSONResponse(status_code=404, content={"error": "Invalid session_id"})
    return {
        "images": [to_original_url(path) for path in data["images"]],
        "labeled": data["labeled"],
    }


@app.get("/share-card/{session_id}")
async def get_share_card(session_id: str):
    """Return simple share-card metadata for the frontend."""
    data = SESSION_DATA.get(session_id)
    if not data:
        return JSONResponse(status_code=404, content={"error": "Invalid session_id"})
    overview = data.get("overview", {})
    return {
        "session_id": session_id,
        "file_name": overview.get("file_name"),
        "headline": overview.get("share_card", {}).get("headline"),
        "stats": overview.get("share_card", {}).get("stats", {}),
        "top_concepts": overview.get("share_card", {}).get("top_concepts", []),
    }


@app.post("/api/generate-knowledge-graph")
async def generate_knowledge_graph_api(request: GraphRequest):
    """Guide-aligned graph endpoint."""
    concepts = request.concepts
    if request.session_id and not concepts:
        data = SESSION_DATA.get(request.session_id)
        if not data:
            return JSONResponse(status_code=404, content={"error": "Invalid session_id"})
        concepts = data.get("overview", {}).get("concepts") or ai_extract_concepts(data["summary"])
    concepts = concepts or []
    return build_knowledge_graph(concepts)


@app.post("/api/detect-confusion-points")
async def detect_confusion_points_api(request: ConfusionRequest):
    """Guide-aligned confusion endpoint."""
    concepts = request.concepts
    if request.session_id and not concepts:
        data = SESSION_DATA.get(request.session_id)
        if not data:
            return JSONResponse(status_code=404, content={"error": "Invalid session_id"})
        concepts = data.get("overview", {}).get("concepts") or ai_extract_concepts(data["summary"])
    return {"confusion_points": ai_detect_confusion_points(concepts or [])}


@app.post("/api/generate-explanations")
async def generate_explanations_api(request: ExplanationRequest):
    """Guide-aligned explanation endpoint."""
    summary = ""
    text = ""
    if request.session_id:
        data = SESSION_DATA.get(request.session_id)
        if not data:
            return JSONResponse(status_code=404, content={"error": "Invalid session_id"})
        summary = data["summary"]
        text = data["text"]
    return ai_generate_explanations(summary, text, request.concept, request.modes or ["technical"])


@app.post("/api/create-quiz")
async def create_quiz_api(request: QuizCreateRequest):
    """Guide-aligned quiz creation endpoint."""
    data = SESSION_DATA.get(request.session_id)
    learner = LEARNER_PROFILES.get(request.session_id)
    if not data or not learner:
        return JSONResponse(status_code=404, content={"error": "Invalid session"})

    questions = ai_create_quiz(
        topic_name=list(learner.topics.values())[0].name if learner.topics else "Topic",
        summary=data["summary"],
        detailed_text=data.get("details") or "",
        difficulty=request.difficulty,
        question_count=request.question_count,
    )
    quiz_id = str(uuid.uuid4())
    learner.quizzes[quiz_id] = questions

    return {
        "quiz_id": quiz_id,
        "questions": [q.to_dict() for q in questions],
        "total_questions": len(questions),
        "difficulty": request.difficulty,
    }


@app.post("/api/generate-share-card")
async def generate_share_card_api(request: SessionRequest):
    """Guide-aligned share card endpoint."""
    return await get_share_card(request.session_id)


@app.post("/api/track-analytics")
async def track_analytics_api(request: AnalyticsEventRequest):
    """Guide-aligned analytics tracking endpoint."""
    event = {
        "type": request.type,
        "session_id": request.session_id,
        "metadata": request.metadata,
    }
    tracking = analytics_track_event(event)
    return {
        **tracking,
        "engagement": summarize_engagement(EVENT_LOG),
    }


@app.post("/images/label/{session_id}")
async def label_images(session_id: str):
    """Identify and label anatomical structures in extracted images."""
    data = SESSION_DATA.get(session_id)
    if not data:
        return JSONResponse(status_code=404, content={"error": "Invalid session_id"})

    labeled_outputs = []

    for img_path in data["images"]:
        organ_info = identify_organ(img_path)
        organ = organ_info.get("organ", "unknown")
        labels = organ_info.get("labels", [])

        static_organ_path = get_static_organ_image(organ)

        labeled_outputs.append(
            {
                "original": to_original_url(img_path),
                "organ": organ,
                "labels": labels,
                "labeled_image": static_organ_path,
                "labeled_image_url": to_organ_url(static_organ_path),
                "image_generation_status": (
                    "ok" if static_organ_path else "not_found"
                ),
            }
        )

    data["labeled"] = labeled_outputs
    SESSION_DATA[session_id] = data

    return {"results": labeled_outputs}


@app.post("/identify-organ-image")
async def identify_organ_image(file: UploadFile = File(...)):
    """Identify organ from uploaded anatomy image."""
    contents = await file.read()
    ext = os.path.splitext(file.filename)[1] or ".png"

    single_image_dir = os.path.join(BASE_UPLOAD_DIR, "single_images")
    os.makedirs(single_image_dir, exist_ok=True)

    image_path = os.path.join(single_image_dir, f"{uuid.uuid4()}{ext}")
    with open(image_path, "wb") as f:
        f.write(contents)

    organ_info = identify_organ_with_static_image(image_path)
    organ = organ_info.get("organ", "unknown")
    labels = organ_info.get("labels", [])
    static_image_path = organ_info.get("static_image_path")

    return {
        "organ": organ,
        "labels": labels,
        "original_image": to_original_url(image_path),
        "detailed_image": static_image_path,
        "detailed_image_url": to_organ_url(static_image_path),
        "image_generation_status": "ok" if static_image_path else "not_found",
    }


# ============================================================================
# NEW FEATURES - Enhanced Learning Platform
# ============================================================================

@app.post("/quiz/generate/{session_id}")
async def generate_quiz(session_id: str, difficulty: str = "intermediate"):
    """Generate AI-powered quiz questions from content."""
    data = SESSION_DATA.get(session_id)
    learner = LEARNER_PROFILES.get(session_id)

    if not data or not learner:
        return JSONResponse(status_code=404, content={"error": "Invalid session"})

    try:
        difficulty_level = DifficultyLevel(difficulty)
    except ValueError:
        difficulty_level = DifficultyLevel.INTERMEDIATE

    questions = generate_quiz_from_content(
        topic_name=list(learner.topics.values())[0].name if learner.topics else "Topic",
        summary=data["summary"],
        detailed_text=data.get("details", ""),
        difficulty=difficulty_level,
        num_questions=8
    )

    quiz_id = str(uuid.uuid4())
    learner.quizzes[quiz_id] = questions

    return {
        "quiz_id": quiz_id,
        "questions": [q.to_dict() for q in questions],
        "total_questions": len(questions),
        "difficulty": difficulty,
    }


@app.post("/quiz/submit/{session_id}/{quiz_id}")
async def submit_quiz(
    session_id: str,
    quiz_id: str,
    answers: List[QuizAnswerSubmission] = Body(...)
):
    """Submit quiz answers and receive immediate feedback."""
    learner = LEARNER_PROFILES.get(session_id)
    if not learner or quiz_id not in learner.quizzes:
        return JSONResponse(status_code=404, content={"error": "Invalid session or quiz"})

    questions = learner.quizzes[quiz_id]
    total_points = 0
    score_points = 0
    results = []

    for answer in answers:
        question = next((q for q in questions if q.id == answer.question_id), None)
        if not question:
            continue

        total_points += question.points
        evaluation = evaluate_answer(question, answer.answer)

        score_points += evaluation["score"]
        results.append({
            "question_id": answer.question_id,
            "is_correct": evaluation["is_correct"],
            "score": evaluation["score"],
            "explanation": evaluation["explanation"],
            "your_answer": answer.answer,
            "correct_answer": evaluation["correct_answer"],
        })

    score_percentage = (score_points / total_points * 100) if total_points > 0 else 0

    # Record attempt
    topic_id = list(learner.topics.keys())[0]
    attempt = QuizAttempt(
        quiz_id=quiz_id,
        timestamp=datetime.now(),
        answers={a.question_id: a.answer for a in answers},
        score=score_percentage,
        time_taken=sum(a.time_taken_seconds for a in answers),
        topics_covered=[topic_id],
    )

    learner.topic_progress[topic_id].quiz_attempts.append(attempt)
    learner.topic_progress[topic_id].best_quiz_score = max(
        learner.topic_progress[topic_id].best_quiz_score,
        score_percentage
    )
    learner.topic_progress[topic_id].completion_percentage = min(
        learner.topic_progress[topic_id].completion_percentage + 20, 100
    )

    return {
        "quiz_id": quiz_id,
        "score": round(score_percentage, 2),
        "max_points": total_points,
        "earned_points": score_points,
        "mastery_level": learner.topic_progress[topic_id].get_mastery_level(),
        "results": results,
        "feedback": f"You scored {score_percentage:.1f}%! " + (
            "Excellent work! Keep it up!" if score_percentage >= 90
            else "Good effort! Review the material and try again." if score_percentage >= 70
            else "Keep practicing to strengthen your understanding."
        ),
    }


@app.post("/notes/add/{session_id}")
async def add_note(session_id: str, note: NoteData):
    """Add study notes to a topic."""
    learner = LEARNER_PROFILES.get(session_id)
    if not learner or note.topic_id not in learner.topic_progress:
        return JSONResponse(status_code=404, content={"error": "Invalid session or topic"})

    learner.topic_progress[note.topic_id].notes += f"\n{note.text}"
    return {"status": "success", "notes_length": len(learner.topic_progress[note.topic_id].notes)}


@app.post("/bookmark/add/{session_id}")
async def add_bookmark(session_id: str, bookmark: BookmarkData):
    """Bookmark important content for quick reference."""
    learner = LEARNER_PROFILES.get(session_id)
    if not learner or bookmark.topic_id not in learner.topic_progress:
        return JSONResponse(status_code=404, content={"error": "Invalid session or topic"})

    learner.topic_progress[bookmark.topic_id].bookmarks.append({
        "content": bookmark.content,
        "position": bookmark.position,
        "timestamp": datetime.now().isoformat(),
    })

    return {
        "status": "success",
        "bookmarks_count": len(learner.topic_progress[bookmark.topic_id].bookmarks)
    }


@app.get("/dashboard/{session_id}")
async def learning_dashboard(session_id: str):
    """Get comprehensive learning dashboard and progress overview."""
    learner = LEARNER_PROFILES.get(session_id)
    if not learner:
        return JSONResponse(status_code=404, content={"error": "Invalid session"})

    learner.calculate_overall_progress()
    stats = learner.get_dashboard_stats()
    recommendations = LearningAnalytics.get_study_recommendations(learner)
    velocity = LearningAnalytics.get_learning_velocity(learner)
    weak_areas = LearningAnalytics.identify_weak_areas(learner)

    return {
        "session_id": session_id,
        "stats": stats,
        "velocity": velocity,
        "recommendations": recommendations,
        "weak_areas": weak_areas,
        "study_plan": LearningAnalytics.generate_study_plan(learner, weeks=4),
    }


@app.get("/progress/{session_id}/{topic_id}")
async def topic_progress(session_id: str, topic_id: str):
    """Get detailed progress on a specific topic."""
    learner = LEARNER_PROFILES.get(session_id)
    if not learner or topic_id not in learner.topic_progress:
        return JSONResponse(status_code=404, content={"error": "Invalid session or topic"})

    progress = learner.topic_progress[topic_id]
    topic = learner.topics.get(topic_id)

    spaced_rep = LearningAnalytics.get_spaced_repetition_schedule(progress)
    mastery_prob = LearningAnalytics.estimate_mastery_probability(
        progress.best_quiz_score,
        len(progress.quiz_attempts),
        (datetime.now() - progress.last_viewed).days,
    )

    return {
        "topic_id": topic_id,
        "topic_name": topic.name if topic else topic_id,
        "progress": progress.to_dict(),
        "spaced_repetition": spaced_rep,
        "mastery_probability": mastery_prob,
        "next_difficulty": LearningAnalytics.get_difficulty_recommendation(progress).value,
        "notes_preview": progress.notes[:200] if progress.notes else "",
        "bookmarks_count": len(progress.bookmarks),
    }


@app.post("/assessment/diagnostic/{session_id}")
async def diagnostic_assessment(session_id: str):
    """Generate diagnostic assessment to identify knowledge gaps."""
    data = SESSION_DATA.get(session_id)
    learner = LEARNER_PROFILES.get(session_id)

    if not data or not learner:
        return JSONResponse(status_code=404, content={"error": "Invalid session"})

    questions = generate_knowledge_gap_assessment(
        topic_name=list(learner.topics.values())[0].name if learner.topics else "Topic",
        summary=data["summary"],
    )

    assessment_id = str(uuid.uuid4())
    learner.quizzes[assessment_id] = questions

    return {
        "assessment_id": assessment_id,
        "questions": [q.to_dict() for q in questions],
        "purpose": "This diagnostic assessment helps identify knowledge gaps and misconceptions",
    }


@app.get("/learning-path/{session_id}")
async def get_learning_path(session_id: str):
    """Get personalized learning path based on prerequisites and progress."""
    learner = LEARNER_PROFILES.get(session_id)
    if not learner:
        return JSONResponse(status_code=404, content={"error": "Invalid session"})

    path = LearningAnalytics.get_learning_path(learner)
    next_topics = [p for p in path if p["prerequisites_met"]][:3]

    return {
        "current_progress": learner.overall_completion_percentage,
        "recommended_next_topics": next_topics,
        "all_available_topics": path,
        "next_review_topics": learner.get_next_review_topics(),
    }


@app.post("/session/new")
async def create_learning_session():
    """Create a new learning session without uploading a PDF."""
    session_id = str(uuid.uuid4())

    SESSION_DATA[session_id] = {
        "pdf_path": None,
        "text": "",
        "summary": "",
        "images": [],
        "translations": {},
        "details": None,
        "references": None,
        "labeled": [],
    }

    learner = LearnerProfile(session_id=session_id, created_at=datetime.now())
    LEARNER_PROFILES[session_id] = learner

    return {"session_id": session_id, "status": "Learning session created"}


@app.get("/health")
async def health_check():
    """Health check endpoint for system status."""
    return {
        "status": "healthy",
        "app": "EduVision Medical Learning Platform",
        "active_sessions": len(LEARNER_PROFILES),
        "features": [
            "PDF extraction",
            "AI summarization",
            "Quiz generation",
            "Progress tracking",
            "Spaced repetition",
            "Analytics",
        ],
    }
