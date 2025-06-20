#!/usr/bin/env python3
"""Integration tests for VCF upload functionality through the HTTP API."""

import json
import os
from typing import Dict, List, Optional, Tuple

import requests
import vobject

from radicale.privacy.vcard_properties import PRIVACY_TO_VCARD_MAP
from radicale.utils import normalize_phone_e164

# Configuration
API_BASE_URL = "http://localhost:5232"
VCF_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "vcf")
SETTINGS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "settings")


def read_vcf_file(file_path: str) -> str:
    """Read a VCF file and return its contents."""
    with open(file_path, 'r', encoding='utf-8') as f:
        return f.read()


def extract_email_from_vcf(vcf_content: str) -> Optional[str]:
    """Extract email identifier from VCF content.

    Uses vobject to properly parse the VCF and extract email addresses,
    prioritizing preferred email if specified.
    """
    try:
        vcard = vobject.readOne(vcf_content)

        # Check for email_list property
        if hasattr(vcard, "email_list"):
            # Look for preferred email first
            for email in vcard.email_list:
                if hasattr(email, 'params') and email.params.get('PREF') == ['1']:
                    return email.value
            # If no preferred email, return the first one
            return vcard.email_list[0].value if vcard.email_list else None

        return None
    except Exception as e:
        print(f"Warning: Failed to parse vCard: {e}")
        return None


def read_settings(vcf_filename: str) -> Optional[Dict[str, bool]]:
    """Read privacy settings from JSON file for a specific test case.

    Returns None if no settings file exists, allowing server to use defaults.
    Returns the settings dict if a settings file exists.
    """
    settings_filename = f"{os.path.splitext(vcf_filename)[0]}_settings.json"
    settings_path = os.path.join(SETTINGS_DIR, settings_filename)

    try:
        with open(settings_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError) as e:
        print(f"Info: No valid settings file found for {vcf_filename}, server will use defaults: {e}")
        return None


def upload_settings(user: str, settings: Dict[str, bool]) -> Tuple[bool, str]:
    """Upload privacy settings for a user."""
    settings_url = f"{API_BASE_URL}/privacy/settings/{user}"

    try:
        # Check if settings exist
        response_get: requests.Response = requests.get(settings_url, auth=(user, ""))

        if response_get.status_code == 404:
            # Create new settings
            response_post: requests.Response = requests.post(settings_url, json=settings, auth=(user, ""))
            if response_post.status_code != 201:
                return False, f"Failed to create settings: {response_post.text}"
            return True, "Settings created successfully"

        elif response_get.status_code == 200:
            # Update existing settings
            response_put: requests.Response = requests.put(settings_url, json=settings, auth=(user, ""))
            if response_put.status_code != 200:
                return False, f"Failed to update settings: {response_put.text}"
            return True, "Settings updated successfully"

        return False, f"Unexpected status code: {response_get.status_code}"

    except requests.exceptions.RequestException as e:
        return False, f"Request failed: {str(e)}"


def upload_vcf(vcf_content: str, user: str) -> Tuple[bool, str]:
    """Upload a VCF file through the HTTP API."""
    try:
        # Upload the VCF content to the user's contacts collection
        cards_url: str = f"{API_BASE_URL}/{user}/contacts/"
        print(f"\nUploading to URL: {cards_url}")

        # Send the VCF content directly
        response_put: requests.Response = requests.put(
            cards_url,
            data=vcf_content,
            auth=(user, ""),
            headers={"Content-Type": "text/vcard"}
        )

        # Explicit status code handling
        if response_put.status_code == 201:
            return True, "VCF created successfully"
        elif response_put.status_code == 200:
            return True, "VCF updated successfully"
        else:
            return False, f"Failed to upload VCF: HTTP {response_put.status_code}: {response_put.text}"

    except requests.exceptions.RequestException as e:
        return False, f"Request failed: {str(e)}"


