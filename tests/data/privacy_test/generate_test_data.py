#!/usr/bin/env python3

import os
import json
from typing import Dict, List

import vobject


def create_vcard(data: Dict) -> vobject.vCard:
    """Create a vCard with the given data."""
    card = vobject.vCard()

    # Add UID
    card.add("uid")
    card.uid.value = data.get("uid", "")

    # Add name
    if "name" in data:
        card.add("n")
        card.n.value = vobject.vcard.Name(
            family=data["name"].split()[1] if len(data["name"].split()) > 1 else "",
            given=data["name"].split()[0],
        )
        card.add("fn")
        card.fn.value = data["name"]

    # Add email(s)
    if "email" in data:
        emails = data["email"] if isinstance(data["email"], list) else [data["email"]]
        for email in emails:
            card.add("email")
            card.email.value = email
            card.email.type_param = "INTERNET"

    # Add phone(s)
    if "phone" in data:
        phones = data["phone"] if isinstance(data["phone"], list) else [data["phone"]]
        for phone in phones:
            card.add("tel")
            card.tel.value = phone
            card.tel.type_param = "CELL"

    # Add company
    if "company" in data:
        card.add("org")
        card.org.value = [data["company"]]

    # Add title
    if "title" in data:
        card.add("title")
        card.title.value = data["title"]

    # Add photo
    if "photo" in data:
        card.add("photo")
        card.photo.value = data["photo"]
        card.photo.type_param = "PNG"

    # Add birthday
    if "birthday" in data:
        card.add("bday")
        card.bday.value = data["birthday"]

    # Add address
    if "address" in data:
        card.add("adr")
        card.adr.value = vobject.vcard.Address(
            street=data["address"].get("street", ""),
            city=data["address"].get("city", ""),
            region=data["address"].get("region", ""),
            code=data["address"].get("code", ""),
            country=data["address"].get("country", ""),
        )

    return card


def generate_test_cards() -> List[Dict]:
    """Generate test card data."""
    return [
        # Test case 1: Basic contact with email and phone
        {
            "uid": "test1",
            "name": "John Doe",
            "email": "john.doe@example.com",
            "phone": "+1234567890",
            "company": "Test Company",
            "title": "Software Engineer",
        },
        # Test case 2: Contact with same email as test1
        {
            "uid": "test2",
            "name": "John Doe (Work)",
            "email": "john.doe@example.com",
            "phone": "+1987654321",
            "company": "Another Company",
            "title": "Senior Developer",
        },
        # Test case 3: Contact with same phone as test1
        {
            "uid": "test3",
            "name": "John Doe (Personal)",
            "email": "john.doe.personal@example.com",
            "phone": "+1234567890",
            "company": "Personal Business",
            "title": "Freelancer",
        },
        # Test case 4: Contact with photo and birthday
        {
            "uid": "test4",
            "name": "Jane Smith",
            "email": "jane.smith@example.com",
            "phone": "+1122334455",
            "company": "Photo Company",
            "title": "Photographer",
            "photo": "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAIAAACQd1PeAAAAD0lEQVQIHQEEAPv/AP///wX+Av4DfRnGAAAAAElFTkSuQmCC",
            "birthday": "1990-01-01",
        },
        # Test case 5: Contact with full address
        {
            "uid": "test5",
            "name": "Bob Wilson",
            "email": "bob.wilson@example.com",
            "phone": "+1555666777",
            "company": "Address Company",
            "title": "Manager",
            "address": {
                "street": "123 Main St",
                "city": "Springfield",
                "region": "IL",
                "code": "62701",
                "country": "USA",
            },
        },
        # Test case 6: Contact with multiple emails
        {
            "uid": "test6",
            "name": "Alice Brown",
            "email": ["alice.brown@example.com", "alice@personal.com"],
            "phone": "+1666777888",
            "company": "Multi Email Corp",
            "title": "Marketing Manager",
        },
        # Test case 7: Contact with multiple phones
        {
            "uid": "test7",
            "name": "Charlie Davis",
            "email": "charlie.davis@example.com",
            "phone": ["+1777888999", "+1888999000"],
            "company": "Multi Phone Inc",
            "title": "Sales Director",
        },
        # Test case 8: Minimal contact (only name and email)
        {"uid": "test8", "name": "Minimal Contact", "email": "minimal@example.com"},
        # Test case 9: Contact with all fields
        {
            "uid": "test9",
            "name": "Full Contact",
            "email": "full.contact@example.com",
            "phone": "+1999000111",
            "company": "Full Details Ltd",
            "title": "CEO",
            "photo": "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAIAAACQd1PeAAAAD0lEQVQIHQEEAPv/AP///wX+Av4DfRnGAAAAAElFTkSuQmCC",
            "birthday": "1985-06-15",
            "address": {
                "street": "456 Business Ave",
                "city": "Metropolis",
                "region": "NY",
                "code": "10001",
                "country": "USA",
            },
        },
    ]


def main():
    """Generate test VCF files."""
    # Get the base directory (tests/data/privacy_test)
    base_dir = os.path.dirname(os.path.abspath(__file__))
    vcf_dir = os.path.join(base_dir, "vcf")
    settings_dir = os.path.join(base_dir, "settings")

    # Create directories if they don't exist
    os.makedirs(vcf_dir, exist_ok=True)
    os.makedirs(settings_dir, exist_ok=True)

    # Generate test cards
    test_cards = generate_test_cards()

    # Create individual VCF files
    for card_data in test_cards:
        card = create_vcard(card_data)
        filename = os.path.join(vcf_dir, f"{card_data['uid']}.vcf")
        with open(filename, "w") as f:
            f.write(card.serialize())
        print(f"Created {filename}")

    # Create a combined VCF file
    combined_filename = os.path.join(vcf_dir, "all_contacts.vcf")
    with open(combined_filename, "w") as f:
        for card_data in test_cards:
            card = create_vcard(card_data)
            f.write(card.serialize())
    print(f"Created {combined_filename}")

    # Create a sample privacy settings file
    sample_settings = {
        "john.doe@example.com": {
            "private_fields": ["photo", "birthday", "address"],
            "allowed_fields": ["name", "email", "phone", "company", "title"],
        },
        "jane.smith@example.com": {
            "private_fields": ["phone", "address"],
            "allowed_fields": [
                "name",
                "email",
                "company",
                "title",
                "photo",
                "birthday",
            ],
        },
    }

    settings_file = os.path.join(settings_dir, "sample_settings.json")
    with open(settings_file, "w") as f:
        json.dump(sample_settings, f, indent=2)
    print(f"Created {settings_file}")


if __name__ == "__main__":
    main()
