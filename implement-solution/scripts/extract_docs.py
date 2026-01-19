#!/usr/bin/env python3
"""
Extract structured content from project documentation.
Reduces token usage while preserving important context.
"""

import json
import sys
import re
from pathlib import Path


def extract_sentences(text, count=3):
    """Extract first N sentences from text."""
    # Split on sentence boundaries (., !, ?)
    sentences = re.split(r'(?<=[.!?])\s+', text.strip())
    return ' '.join(sentences[:count])


def extract_markdown_content(file_path):
    """Extract key content from a markdown file."""
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()

    extracted = {
        'filename': file_path.name,
        'sections': []
    }

    # Split content into lines
    lines = content.split('\n')

    current_section = None
    section_text = []
    in_code_block = False
    in_list = False
    code_block_lines = []
    list_items = []

    for line in lines:
        # Track code blocks
        if line.strip().startswith('```'):
            if not in_code_block:
                in_code_block = True
                code_block_lines = [line]
            else:
                in_code_block = False
                code_block_lines.append(line)
                # Save code block to current section
                if current_section:
                    if 'codeBlocks' not in current_section:
                        current_section['codeBlocks'] = []
                    current_section['codeBlocks'].append('\n'.join(code_block_lines))
                code_block_lines = []
            continue

        if in_code_block:
            code_block_lines.append(line)
            continue

        # Check for headings
        heading_match = re.match(r'^(#{1,3})\s+(.+)', line)
        if heading_match:
            # Save previous section
            if current_section:
                # Extract first 2-3 sentences from accumulated text
                if section_text:
                    text = ' '.join(section_text)
                    current_section['text'] = extract_sentences(text, 3)
                extracted['sections'].append(current_section)

            # Start new section
            level = len(heading_match.group(1))
            title = heading_match.group(2).strip()
            current_section = {
                'level': level,
                'title': title,
                'text': '',
                'lists': [],
                'codeBlocks': [],
                'tables': []
            }
            section_text = []
            in_list = False
            list_items = []
            continue

        # Check for list items (bullets or numbered)
        list_match = re.match(r'^(\s*)([-*+]|\d+\.)\s+(.+)', line)
        if list_match:
            if not in_list:
                in_list = True
                list_items = []
            list_items.append(list_match.group(3).strip())
            continue

        # If we were in a list and hit non-list content, save the list
        if in_list and not list_match:
            if current_section and list_items:
                current_section['lists'].append(list_items)
            in_list = False
            list_items = []

        # Check for table rows
        if '|' in line and line.strip():
            if current_section:
                if not current_section['tables']:
                    current_section['tables'] = []
                # Add table row
                current_section['tables'].append(line.strip())
            continue

        # Regular text - accumulate for sentence extraction
        if line.strip() and current_section:
            section_text.append(line.strip())

    # Save final section
    if current_section:
        if section_text:
            text = ' '.join(section_text)
            current_section['text'] = extract_sentences(text, 3)
        if in_list and list_items:
            current_section['lists'].append(list_items)
        extracted['sections'].append(current_section)

    return extracted


def extract_docs(docs_path='docs'):
    """Extract content from all markdown files in docs directory."""
    docs_dir = Path(docs_path)

    if not docs_dir.exists():
        return {'error': f'Documentation directory not found: {docs_path}'}

    # Find all .md files in docs root (not subdirectories)
    md_files = sorted(docs_dir.glob('*.md'))

    if not md_files:
        return {'error': f'No markdown files found in {docs_path}'}

    result = {
        'source': docs_path,
        'files': []
    }

    for md_file in md_files:
        try:
            extracted = extract_markdown_content(md_file)
            result['files'].append(extracted)
        except Exception as e:
            result['files'].append({
                'filename': md_file.name,
                'error': str(e)
            })

    return result


if __name__ == '__main__':
    # Allow custom docs path as argument
    docs_path = sys.argv[1] if len(sys.argv) > 1 else 'docs'

    result = extract_docs(docs_path)
    print(json.dumps(result, indent=2))