def verify_card(user: str) -> Tuple[bool, str]:
    """Verify that the VCF was uploaded and can be retrieved.

    Verifies:
    1. Card can be retrieved from the server
    2. Card has basic required fields (name)
    3. Card has at least one identifier (email or phone) that matches the user
    """
    try:
        cards_url = f"{API_BASE_URL}/privacy/cards/{user}"
        print(f"\nVerifying at URL: {cards_url}")
        response_get: requests.Response = requests.get(cards_url, auth=(user, ""))

        if response_get.status_code != 200:
            return False, f"Failed to retrieve cards: {response_get.text}"

        data = response_get.json()
        if not data or "matches" not in data:
            return False, "No cards data found"

        cards = data["matches"]
        if not cards:
            return False, "No cards found"

        # Verify each card
        print(f"\nFound {len(cards)} cards:")
        for card in cards:
            # Check required fields exist
            if "fields" not in card:
                return False, "Card missing fields data"

            fields = card["fields"]

            # Verify required name field
            if "fn" not in fields:
                return False, "Card missing required fn (formatted name) field"

            # Verify at least one identifier matches the user
            identifiers_match = False

            # Check email identifiers
            if '@' in user and "email" in fields:
                emails = fields["email"]
                if isinstance(emails, str):
                    emails = [emails]
                for email in emails:
                    if email.lower() == user.lower():
                        identifiers_match = True
                        break

            # Check phone identifiers
            elif '@' not in user and "tel" in fields:
                user_phone = user
                try:
                    user_phone = normalize_phone_e164(user)
                except Exception:
                    pass

                phones = fields["tel"]
                if isinstance(phones, str):
                    phones = [phones]
                for phone in phones:
                    phone_value = phone
                    try:
                        phone_value = normalize_phone_e164(phone)
                    except Exception:
                        pass

                    if phone_value == user_phone:
                        identifiers_match = True
                        break

            if not identifiers_match:
                return False, f"Card does not contain matching identifier for user {user}"

        return True, f"Successfully verified {len(cards)} cards"

    except requests.exceptions.RequestException as e:
        return False, f"Request failed: {str(e)}"


def verify_filtered_content(user: str, settings: Dict[str, bool]) -> Tuple[bool, str]:
    """Verify that the VCF cards are filtered according to privacy settings.

    For each card, checks that:
    1. If a privacy setting is enabled (True), the corresponding fields should NOT be present
    2. Basic fields (fn, version) are mandatory
    3. Basic fields (fn, n, email/tel) are public and should never be filtered if original card had them
    """
    try:
        # Get the filtered cards
        cards_url = f"{API_BASE_URL}/privacy/cards/{user}"
        response_get: requests.Response = requests.get(cards_url, auth=(user, ""))

        if response_get.status_code != 200:
            return False, f"Failed to get filtered cards: HTTP {response_get.status_code}: {response_get.text}"

        data = response_get.json()

        if not data or "matches" not in data:
            return False, "No cards data found"

        cards = data["matches"]

        print(cards)

        if not cards:
            return False, "No cards found after filtering"

        # Verify each card's content against settings
        for card_idx, card in enumerate(cards):
            if "fields" not in card:
                return False, f"Card {card_idx}: Missing fields data"

            fields = card["fields"]

            # Always verify basic fields are present (these should never be filtered)
            if "fn" not in fields:
                return False, f"Card {card_idx}: Missing required fn field"
            if "version" not in fields:
                return False, f"Card {card_idx}: Missing required version field"
            # if "n" not in fields:
            #     return False, f"Card {card_idx}: Missing required n field"
            # if "email" not in fields and "tel" not in fields:
            #     return False, f"Card {card_idx}: Missing both email and tel fields"

            # Check each privacy setting against its corresponding vCard properties
            for setting, properties in PRIVACY_TO_VCARD_MAP.items():
                if settings.get(setting, False):  # If the privacy setting is enabled
                    # Check if any of the disallowed properties are present
                    for prop in properties:  # properties are already uppercase from PRIVACY_TO_VCARD_MAP
                        if prop in fields:
                            return False, f"Card {card_idx}: {prop} found when {setting} is enabled"

        return True, f"All {len(cards)} cards properly filtered according to settings"

    except requests.exceptions.RequestException as e:
        return False, f"Request failed: {str(e)}"


def verify_settings(user: str, expected_settings: Optional[Dict[str, bool]]) -> Tuple[bool, str]:
    """Verify that the settings stored on the server match the expected settings.

    Args:
        user: The user identifier (email)
        expected_settings: The expected settings dict, or None if no settings expected

    Returns:
        Tuple of (success, message)
    """
    try:
        settings_url = f"{API_BASE_URL}/privacy/settings/{user}"
        response: requests.Response = requests.get(settings_url, auth=(user, ""))

        if expected_settings is None:
            # We expect no settings to exist
            if response.status_code == 404:
                return True, "No settings exist as expected"
            return False, f"Expected no settings but got status code {response.status_code}"

        # We expect settings to exist
        if response.status_code != 200:
            return False, f"Failed to get settings: HTTP {response.status_code}: {response.text}"

        actual_settings = response.json()
        if not isinstance(actual_settings, dict):
            return False, f"Invalid settings format: {actual_settings}"

        # Compare settings
        for key, value in expected_settings.items():
            if key not in actual_settings:
                return False, f"Missing setting: {key}"
            if actual_settings[key] != value:
                return False, f"Setting {key} has value {actual_settings[key]}, expected {value}"

        return True, "Settings match expected values"

    except requests.exceptions.RequestException as e:
        return False, f"Request failed: {str(e)}"


