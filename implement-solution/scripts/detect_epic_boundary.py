#!/usr/bin/env python3
"""
Detect if a completed story is the last story in its epic.
Returns epic boundary information.
"""

import json
import sys
import argparse
import re
from pathlib import Path


def detect_epic_boundary(story_number):
    """Check if story is the last in its epic."""
    # Parse epic number from story (e.g., "5.015" -> epic 5)
    try:
        epic_num = int(story_number.split('.')[0])
        story_parts = story_number.split('.')
        if len(story_parts) != 2:
            return {'error': f'Invalid story number format: {story_number}. Expected Epic#.Story###'}
    except (ValueError, IndexError):
        return {'error': f'Invalid story number: {story_number}'}

    # Read implementation-progress.json to get current phase
    project_work = Path('.project-work')
    progress_file = project_work / 'implementation-progress.json'

    if not progress_file.exists():
        return {'error': 'implementation-progress.json not found'}

    with open(progress_file, 'r') as f:
        progress = json.load(f)

    current_phase = progress.get('currentPhase', 1)

    # Read phase stories file
    stories_file = project_work / f'phase-{current_phase}-stories.md'
    if not stories_file.exists():
        return {'error': f'phase-{current_phase}-stories.md not found'}

    with open(stories_file, 'r') as f:
        content = f.read()

    # Find all stories for this epic (format: ## Story 5.001: Title)
    pattern = rf'##\s+Story\s+{epic_num}\.\d{{3}}:'
    epic_story_headers = re.findall(pattern, content)

    if not epic_story_headers:
        return {'error': f'No stories found for epic {epic_num}'}

    # Extract story numbers for this epic
    story_numbers = []
    for header in epic_story_headers:
        match = re.search(rf'{epic_num}\.(\d{{3}})', header)
        if match:
            story_numbers.append(f'{epic_num}.{match.group(1)}')

    # Sort story numbers to find the last one
    story_numbers.sort()

    total_stories_in_epic = len(story_numbers)
    last_story_number = story_numbers[-1] if story_numbers else None
    is_last_in_epic = (story_number == last_story_number)

    return {
        'isLastInEpic': is_last_in_epic,
        'epicNumber': epic_num,
        'totalStoriesInEpic': total_stories_in_epic,
        'lastStoryNumber': last_story_number,
        'allStoriesInEpic': story_numbers
    }


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Detect epic boundary for a story')
    parser.add_argument('--story', required=True, help='Story number (e.g., 5.015)')

    args = parser.parse_args()
    result = detect_epic_boundary(args.story)

    print(json.dumps(result, indent=2))
    sys.exit(0 if 'error' not in result else 1)
