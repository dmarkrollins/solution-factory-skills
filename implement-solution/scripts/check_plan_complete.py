#!/usr/bin/env python3
"""
Check if all success criteria in a story plan are marked complete.
Returns JSON with completion status and list of incomplete items.
"""

import json
import sys
import argparse
import re
from pathlib import Path


def check_plan_complete(story_number):
    """Check if all success criteria checkboxes are marked complete."""
    plan_file = Path('.project-work') / 'plans' / f'{story_number}-plan.md'

    if not plan_file.exists():
        return {'error': f'Plan file not found: {plan_file}'}

    with open(plan_file, 'r') as f:
        content = f.read()

    # Find Success Criteria section
    criteria_match = re.search(r'##\s+Success Criteria\s*\n(.*?)(?=\n##|\Z)', content, re.DOTALL)

    if not criteria_match:
        return {'error': 'Success Criteria section not found in plan'}

    criteria_section = criteria_match.group(1)

    # Find all checkboxes
    checked_items = re.findall(r'-\s+\[x\]\s+(.+)', criteria_section, re.IGNORECASE)
    unchecked_items = re.findall(r'-\s+\[\s\]\s+(.+)', criteria_section)

    if unchecked_items:
        return {
            'complete': False,
            'incomplete': unchecked_items,
            'checked': len(checked_items),
            'total': len(checked_items) + len(unchecked_items)
        }

    return {
        'complete': True,
        'total': len(checked_items)
    }


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Check plan completion status')
    parser.add_argument('--story', required=True, help='Story number (e.g., 1.01)')

    args = parser.parse_args()
    result = check_plan_complete(args.story)

    print(json.dumps(result, indent=2))
    sys.exit(0 if result.get('complete', False) else 1)