def process_vcf_file(vcf_file: str) -> Tuple[bool, List[str]]:
    """Process a single VCF file through the upload and verification workflow."""
    messages = []

    # Read VCF content
    vcf_path = os.path.join(VCF_DIR, vcf_file)
    try:
        vcf_content = read_vcf_file(vcf_path)
    except Exception as e:
        return False, [f"Failed to read VCF file: {e}"]

    # Extract email identifier
    user = extract_email_from_vcf(vcf_content)

    if not user:
        return False, ["Could not extract email from VCF"]

    # Read settings if they exist (None if they don't)
    settings = read_settings(vcf_file)

    # If settings exist, upload them. If not, let server use defaults
    if settings is not None:
        success, msg = upload_settings(user, settings)
        messages.append(f"Settings: {msg}")
        if not success:
            return False, messages

        # Verify settings were uploaded correctly
        success, msg = verify_settings(user, settings)
        messages.append(f"Settings verification: {msg}")
        if not success:
            return False, messages

    # Upload VCF
    success, msg = upload_vcf(vcf_content, user)
    messages.append(f"VCF: {msg}")
    if not success:
        return False, messages

    # Verify upload
    success, msg = verify_card(user)
    messages.append(f"Verification: {msg}")
    if not success:
        return False, messages

    # Verify filtered content (using settings if provided, otherwise verify with server defaults)
    if settings is None:
        # Use default settings for verification (all fields allowed)
        settings = {setting: False for setting in PRIVACY_TO_VCARD_MAP.keys()}
    success, msg = verify_filtered_content(user, settings)
    messages.append(f"Filter verification with custom settings: {msg}")

    if not success:
        return False, messages

    return True, messages


def test_privacy_enforcement_across_users() -> Tuple[bool, List[str]]:
    """Test privacy settings enforcement across multiple users' vCards.

    Scenario:
    1. Create vCards for 3 users (user1, user2, user3) all containing info about target_user
    2. Set default privacy settings for all users including target_user
    3. Verify fields are visible in all vCards
    4. Update target_user's privacy settings to be more restrictive
    5. Verify fields are filtered in all vCards
    """
    messages = []
    target_user = "target@example.com"
    test_users = ["user1@example.com", "user2@example.com", "user3@example.com"]

    # Step 1: Create default privacy settings for all users (including target user)
    default_settings = {setting: False for setting in PRIVACY_TO_VCARD_MAP.keys()}

    # Create settings for all test users
    for user in test_users + [target_user]:
        success, msg = upload_settings(user, default_settings)
        messages.append(f"Default settings upload for {user}: {msg}")
        if not success:
            return False, messages

        # Verify settings were uploaded correctly
        success, msg = verify_settings(user, default_settings)
        messages.append(f"Default settings verification: {msg}")
        if not success:
            return False, messages

    # Step 2: Upload target_user's vCards for each user
    for user in test_users:
        # Create a vCard containing target user's info
        vcf_content = f"""BEGIN:VCARD
VERSION:4.0
FN:Target User
EMAIL:{target_user}
ORG:Test Company
TITLE:Test Title
BDAY:1990-01-01
GENDER:M
ADR:;;123 Test St;Test City;;12345;Test Country
END:VCARD"""

        success, msg = upload_vcf(vcf_content, user)
        messages.append(f"VCard upload for {user}: {msg}")
        if not success:
            return False, messages

    # Step 3: Verify fields are visible in target_user's vCards
    success, msg = verify_filtered_content(target_user, default_settings)
    messages.append(f"Initial verification for {target_user}: {msg}")
    if not success:
        return False, messages

    # Step 4: Update target user's privacy settings to be more restrictive
    restricted_settings = {setting: True for setting in PRIVACY_TO_VCARD_MAP.keys()}

    success, msg = upload_settings(target_user, restricted_settings)
    messages.append(f"Restricted settings upload for {target_user}: {msg}")
    if not success:
        return False, messages

    success, msg = verify_settings(target_user, restricted_settings)
    messages.append(f"Restricted settings verification: {msg}")
    if not success:
        return False, messages

    # Step 5: Verify fields are filtered in all vCards
    success, msg = verify_filtered_content(target_user, restricted_settings)
    messages.append(f"Post-restriction verification for {user}: {msg}")
    if not success:
        return False, messages

    return True, messages


