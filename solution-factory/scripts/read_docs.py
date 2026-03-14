#!/usr/bin/env python3
"""
Extract structured content from .solution-factory/docs/ folder.
Produces token-efficient JSON summaries of documentation.
"""

import json
import sys
import re
from pathlib import Path


def extract_sentences(text, count=3):
    """Extract first N sentences from text."""
    sentences = re.split(r'(?<=[.!?])\s+', text.strip())
    return ' '.join(sentences[:count])


def extract_markdown(file_path):
    """Extract key content from a markdown file."""
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()

    extracted = {
        'filename': file_path.name,
        'sections': []
    }

    lines = content.split('\n')
    current_section = None
    section_text = []
    in_code_block = False

    for line in lines:
        if line.strip().startswith('```'):
            in_code_block = not in_code_block
            continue

        if in_code_block:
            continue

        heading_match = re.match(r'^(#{1,3})\s+(.+)', line)
        if heading_match:
            if current_section and section_text:
                current_section['text'] = extract_sentences(' '.join(section_text), 3)
                extracted['sections'].append(current_section)

            current_section = {
                'level': len(heading_match.group(1)),
                'title': heading_match.group(2).strip(),
                'text': '',
                'lists': []
            }
            section_text = []
            continue

        list_match = re.match(r'^\s*[-*+]\s+(.+)', line)
        if list_match and current_section:
            current_section['lists'].append(list_match.group(1).strip())
            continue

        if line.strip() and current_section:
            section_text.append(line.strip())

    if current_section:
        if section_text:
            current_section['text'] = extract_sentences(' '.join(section_text), 3)
        extracted['sections'].append(current_section)

    return extracted


def read_docs(root="."):
    """Extract content from all docs in .solution-factory/docs/."""
    docs_dir = Path(root) / ".solution-factory" / "docs"

    if not docs_dir.exists():
        return {'error': f'Docs directory not found: {docs_dir}'}

    md_files = sorted(docs_dir.glob('*.md'))
    if not md_files:
        return {'error': 'No markdown files found in docs/'}

    result = {
        'source': str(docs_dir),
        'files': []
    }

    for md_file in md_files:
        try:
            extracted = extract_markdown(md_file)
            result['files'].append(extracted)
        except Exception as e:
            result['files'].append({'filename': md_file.name, 'error': str(e)})

    return result


if __name__ == '__main__':
    root = sys.argv[1] if len(sys.argv) > 1 else "."
    result = read_docs(root)
    print(json.dumps(result, indent=2))
