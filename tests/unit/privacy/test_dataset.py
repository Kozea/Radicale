#!/usr/bin/env python3

import os
import json
import vobject
import unittest

class TestPrivacyDataset(unittest.TestCase):
    """Test cases for the privacy test dataset."""

    @classmethod
    def setUpClass(cls):
        """Set up test data paths."""
        # Get the base directory (tests/data/privacy_test)
        cls.base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        cls.data_dir = os.path.join(cls.base_dir, 'data', 'privacy_test')
        cls.vcf_dir = os.path.join(cls.data_dir, 'vcf')
        cls.settings_dir = os.path.join(cls.data_dir, 'settings')

    def test_vcf_files_exist(self):
        """Test that all expected VCF files exist."""
        expected_files = [
            'test1.vcf', 'test2.vcf', 'test3.vcf', 'test4.vcf', 'test5.vcf',
            'test6.vcf', 'test7.vcf', 'test8.vcf', 'test9.vcf', 'all_contacts.vcf'
        ]
        for filename in expected_files:
            filepath = os.path.join(self.vcf_dir, filename)
            self.assertTrue(os.path.exists(filepath), f"VCF file {filename} does not exist")

    def test_vcf_files_are_valid(self):
        """Test that all VCF files contain valid vCard data."""
        for filename in os.listdir(self.vcf_dir):
            if filename.endswith('.vcf'):
                filepath = os.path.join(self.vcf_dir, filename)
                with open(filepath, 'r') as f:
                    content = f.read()
                    try:
                        # Parse the VCF content
                        vcards = vobject.readComponents(content)
                        # Verify we can read at least one vCard
                        self.assertTrue(any(True for _ in vcards), f"No valid vCard found in {filename}")
                    except Exception as e:
                        self.fail(f"Failed to parse {filename}: {str(e)}")

    def test_test1_has_expected_fields(self):
        """Test that test1.vcf contains the expected fields."""
        filepath = os.path.join(self.vcf_dir, 'test1.vcf')
        with open(filepath, 'r') as f:
            content = f.read()
            vcard = vobject.readOne(content)
            
            # Check required fields
            self.assertEqual(vcard.uid.value, 'test1')
            self.assertEqual(vcard.fn.value, 'John Doe')
            self.assertEqual(vcard.email.value, 'john.doe@example.com')
            self.assertEqual(vcard.tel.value, '+1234567890')
            self.assertEqual(vcard.org.value, ['Test Company'])
            self.assertEqual(vcard.title.value, 'Software Engineer')

    def test_test6_has_multiple_emails(self):
        """Test that test6.vcf contains multiple email addresses."""
        filepath = os.path.join(self.vcf_dir, 'test6.vcf')
        with open(filepath, 'r') as f:
            content = f.read()
            vcard = vobject.readOne(content)
            emails = [email.value for email in vcard.email_list]
            self.assertIn('alice@personal.com', emails)

    def test_test7_has_multiple_phones(self):
        """Test that test7.vcf contains multiple phone numbers."""
        filepath = os.path.join(self.vcf_dir, 'test7.vcf')
        with open(filepath, 'r') as f:
            content = f.read()
            vcard = vobject.readOne(content)
            
            # Get all phone values
            phones = [tel.value for tel in vcard.contents.get('tel', [])]
            self.assertEqual(len(phones), 2)
            self.assertIn('+1777888999', phones)
            self.assertIn('+1888999000', phones)

    def test_test8_is_minimal(self):
        """Test that test8.vcf contains only name and email."""
        filepath = os.path.join(self.vcf_dir, 'test8.vcf')
        with open(filepath, 'r') as f:
            content = f.read()
            vcard = vobject.readOne(content)
            
            # Check required fields
            self.assertEqual(vcard.uid.value, 'test8')
            self.assertEqual(vcard.fn.value, 'Minimal Contact')
            self.assertEqual(vcard.email.value, 'minimal@example.com')
            
            # Check that no other fields exist
            expected_fields = {'uid', 'fn', 'n', 'email', 'version'}
            actual_fields = set(vcard.contents.keys())
            self.assertEqual(actual_fields, expected_fields)

    def test_test9_has_all_fields(self):
        """Test that test9.vcf contains all possible fields."""
        filepath = os.path.join(self.vcf_dir, 'test9.vcf')
        with open(filepath, 'r') as f:
            content = f.read()
            vcard = vobject.readOne(content)
            
            # Check all fields
            self.assertEqual(vcard.uid.value, 'test9')
            self.assertEqual(vcard.fn.value, 'Full Contact')
            self.assertEqual(vcard.email.value, 'full.contact@example.com')
            self.assertEqual(vcard.tel.value, '+1999000111')
            self.assertEqual(vcard.org.value, ['Full Details Ltd'])
            self.assertEqual(vcard.title.value, 'CEO')
            self.assertTrue(hasattr(vcard, 'photo'))
            self.assertEqual(vcard.bday.value, '1985-06-15')
            self.assertTrue(hasattr(vcard, 'adr'))

    def test_privacy_settings_exist(self):
        """Test that the privacy settings file exists and is valid JSON."""
        settings_file = os.path.join(self.settings_dir, 'sample_settings.json')
        self.assertTrue(os.path.exists(settings_file), "Privacy settings file does not exist")
        
        with open(settings_file, 'r') as f:
            try:
                settings = json.load(f)
                self.assertIsInstance(settings, dict)
            except json.JSONDecodeError as e:
                self.fail(f"Invalid JSON in privacy settings file: {str(e)}")

    def test_privacy_settings_structure(self):
        """Test that the privacy settings have the expected structure."""
        settings_file = os.path.join(self.settings_dir, 'sample_settings.json')
        with open(settings_file, 'r') as f:
            settings = json.load(f)
            
            # Check structure for each user
            for email, user_settings in settings.items():
                self.assertIsInstance(user_settings, dict)
                self.assertIn('private_fields', user_settings)
                self.assertIn('allowed_fields', user_settings)
                self.assertIsInstance(user_settings['private_fields'], list)
                self.assertIsInstance(user_settings['allowed_fields'], list)
                
                # Check that fields are not in both lists
                private = set(user_settings['private_fields'])
                allowed = set(user_settings['allowed_fields'])
                self.assertEqual(private.intersection(allowed), set(),
                              f"Fields cannot be both private and allowed for {email}")

    def test_all_contacts_file(self):
        """Test that all_contacts.vcf contains all test contacts."""
        filepath = os.path.join(self.vcf_dir, 'all_contacts.vcf')
        with open(filepath, 'r') as f:
            content = f.read()
            vcards = list(vobject.readComponents(content))
            
            # Should have 9 contacts
            self.assertEqual(len(vcards), 9)
            
            # Check that all UIDs are present
            uids = {vcard.uid.value for vcard in vcards}
            expected_uids = {f'test{i}' for i in range(1, 10)}
            self.assertEqual(uids, expected_uids)

if __name__ == '__main__':
    unittest.main() 