def test_most_restrictive_settings_integration() -> Tuple[bool, List[str]]:
    """Test that the most restrictive settings are applied when multiple matches exist.

    This test verifies that when a vCard contains multiple identifiers (email and phone),
    and different privacy settings exist for each identifier, the most restrictive
    settings are applied (i.e., if any identifier has a setting enabled, that field
    should be filtered out).
    """
    messages = []

    # Test identifiers
    email_identifier = "john.doe.restrictive@example.com"
    phone_identifier = "+14155552671"  # Valid US phone number

    # Create a vCard with multiple identifiers and all privacy-sensitive fields
    vcf_content = f"""BEGIN:VCARD
VERSION:4.0
FN:John Doe
N:Doe;John;;;
EMAIL:{email_identifier}
TEL:{phone_identifier}
PHOTO:data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAIAAACQd1PeAAAAD0lEQVQIHQEEAPv/AP///wX+Av4DfRnGAAAAAElFTkSuQmCC
GENDER:M
BDAY:1990-01-01
ADR:;;123 Main St;Springfield;;12345;USA
ORG:Test Company
TITLE:Software Engineer
END:VCARD"""

    # Step 1: Set up different privacy settings for each identifier
    # Email settings: disallow company and title
    email_settings = {
        "disallow_photo": False,
        "disallow_gender": False,
        "disallow_birthday": False,
        "disallow_address": False,
        "disallow_company": True,  # This should be filtered
        "disallow_title": True,    # This should be filtered
    }

    # Phone settings: disallow photo and gender
    phone_settings = {
        "disallow_photo": True,    # This should be filtered
        "disallow_gender": True,   # This should be filtered
        "disallow_birthday": False,
        "disallow_address": False,
        "disallow_company": False,
        "disallow_title": False,
    }

    # Upload settings for email identifier
    success, msg = upload_settings(email_identifier, email_settings)
    messages.append(f"Email settings upload: {msg}")
    if not success:
        return False, messages

    # Upload settings for phone identifier
    success, msg = upload_settings(phone_identifier, phone_settings)
    messages.append(f"Phone settings upload: {msg}")
    if not success:
        return False, messages

    # Verify settings were uploaded correctly
    success, msg = verify_settings(email_identifier, email_settings)
    messages.append(f"Email settings verification: {msg}")
    if not success:
        return False, messages

    success, msg = verify_settings(phone_identifier, phone_settings)
    messages.append(f"Phone settings verification: {msg}")
    if not success:
        return False, messages

    # Step 2: Upload the vCard (using email as the uploader)
    success, msg = upload_vcf(vcf_content, email_identifier)
    messages.append(f"VCard upload: {msg}")
    if not success:
        return False, messages

    # Step 3: Verify the card was uploaded successfully
    success, msg = verify_card(email_identifier)
    messages.append(f"Card verification: {msg}")
    if not success:
        return False, messages

    # Step 4: Verify that the most restrictive settings are applied
    # The combined most restrictive settings should be:
    most_restrictive_settings = {
        "disallow_photo": True,    # From phone settings
        "disallow_gender": True,   # From phone settings
        "disallow_birthday": False,
        "disallow_address": False,
        "disallow_company": True,  # From email settings
        "disallow_title": True,    # From email settings
    }

    success, msg = verify_filtered_content(email_identifier, most_restrictive_settings)
    messages.append(f"Most restrictive settings verification: {msg}")
    if not success:
        return False, messages

    # Step 5: Also verify from phone identifier perspective
    success, msg = verify_card(phone_identifier)
    messages.append(f"Phone card verification: {msg}")
    if not success:
        return False, messages

    success, msg = verify_filtered_content(phone_identifier, most_restrictive_settings)
    messages.append(f"Phone most restrictive settings verification: {msg}")
    if not success:
        return False, messages

    return True, messages


