#!/usr/bin/env python3
"""Script to create test privacy settings for VCF test cases."""

import json
import os
import sys
from pathlib import Path

from generate_vcf_data import generate_test_cards

from radicale.config import load
from radicale.privacy.api import PrivacyAPI

# Add the project root to the Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))


def generate_privacy_settings(card_data: dict) -> dict:
    """Generate privacy settings based on the card data."""
    # Default settings - start with everything allowed
    settings = {
        "disallow_name": False,
        "disallow_email": False,
        "disallow_phone": False,
        "disallow_company": False,
        "disallow_title": False,
        "disallow_photo": False,
        "disallow_birthday": False,
        "disallow_address": False
    }

    # Test case specific settings
    if card_data['uid'] == 'test1':
        # Basic contact - allow only basic info
        settings.update({
            "disallow_company": True,
            "disallow_title": True,
            "disallow_photo": True,
            "disallow_birthday": True,
            "disallow_address": True
        })
    elif card_data['uid'] == 'test2':
        # Work contact - allow company and title
        settings.update({
            "disallow_photo": True,
            "disallow_birthday": True,
            "disallow_address": True
        })
    elif card_data['uid'] == 'test3':
        # Personal contact - allow birthday and photo
        settings.update({
            "disallow_company": True,
            "disallow_title": True,
            "disallow_address": True
        })
    elif card_data['uid'] == 'test4':
        # Photo contact - allow only photo and basic info
        settings.update({
            "disallow_company": True,
            "disallow_title": True,
            "disallow_address": True
        })
    elif card_data['uid'] == 'test5':
        # Address contact - allow address and basic info
        settings.update({
            "disallow_photo": True,
            "disallow_birthday": True
        })
    elif card_data['uid'] == 'test6':
        # Multiple emails - allow only email and basic info
        settings.update({
            "disallow_phone": True,
            "disallow_company": True,
            "disallow_title": True,
            "disallow_photo": True,
            "disallow_birthday": True,
            "disallow_address": True
        })
    elif card_data['uid'] == 'test7':
        # Multiple phones - allow only phone and basic info
        settings.update({
            "disallow_company": True,
            "disallow_title": True,
            "disallow_photo": True,
            "disallow_birthday": True,
            "disallow_address": True
        })
    elif card_data['uid'] == 'test8':
        # Minimal contact - allow only name and email
        settings.update({
            "disallow_phone": True,
            "disallow_company": True,
            "disallow_title": True,
            "disallow_photo": True,
            "disallow_birthday": True,
            "disallow_address": True
        })
    elif card_data['uid'] == 'test9':
        # Full contact - allow everything
        pass  # Keep all settings as True

    return settings


def main():
    """Create privacy settings for all test cases."""
    # Load configuration
    config = load()

    # Print the database location
    db_path = os.path.expanduser(config.get("privacy", "database_path"))
    print(f"Using privacy database at: {db_path}\n")

    # Initialize the privacy API
    privacy_api = PrivacyAPI(config)

    # Get test cards
    test_cards = generate_test_cards()

    # Create settings for each test case
    for card_data in test_cards:
        email = card_data['email'] if isinstance(card_data['email'], str) else card_data['email'][0]
        settings = generate_privacy_settings(card_data)

        try:
            # First check if settings exist
            status, headers, body = privacy_api.get_settings(email)

            if status == 200:
                # Settings exist, update them
                print(f"Settings for {email} already exist, updating...")
                status, headers, body = privacy_api.update_settings(email, settings)
                if status != 200:
                    error = json.loads(body)
                    print(f"Error updating privacy settings: {error.get('error', 'Unknown error')}")
                    continue
                print("Settings updated successfully")
            else:
                # Settings don't exist, create them
                print(f"Creating new settings for {email}...")
                status, headers, body = privacy_api.create_settings(email, settings)
                if status != 201:
                    error = json.loads(body)
                    print(f"Error creating privacy settings: {error.get('error', 'Unknown error')}")
                    continue
                print("Settings created successfully")

            # Get the settings to verify
            status, headers, body = privacy_api.get_settings(email)
            if status == 200:
                current_settings = json.loads(body)
                print(f"\nCurrent settings for {email}:")
                print(f"  Name allowed: {current_settings['disallow_name']}")
                print(f"  Email allowed: {current_settings['disallow_email']}")
                print(f"  Phone allowed: {current_settings['disallow_phone']}")
                print(f"  Company allowed: {current_settings['disallow_company']}")
                print(f"  Title allowed: {current_settings['disallow_title']}")
                print(f"  Photo allowed: {current_settings['disallow_photo']}")
                print(f"  Birthday allowed: {current_settings['disallow_birthday']}")
                print(f"  Address allowed: {current_settings['disallow_address']}\n")
            else:
                print(f"Settings were created/updated for {email} but could not verify them\n")

        except Exception as e:
            print(f"Error processing {email}: {e}\n")


if __name__ == "__main__":
    main()
