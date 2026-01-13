#!/usr/bin/env python3
"""
Update a success criteria checkbox in a story plan to mark it complete.
"""

import json
import sys
import argparse
import re
from pathlib import Path


def update_plan_checkbox(story_number, criterion_text):
    """Mark a specific success criterion as complete in the plan file."""
    plan_file = Path('.project-work') / 'plans' / f'{story_number}-plan.md'

    if not plan_file.exists():
        return {'success': False, 'error': f'Plan file not found: {plan_file}'}

    with open(plan_file, 'r') as f:
        content = f.read()

    # Escape special regex characters in criterion text
    escaped_criterion = re.escape(criterion_text)

    # Pattern to find unchecked checkbox with this criterion
    pattern = r'(-\s+\[)\s(\]\s+' + escaped_criterion + r')'

    # Check if this criterion exists
    if not re.search(pattern, content, re.IGNORECASE):
        # Check if it's already checked
        checked_pattern = r'-\s+\[x\]\s+' + escaped_criterion
        if re.search(checked_pattern, content, re.IGNORECASE):
            return {'success': True, 'message': 'Criterion already marked complete', 'alreadyChecked': True}
        else:
            return {'success': False, 'error': f'Criterion not found: {criterion_text}'}

    # Replace [ ] with [x]
    updated_content = re.sub(pattern, r'\1x\2', content, flags=re.IGNORECASE)

    # Write back to file
    with open(plan_file, 'w') as f:
        f.write(updated_content)

    return {'success': True, 'message': 'Checkbox updated to complete'}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Update plan checkbox')
    parser.add_argument('--story', required=True, help='Story number (e.g., 1.01)')
    parser.add_argument('--criterion', required=True, help='Criterion text to mark complete')

    args = parser.parse_args()
    result = update_plan_checkbox(args.story, args.criterion)

    print(json.dumps(result, indent=2))
    sys.exit(0 if result.get('success', False) else 1)
