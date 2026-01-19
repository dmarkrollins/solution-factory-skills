#!/usr/bin/env python3
"""
Extract key sections from a dependency story plan.
Returns only Success Criteria, Why This Approach, and Dependencies sections.
"""

import json
import sys
import argparse
import re
from pathlib import Path


def extract_section(content, section_name):
    """Extract a specific section from markdown content."""
    # Pattern to match section header and capture content until next ## header or end
    pattern = rf'##\s+{re.escape(section_name)}(.*?)(?=^##\s|\Z)'
    match = re.search(pattern, content, re.DOTALL | re.MULTILINE | re.IGNORECASE)

    if match:
        section_content = match.group(1).strip()
        return section_content
    return None


def extract_subsection(content, parent_section, subsection_name):
    """Extract a subsection from within a parent section."""
    # First get the parent section
    parent_pattern = rf'##\s+{re.escape(parent_section)}(.*?)(?=^##\s|\Z)'
    parent_match = re.search(parent_pattern, content, re.DOTALL | re.MULTILINE | re.IGNORECASE)

    if not parent_match:
        return None

    parent_content = parent_match.group(1)

    # Now find the subsection within parent
    # Match ### followed by section name, then capture content until next ### or end
    subsection_pattern = rf'###\s+{re.escape(subsection_name)}(.*?)(?=^###\s|\Z)'
    subsection_match = re.search(subsection_pattern, parent_content, re.DOTALL | re.MULTILINE | re.IGNORECASE)

    if subsection_match:
        return subsection_match.group(1).strip()
    return None


def get_dependency_summary(story_number):
    """Get summary of a dependency story plan."""
    plan_file = Path('.project-work') / 'plans' / f'{story_number}-plan.md'

    if not plan_file.exists():
        return {'error': f'Plan file not found: {plan_file}'}

    with open(plan_file, 'r') as f:
        content = f.read()

    # Extract story title from first heading
    title_match = re.match(r'#\s+Story\s+([\d.]+):\s+(.+)', content, re.MULTILINE)
    title = title_match.group(2).strip() if title_match else 'Unknown'

    summary = {
        'storyNumber': story_number,
        'title': title,
        'successCriteria': None,
        'whyThisApproach': None,
        'dependencies': None
    }

    # Extract Success Criteria section
    success_criteria = extract_section(content, 'Success Criteria')
    if success_criteria:
        summary['successCriteria'] = success_criteria

    # Extract "Why This Approach" subsection from Plan Simplification Review
    why_approach = extract_subsection(content, 'Plan Simplification Review', 'Why This Approach')
    if why_approach:
        summary['whyThisApproach'] = why_approach

    # Extract Dependencies section
    dependencies = extract_section(content, 'Dependencies')
    if dependencies:
        summary['dependencies'] = dependencies

    return summary


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Get dependency story plan summary')
    parser.add_argument('--story', required=True, help='Story number (e.g., 1.01)')

    args = parser.parse_args()
    result = get_dependency_summary(args.story)

    print(json.dumps(result, indent=2))
    sys.exit(0 if 'error' not in result else 1)
