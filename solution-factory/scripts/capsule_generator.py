#!/usr/bin/env python3
"""
Auto-generate context capsules by clustering ADRs and constraints by topic.
Capsules are token-efficient summaries that aggregate related decisions/constraints.

Topics are inferred from file content keywords. Each capsule summarizes
the essence of its related decisions and constraints.
"""

import json
import sys
import argparse
import re
from pathlib import Path
from collections import defaultdict

# Topic keywords for clustering
TOPIC_KEYWORDS = {
    "observability": ["logging", "monitoring", "tracing", "metrics", "observability", "alerting", "dashboard"],
    "data-persistence": ["database", "storage", "migration", "schema", "query", "orm", "persistence", "data model"],
    "authentication": ["auth", "authentication", "authorization", "jwt", "token", "session", "identity", "oauth"],
    "api-design": ["api", "endpoint", "rest", "graphql", "route", "request", "response", "http"],
    "runtime-architecture": ["runtime", "deployment", "infrastructure", "serverless", "container", "lambda", "architecture"],
    "testing-strategy": ["test", "testing", "coverage", "unit test", "integration", "e2e", "validation"],
    "security": ["security", "encryption", "vulnerability", "cors", "csrf", "injection", "sanitize"],
    "ux-patterns": ["ui", "ux", "component", "layout", "design system", "wireframe", "responsive", "accessibility"],
    "error-handling": ["error", "exception", "fallback", "retry", "timeout", "circuit breaker", "graceful"],
    "performance": ["performance", "cache", "optimization", "latency", "throughput", "scaling", "concurrent"],
}


def classify_topic(content):
    """Classify content into topics based on keyword matching."""
    content_lower = content.lower()
    scores = {}
    for topic, keywords in TOPIC_KEYWORDS.items():
        score = sum(1 for kw in keywords if kw in content_lower)
        if score > 0:
            scores[topic] = score
    return scores


def generate_capsules(root="."):
    """Scan all ADRs and constraints, cluster by topic, generate capsules."""
    base = Path(root) / ".solution-factory"
    decisions_dir = base / "decisions"
    constraints_dir = base / "constraints"
    capsules_dir = base / "context" / "capsules"
    capsules_dir.mkdir(parents=True, exist_ok=True)

    # Collect all documents with their topics
    topic_docs = defaultdict(list)

    # Scan decisions
    if decisions_dir.exists():
        for f in sorted(decisions_dir.glob("*.md")):
            content = f.read_text()
            title_match = re.search(r'^#\s+(.+)', content, re.MULTILINE)
            title = title_match.group(1) if title_match else f.stem

            scores = classify_topic(content)
            for topic, score in scores.items():
                topic_docs[topic].append({
                    "type": "decision",
                    "id": f.stem,
                    "title": title,
                    "content": content,
                    "score": score
                })

    # Scan constraints
    if constraints_dir.exists():
        for f in sorted(constraints_dir.glob("*.md")):
            content = f.read_text()
            title_match = re.search(r'^#\s+(.+)', content, re.MULTILINE)
            title = title_match.group(1) if title_match else f.stem

            scores = classify_topic(content)
            for topic, score in scores.items():
                topic_docs[topic].append({
                    "type": "constraint",
                    "id": f.stem,
                    "title": title,
                    "content": content,
                    "score": score
                })

    # Generate capsules for topics with 2+ documents
    generated = []
    for topic, docs in topic_docs.items():
        if len(docs) < 1:
            continue

        # Sort by relevance score within topic
        docs.sort(key=lambda d: d["score"], reverse=True)

        # Build capsule content
        decisions = [d for d in docs if d["type"] == "decision"]
        constraints = [d for d in docs if d["type"] == "constraint"]

        capsule_content = f"""# {topic.replace('-', ' ').title()} — Context Capsule

> Auto-generated summary of {len(docs)} related decisions and constraints.

"""
        if decisions:
            capsule_content += "## Key Decisions\n\n"
            for d in decisions:
                # Extract first meaningful paragraph after title
                lines = d["content"].split("\n")
                summary_lines = []
                capture = False
                for line in lines:
                    if line.startswith("## "):
                        if capture:
                            break
                        capture = True
                        continue
                    if capture and line.strip():
                        summary_lines.append(line.strip())
                        if len(summary_lines) >= 2:
                            break

                summary = " ".join(summary_lines) if summary_lines else d["title"]
                capsule_content += f"- **{d['id']}**: {summary}\n"
            capsule_content += "\n"

        if constraints:
            capsule_content += "## Constraints\n\n"
            for c in constraints:
                lines = c["content"].split("\n")
                summary_lines = []
                capture = False
                for line in lines:
                    if line.startswith("## "):
                        if capture:
                            break
                        capture = True
                        continue
                    if capture and line.strip():
                        summary_lines.append(line.strip())
                        if len(summary_lines) >= 2:
                            break

                summary = " ".join(summary_lines) if summary_lines else c["title"]
                capsule_content += f"- **{c['id']}**: {summary}\n"
            capsule_content += "\n"

        capsule_content += f"## References\n\n"
        for d in docs:
            capsule_content += f"- `{d['id']}.md` ({d['type']})\n"

        capsule_path = capsules_dir / f"{topic}.md"
        capsule_path.write_text(capsule_content)
        generated.append({
            "topic": topic,
            "path": str(capsule_path),
            "decisions": len(decisions),
            "constraints": len(constraints)
        })

    return {
        "success": True,
        "capsules_generated": len(generated),
        "capsules": generated,
        "topics_found": list(topic_docs.keys())
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate context capsules")
    parser.add_argument("--root", default=".", help="Project root")

    args = parser.parse_args()
    result = generate_capsules(args.root)

    print(json.dumps(result, indent=2))
    sys.exit(0 if result.get("success") else 1)
