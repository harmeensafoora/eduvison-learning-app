from typing import Dict, List

from ..ai_utils import generate_detailed_text


def generate_explanations(summary: str, full_text: str, concept: Dict, modes: List[str]) -> Dict:
    """Generate explanation variants for a concept using existing detail generation."""
    concept_name = concept.get("name") or "Concept"
    base_text = generate_detailed_text(summary, full_text)
    concept_summary = concept.get("summary") or f"Key idea from {concept_name}."

    explanations = {}
    if "visual" in modes:
        explanations["visual"] = f"{concept_name}: visualize this as a system map. {concept_summary}"
    if "analogy" in modes:
        explanations["analogy"] = f"{concept_name}: think of it as a working model where each part has a clear role. {concept_summary}"
    if "technical" in modes:
        explanations["technical"] = base_text

    return explanations
