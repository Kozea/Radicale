#!/usr/bin/env python3
"""Script to create test privacy settings for VCF test cases."""

import os
import sys
from pathlib import Path

from generate_vcf_data import generate_test_cards

from radicale.config import load
from radicale.privacy.core import PrivacyCore

# Add the project root to the Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))


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
    """Create privacy settings for all test cases."""
    db_path = os.path.join(os.path.expanduser("~/.local/share/radicale"), "privacy.db")

    # Create test-specific configuration
    configuration = load()
    configuration.update({
        "privacy": {
            "database_path": db_path
        },
        "storage": {
            "type": "multifilesystem",
            "filesystem_folder": os.path.expanduser("~/.var/lib/radicale/collections")
        }
    }, "test")

    # Print the database location
    print(f"Using privacy database at: {db_path}\n")

    # Initialize the privacy core
    privacy_core = PrivacyCore(configuration)

    # Get test cards
    test_cards = generate_test_cards()

    # Create settings for each test case
    for card_data in test_cards:
        email = card_data['email'] if isinstance(card_data['email'], str) else card_data['email'][0]
        settings = generate_privacy_settings(card_data)

        try:
            # First check if settings exist
            success, result = privacy_core.get_settings(email)

            if success:
                # Settings exist, update them
                print(f"Settings for {email} already exist, updating...")
                success, result = privacy_core.update_settings(email, settings)
                if not success:
                    print(f"Error updating privacy settings: {result}")
                    continue
                print("Settings updated successfully")
            else:
                # Settings don't exist, create them
                print(f"Creating new settings for {email}...")
                success, result = privacy_core.create_settings(email, settings)
                if not success:
                    print(f"Error creating privacy settings: {result}")
                    continue
                print("Settings created successfully")

            # Get the settings to verify
            success, result = privacy_core.get_settings(email)
            if success:
                print(f"\nCurrent settings for {email}:")
                print(f"  Photo allowed: {result['disallow_photo']}")
                print(f"  Gender allowed: {result['disallow_gender']}")
                print(f"  Birthday allowed: {result['disallow_birthday']}")
                print(f"  Address allowed: {result['disallow_address']}")
                print(f"  Company allowed: {result['disallow_company']}")
                print(f"  Title allowed: {result['disallow_title']}")
                print("\n")
            else:
                print(f"Settings were created/updated for {email} but could not verify them\n")

        except Exception as e:
            print(f"Error processing {email}: {e}\n")


if __name__ == "__main__":
    main()
