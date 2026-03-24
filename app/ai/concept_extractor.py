from typing import Dict, List


def extract_concepts(summary: str) -> List[Dict]:
    """Extract concept cards from markdown headings and bullets."""
    concepts: List[Dict] = []
    current: Dict | None = None

    for raw_line in summary.splitlines():
        line = raw_line.strip()
        if not line:
            continue

        if line.startswith("### "):
            title = line[4:].strip()
            current = {
                "id": title.lower().replace(" ", "-"),
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

    for index, concept in enumerate(concepts):
        bullets = concept.get("bullets", [])
        concept["summary"] = bullets[0] if bullets else f"Key idea from {concept['name']}."
        concept["importance"] = max(1, min(5, len(bullets) or (len(concepts) - index)))
        concept["type"] = "foundation" if index == 0 else ("bridge" if index < 3 else "detail")

    return concepts[:10]
