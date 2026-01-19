#!/usr/bin/env python3
"""
Find the next uncompleted story from the current phase.
Outputs JSON with story details or empty if no stories remain.
"""

import json
import sys
import re
from pathlib import Path


def parse_story(story_text):
    """Parse a story block from markdown into structured data."""
    lines = story_text.strip().split('\n')

    # Extract story number and title from header (## Story 1.01: Title)
    header_match = re.match(r'##\s+Story\s+([\d.]+):\s+(.+)', lines[0])
    if not header_match:
        return None

    story_number = header_match.group(1)
    title = header_match.group(2).strip()

    # Extract fields
    complexity = None
    description = None
    dependencies = []
    acceptance_criteria = []

    current_section = None
    for line in lines[1:]:
        line = line.strip()

        if line.startswith('**Complexity**:'):
            complexity_match = re.search(r'(\d+)/10', line)
            if complexity_match:
                complexity = int(complexity_match.group(1))
        elif line.startswith('**Description**:'):
            description = line.replace('**Description**:', '').strip()
        elif line.startswith('**Dependencies**:'):
            deps_text = line.replace('**Dependencies**:', '').strip()
            if deps_text and deps_text.lower() != 'none':
                dependencies = [d.strip() for d in deps_text.split(',')]
        elif line.startswith('**Acceptance Criteria**:'):
            current_section = 'criteria'
        elif current_section == 'criteria' and line.startswith('-'):
            acceptance_criteria.append(line[1:].strip())

    return {
        'storyNumber': story_number,
        'title': title,
        'complexity': complexity,
        'description': description,
        'dependencies': dependencies,
        'acceptanceCriteria': acceptance_criteria
    }


def get_next_story():
    """Find the next uncompleted story from the current phase."""
    project_work = Path('.project-work')

    # Check if .project-work exists
    if not project_work.exists():
        return {'error': '.project-work directory not found'}

    # Read progress file
    progress_file = project_work / 'implementation-progress.json'
    if not progress_file.exists():
        return {'error': 'implementation-progress.json not found'}

    with open(progress_file, 'r') as f:
        progress = json.load(f)

    current_phase = progress.get('currentPhase', 1)
    completed_stories = [s['storyNumber'] for s in progress.get('completedStories', [])]
    current_story = progress.get('currentStory')

    # If there's a current story in progress, return it
    if current_story and not current_story.get('completed_at'):
        # Read story details from stories file
        stories_file = project_work / f'phase-{current_phase}-stories.md'
        if not stories_file.exists():
            return {'error': f'phase-{current_phase}-stories.md not found'}

        with open(stories_file, 'r') as f:
            content = f.read()

        # Split by story headers (format: Epic#.Story### e.g., 1.003, 2.024)
        story_blocks = re.split(r'\n(?=## Story \d+\.\d{3}:)', content)
        for block in story_blocks:
            story = parse_story(block)
            if story and story['storyNumber'] == current_story['storyNumber']:
                story['inProgress'] = True
                return story

    # Find next uncompleted story
    stories_file = project_work / f'phase-{current_phase}-stories.md'
    if not stories_file.exists():
        return {'error': f'phase-{current_phase}-stories.md not found'}

    with open(stories_file, 'r') as f:
        content = f.read()

    # Split by story headers (format: Epic#.Story### e.g., 1.003, 2.024)
    story_blocks = re.split(r'\n(?=## Story \d+\.\d{3}:)', content)

    for block in story_blocks:
        story = parse_story(block)
        if story and story['storyNumber'] not in completed_stories:
            story['inProgress'] = False
            return story

    # No uncompleted stories found
    return {'complete': True, 'message': f'All stories in phase {current_phase} are completed'}


if __name__ == '__main__':
    result = get_next_story()
    print(json.dumps(result, indent=2))
