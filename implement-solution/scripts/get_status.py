#!/usr/bin/env python3
"""
Generate a status report of project progress.
Shows completed/remaining stories for current phase.
"""

import json
import sys
import re
from pathlib import Path
from datetime import datetime


def get_status():
    """Generate status report."""
    project_work = Path('.project-work')
    progress_file = project_work / 'implementation-progress.json'

    if not progress_file.exists():
        return {'error': 'implementation-progress.json not found'}

    with open(progress_file, 'r') as f:
        progress = json.load(f)

    current_phase = progress.get('currentPhase', 1)
    completed_stories = progress.get('completedStories', [])
    current_story = progress.get('currentStory')

    # Read stories file to count total
    stories_file = project_work / f'phase-{current_phase}-stories.md'
    if not stories_file.exists():
        return {'error': f'phase-{current_phase}-stories.md not found'}

    with open(stories_file, 'r') as f:
        content = f.read()

    # Count stories by finding story headers
    story_headers = re.findall(r'##\s+Story\s+[\d.]+:', content)
    total_stories = len(story_headers)
    completed_count = len(completed_stories)
    remaining_count = total_stories - completed_count

    # Handle current story
    current_info = None
    if current_story and not current_story.get('completed_at'):
        started_at = datetime.fromisoformat(current_story['started_at'].replace('Z', '+00:00'))
        now = datetime.utcnow().replace(tzinfo=started_at.tzinfo)
        elapsed = now - started_at
        hours = int(elapsed.total_seconds() / 3600)
        minutes = int((elapsed.total_seconds() % 3600) / 60)

        current_info = {
            'storyNumber': current_story['storyNumber'],
            'elapsedHours': hours,
            'elapsedMinutes': minutes,
            'testFiles': current_story.get('test_files', []),
            'blockers': current_story.get('blockers', [])
        }

    return {
        'currentPhase': current_phase,
        'totalStories': total_stories,
        'completed': completed_count,
        'remaining': remaining_count,
        'currentStory': current_info
    }


if __name__ == '__main__':
    result = get_status()
    print(json.dumps(result, indent=2))
