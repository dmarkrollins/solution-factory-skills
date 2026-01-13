#!/usr/bin/env python3
"""
Update implementation-progress.json with story progress.
Supports: start, complete, add-blocker, add-test-file actions.
"""

import json
import sys
import argparse
from pathlib import Path
from datetime import datetime


def update_progress(action, story_number=None, test_files=None, blocker=None, notes=None):
    """Update progress file based on action."""
    project_work = Path('.project-work')
    progress_file = project_work / 'implementation-progress.json'

    # Load existing progress
    if progress_file.exists():
        with open(progress_file, 'r') as f:
            progress = json.load(f)
    else:
        progress = {
            'currentPhase': 1,
            'preferences': {},
            'currentStory': None,
            'completedStories': []
        }

    if action == 'start':
        if not story_number:
            return {'success': False, 'error': 'story_number required for start action'}

        progress['currentStory'] = {
            'storyNumber': story_number,
            'started_at': datetime.utcnow().isoformat() + 'Z',
            'completed_at': None,
            'duration_minutes': 0,
            'test_files': [],
            'blockers': [],
            'notes': ''
        }

    elif action == 'complete':
        if not progress.get('currentStory'):
            return {'success': False, 'error': 'No current story to complete'}

        current = progress['currentStory']
        started_at = datetime.fromisoformat(current['started_at'].replace('Z', '+00:00'))
        completed_at = datetime.utcnow().replace(tzinfo=started_at.tzinfo)
        duration_minutes = int((completed_at - started_at).total_seconds() / 60)

        # Update current story
        current['completed_at'] = completed_at.isoformat() + 'Z'
        current['duration_minutes'] = duration_minutes

        # Add test files if provided
        if test_files:
            current['test_files'].extend(test_files)

        # Set notes if provided
        if notes:
            current['notes'] = notes

        # Move to completed stories
        progress['completedStories'].append(current)
        progress['currentStory'] = None

    elif action == 'add-blocker':
        if not progress.get('currentStory'):
            return {'success': False, 'error': 'No current story to add blocker to'}
        if not blocker:
            return {'success': False, 'error': 'blocker text required'}

        progress['currentStory']['blockers'].append(blocker)

    elif action == 'add-test-file':
        if not progress.get('currentStory'):
            return {'success': False, 'error': 'No current story to add test file to'}
        if not test_files:
            return {'success': False, 'error': 'test_files required'}

        progress['currentStory']['test_files'].extend(test_files)

    elif action == 'set-preference':
        # Used to store execution/testing strategy preferences
        if not story_number or not test_files:  # reusing params for key/value
            return {'success': False, 'error': 'preference key and value required'}

        progress['preferences'][story_number] = test_files[0]  # key=story_number, value=test_files[0]

    else:
        return {'success': False, 'error': f'Unknown action: {action}'}

    # Write updated progress
    with open(progress_file, 'w') as f:
        json.dump(progress, f, indent=2)

    return {'success': True, 'message': f'Progress updated: {action}'}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Update implementation progress')
    parser.add_argument('--action', required=True,
                        choices=['start', 'complete', 'add-blocker', 'add-test-file', 'set-preference'],
                        help='Action to perform')
    parser.add_argument('--story', help='Story number')
    parser.add_argument('--test-files', nargs='*', help='Test file paths')
    parser.add_argument('--blocker', help='Blocker description')
    parser.add_argument('--notes', help='Story completion notes')

    args = parser.parse_args()

    result = update_progress(
        action=args.action,
        story_number=args.story,
        test_files=args.test_files,
        blocker=args.blocker,
        notes=args.notes
    )

    print(json.dumps(result, indent=2))
    sys.exit(0 if result.get('success') else 1)
