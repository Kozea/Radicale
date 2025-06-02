#!/usr/bin/env python3
"""Script to test VCF upload through the HTTP API."""

import json
import os
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import requests

# Add the project root to the Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# Configuration
API_BASE_URL: str = "http://localhost:5232"  # Adjust if needed
VCF_DIR: str = os.path.join(os.path.dirname(os.path.abspath(__file__)), "vcf")
SETTINGS_DIR: str = os.path.join(os.path.dirname(os.path.abspath(__file__)), "settings")


def read_vcf_file(file_path: str) -> str:
    """Read a VCF file and return its contents."""
    with open(file_path, 'r') as f:
        return f.read()


def read_privacy_settings(vcf_filename: str) -> Dict[str, bool]:
    """Read privacy settings from JSON file for a specific user.

    Args:
        vcf_filename: The VCF filename (e.g., 'test1.vcf')

    Returns:
        Dictionary containing privacy settings
    """
    # Convert vcf filename to settings filename (e.g., 'test1.vcf' -> 'test1_settings.json')
    settings_filename: str = f"{os.path.splitext(vcf_filename)[0]}_settings.json"
    settings_file: str = os.path.join(SETTINGS_DIR, settings_filename)

    default_settings: Dict[str, bool] = {
        "disallow_photo": False,
        "disallow_gender": False,
        "disallow_birthday": False,
        "disallow_address": False,
        "disallow_company": False,
        "disallow_title": False,
    }

    try:
        with open(settings_file, 'r') as f:
            return json.load(f)
    except FileNotFoundError:
        print(f"Warning: No settings file found for {settings_filename}, using default settings")
        return default_settings
    except json.JSONDecodeError:
        print(f"Error: Invalid JSON in settings file for {settings_filename}, using default settings")
        return default_settings


def upload_settings(user: str, settings: Dict[str, bool]) -> Tuple[bool, str]:
    """Upload privacy settings for a user.

    Args:
        user: The user identifier (email)
        settings: The privacy settings to upload

    Returns:
        Tuple of (success, message)
    """
    try:
        settings_url: str = f"{API_BASE_URL}/privacy/settings/{user}"
        response: requests.Response = requests.get(settings_url, auth=(user, ""))

        if response.status_code == 404:
            # Settings don't exist, create them
            response = requests.post(settings_url, json=settings, auth=(user, ""))
            if response.status_code != 201:
                return False, f"Failed to create settings: {response.text}"
            return True, "Settings created successfully"
        elif response.status_code == 200:
            # Settings exist, update them
            response = requests.put(settings_url, json=settings, auth=(user, ""))
            if response.status_code != 200:
                return False, f"Failed to update settings: {response.text}"
            return True, "Settings updated successfully"
        else:
            return False, f"Failed to check settings: {response.text}"

    except requests.exceptions.RequestException as e:
        return False, f"Request failed: {str(e)}"


def upload_vcf(vcf_content: str, user: str) -> Tuple[bool, str]:
    """Upload a VCF file through the HTTP API.

    Args:
        vcf_content: The content of the VCF file
        user: The user identifier (email)

    Returns:
        Tuple of (success, message)
    """
    try:
        # Upload the VCF content to the user's contacts collection
        cards_url: str = f"{API_BASE_URL}/{user}/contacts/"
        # Send the VCF content directly
        response: requests.Response = requests.put(
            cards_url,
            data=vcf_content,
            auth=(user, ""),
            headers={"Content-Type": "text/vcard"}
        )

        if response.status_code in (200, 201):
            return True, "VCF uploaded successfully"
        else:
            return False, f"Failed to upload VCF: {response.text}"

    except requests.exceptions.RequestException as e:
        return False, f"Request failed: {str(e)}"


def verify_upload(user: str) -> Tuple[bool, str]:
    """Verify that the VCF was uploaded and processed correctly.

    Args:
        user: The user identifier (email)

    Returns:
        Tuple of (success, message)
    """
    try:
        # Get the processed cards
        cards_url: str = f"{API_BASE_URL}/privacy/cards/{user}"
        response: requests.Response = requests.get(cards_url, auth=(user, ""))

        if response.status_code != 200:
            return False, f"Failed to get cards: {response.text}"

        cards: List[Dict[str, Any]] = response.json()
        if not cards:
            return False, "No cards found after upload"

        return True, f"Found {len(cards)} cards after upload"

    except requests.exceptions.RequestException as e:
        return False, f"Request failed: {str(e)}"


def process_vcf_file(vcf_file: str) -> Tuple[bool, str]:
    """Process a single VCF file: read content, extract user, upload settings and VCF.

    Args:
        vcf_file: The name of the VCF file to process

    Returns:
        Tuple of (success, message)
    """
    print(f"\nProcessing {vcf_file}...")

    # Read VCF content
    vcf_path: str = os.path.join(VCF_DIR, vcf_file)
    vcf_content: str = read_vcf_file(vcf_path)

    # Extract user identifier from VCF content
    user: Optional[str] = None
    for line in vcf_content.split('\n'):
        if line.startswith('EMAIL;'):
            user = line.split(':')[1].strip()
            break

    if not user:
        return False, f"Could not find email in {vcf_file}"

    # Get and upload settings first
    settings: Dict[str, bool] = read_privacy_settings(vcf_file)
    success: bool
    message: str
    success, message = upload_settings(user, settings)
    if not success:
        return False, f"Settings upload failed: {message}"
    print(f"Settings: {message}")

    # Then upload VCF
    success, message = upload_vcf(vcf_content, user)
    if not success:
        return False, f"VCF upload failed: {message}"
    print(f"VCF: {message}")

    # Verify upload
    success, message = verify_upload(user)
    if not success:
        return False, f"Verification failed: {message}"
    print(f"Verification: {message}")

    return True, "Processing completed successfully"


def main() -> None:
    """Main function to test VCF upload."""
    print("Starting VCF upload test...")

    # Get all VCF files
    vcf_files: List[str] = [f for f in os.listdir(VCF_DIR) if f.endswith('.vcf')]

    # Process each VCF file
    results: List[Tuple[str, bool, str]] = []
    for vcf_file in vcf_files:
        success: bool
        message: str
        success, message = process_vcf_file(vcf_file)
        results.append((vcf_file, success, message))

    # Print summary
    print("\nTest Summary:")
    print("-" * 50)
    for vcf_file, success, message in results:
        status: str = "✓" if success else "✗"
        print(f"{status} {vcf_file}: {message}")
    print("-" * 50)

    # Count successes and failures
    successes: int = sum(1 for _, success, _ in results if success)
    failures: int = len(results) - successes
    print(f"\nTotal: {len(results)} files")
    print(f"Successes: {successes}")
    print(f"Failures: {failures}")


if __name__ == "__main__":
    main()
