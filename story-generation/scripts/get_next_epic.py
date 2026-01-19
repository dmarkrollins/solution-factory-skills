#!/usr/bin/env python3
"""
Determine the next epic number to generate.
Reads implementation-progress.json and returns next epic to work on.
"""

import json
import sys
from pathlib import Path


def get_next_epic():
    """Determine next epic number to generate."""
    project_work = Path('.project-work')
    progress_file = project_work / 'implementation-progress.json'

    if not progress_file.exists():
        return {'error': 'implementation-progress.json not found'}

    with open(progress_file, 'r') as f:
        progress = json.load(f)

    current_phase = progress.get('currentPhase', 1)

    # Check if nextEpicToGenerate is explicitly set
    next_epic_to_generate = progress.get('nextEpicToGenerate')
    if next_epic_to_generate is not None:
        return {
            'nextEpic': next_epic_to_generate,
            'currentPhase': current_phase,
            'lastCompletedEpic': next_epic_to_generate - 1 if next_epic_to_generate > 1 else None
        }

    # Otherwise, calculate from completed stories
    completed_stories = progress.get('completedStories', [])

    if not completed_stories:
        # No stories completed yet, start with epic 1
        return {
            'nextEpic': 1,
            'currentPhase': current_phase,
            'lastCompletedEpic': None
        }

    # Find highest epic number from completed stories
    epic_numbers = []
    for story in completed_stories:
        story_number = story.get('storyNumber', '')
        try:
            epic_num = int(story_number.split('.')[0])
            epic_numbers.append(epic_num)
        except (ValueError, IndexError):
            continue

    if not epic_numbers:
        # No valid epic numbers found, default to 1
        return {
            'nextEpic': 1,
            'currentPhase': current_phase,
            'lastCompletedEpic': None
        }

    last_completed_epic = max(epic_numbers)
    next_epic = last_completed_epic + 1

    return {
        'nextEpic': next_epic,
        'currentPhase': current_phase,
        'lastCompletedEpic': last_completed_epic
    }


if __name__ == '__main__':
    result = get_next_epic()
    print(json.dumps(result, indent=2))
    sys.exit(0 if 'error' not in result else 1)
