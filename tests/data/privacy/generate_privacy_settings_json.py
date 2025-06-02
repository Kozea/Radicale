#!/usr/bin/env python3
"""Script to create individual JSON files for privacy settings of test users."""

import json
from pathlib import Path

from generate_vcf_data import generate_test_cards


def generate_privacy_settings(card_data: dict) -> dict:
    """Generate privacy settings based on the card data."""
    # Default settings - start with everything allowed
    settings = {
        "disallow_photo": False,
        "disallow_gender": False,
        "disallow_birthday": False,
        "disallow_address": False,
        "disallow_title": False,
        "disallow_company": False,
    }

    # Test case specific settings
    if card_data['uid'] == 'test1':
        # Basic contact - allow only basic info
        settings.update({
            "disallow_photo": True,
            "disallow_gender": True,
            "disallow_birthday": True,
            "disallow_address": True,
            "disallow_company": True,
            "disallow_title": True,
        })
    elif card_data['uid'] == 'test2':
        # Work contact - allow company and title
        settings.update({
            "disallow_photo": True,
            "disallow_gender": True,
            "disallow_birthday": True,
            "disallow_address": True,
        })
    elif card_data['uid'] == 'test3':
        # Personal contact - allow birthday and photo
        settings.update({
            "disallow_address": True,
            "disallow_gender": True,
            "disallow_company": True,
            "disallow_title": True,
        })
    elif card_data['uid'] == 'test4':
        # Photo contact - allow only photo and basic info
        settings.update({
            "disallow_gender": True,
            "disallow_address": True,
            "disallow_company": True,
            "disallow_title": True,
        })
    elif card_data['uid'] == 'test5':
        # Address contact - allow address and basic info
        settings.update({
            "disallow_photo": True,
            "disallow_gender": True,
            "disallow_birthday": True,
        })
    elif card_data['uid'] == 'test6':
        # Multiple emails - allow only basic info
        settings.update({
            "disallow_photo": True,
            "disallow_gender": True,
            "disallow_birthday": True,
            "disallow_address": True,
            "disallow_company": True,
            "disallow_title": True,
        })
    elif card_data['uid'] == 'test7':
        # Multiple phones - allow only basic info
        settings.update({
            "disallow_photo": True,
            "disallow_gender": True,
            "disallow_birthday": True,
            "disallow_address": True,
            "disallow_company": True,
            "disallow_title": True,
        })
    elif card_data['uid'] == 'test8':
        # Minimal contact - allow only name and email
        settings.update({
            "disallow_photo": True,
            "disallow_gender": True,
            "disallow_birthday": True,
            "disallow_address": True,
            "disallow_company": True,
            "disallow_title": True,
        })
    elif card_data['uid'] == 'test9':
        # Full contact - allow everything
        pass  # Keep all settings as False

    return settings


def main():
    """Create individual JSON files for privacy settings of all test cases."""
    # Create settings directory if it doesn't exist
    settings_dir = Path(__file__).parent / "settings"
    settings_dir.mkdir(exist_ok=True)

    # Get test cards
    test_cards = generate_test_cards()

    # Create settings for each test case
    for card_data in test_cards:
        email = card_data['email'] if isinstance(card_data['email'], str) else card_data['email'][0]
        settings = generate_privacy_settings(card_data)

        # Create JSON file for this user's settings
        settings_file = settings_dir / f"{card_data['uid']}_settings.json"

        try:
            with open(settings_file, 'w') as f:
                json.dump(settings, f, indent=4)
            print(f"Created settings file for {email} at {settings_file}")
        except Exception as e:
            print(f"Error creating settings file for {email}: {e}")


if __name__ == "__main__":
    main()