def process_multi_vcf_file(vcf_file: str) -> Tuple[bool, List[str]]:
    """Process a VCF file containing multiple vCards.

    This function handles VCF files that contain multiple vCard entries by:
    1. Extracting all email addresses from the file using vobject
    2. Setting up privacy settings for each unique email
    3. Uploading the entire VCF file once
    4. Verifying cards for each email address
    """
    messages = []

    # Read VCF content
    vcf_path = os.path.join(VCF_DIR, vcf_file)
    try:
        vcf_content = read_vcf_file(vcf_path)
    except Exception as e:
        return False, [f"Failed to read VCF file: {e}"]

    # Extract all email addresses using vobject
    emails = set()
    try:
        for vcard in vobject.readComponents(vcf_content):
            if hasattr(vcard, "email_list"):
                for email in vcard.email_list:
                    if email.value:
                        emails.add(email.value)
    except Exception as e:
        return False, [f"Failed to parse VCF content: {e}"]

    if not emails:
        return False, ["No email addresses found in VCF"]

    # Set up settings for each email
    settings = read_settings(vcf_file)
    if not settings:
        messages.append("Warning: Using empty settings")
        settings = {setting: False for setting in PRIVACY_TO_VCARD_MAP.keys()}

    for email in emails:
        success, msg = upload_settings(email, settings)
        messages.append(f"Settings for {email}: {msg}")
        if not success:
            return False, messages

    # Upload VCF once (it contains all contacts)
    # Use the first email as the uploader
    first_email = next(iter(emails))
    success, msg = upload_vcf(vcf_content, first_email)
    messages.append(f"VCF upload by {first_email}: {msg}")
    if not success:
        return False, messages

    # Verify cards for each email
    for email in emails:
        success, msg = verify_card(email)
        messages.append(f"Verification for {email}: {msg}")
        if not success:
            return False, messages

        success, msg = verify_filtered_content(email, settings)
        messages.append(f"Filter verification for {email}: {msg}")
        if not success:
            return False, messages

    return True, messages


def main() -> None:
    """Main function to run integration tests."""
    print("Starting VCF integration tests...")

    # Get all VCF files
    vcf_files = [f for f in os.listdir(VCF_DIR) if f.endswith('.vcf')]

    # Test results
    results = []

    # First process single-vCard files
    single_vcf_files = []
    multi_vcf_files = []

    # Separate single and multi vCard files using vobject
    for vcf_file in sorted(vcf_files):
        vcf_content = read_vcf_file(os.path.join(VCF_DIR, vcf_file))
        try:
            vcards = list(vobject.readComponents(vcf_content))
            if len(vcards) > 1:
                multi_vcf_files.append(vcf_file)
            else:
                single_vcf_files.append(vcf_file)
        except Exception as e:
            print(f"Warning: Failed to parse {vcf_file}: {e}")
            continue

    # Process single-vCard files first
    print("\nProcessing single-vCard files...")
    for vcf_file in single_vcf_files:
        print(f"\nTesting {vcf_file}...")
        success, messages = process_vcf_file(vcf_file)
        results.append((vcf_file, success, messages))
        for msg in messages:
            print(f"  {msg}")

    # # Then process multi-vCard files
    # print("\nProcessing multi-vCard files...")
    # for vcf_file in multi_vcf_files:
    #     print(f"\nTesting {vcf_file}...")
    #     success, messages = process_multi_vcf_file(vcf_file)
    #     results.append((vcf_file, success, messages))
    #     for msg in messages:
    #         print(f"  {msg}")

    # Run privacy enforcement test last
    print("\nTesting privacy enforcement across users...")
    success, messages = test_privacy_enforcement_across_users()
    results.append(("privacy_enforcement", success, messages))
    for msg in messages:
        print(f"  {msg}")

    # Run most restrictive settings test
    print("\nTesting most restrictive settings integration...")
    success, messages = test_most_restrictive_settings_integration()
    results.append(("most_restrictive_settings", success, messages))
    for msg in messages:
        print(f"  {msg}")

    # Print summary
    print("\nTest Summary:")
    print("-" * 60)
    for test_name, success, messages in results:
        status = "✓" if success else "✗"
        print(f"{status} {test_name}")
    print("-" * 60)

    # Count successes and failures
    successes = sum(1 for _, success, _ in results if success)
    total = len(results)
    print(f"\nTotal: {total} tests")
    print(f"Successes: {successes}")
    print(f"Failures: {total - successes}")


if __name__ == "__main__":
    main()
