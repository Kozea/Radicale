#!/usr/bin/env python3

import os
import unittest

import vobject


class TestPrivacyDataset(unittest.TestCase):
    """Test cases for the privacy test dataset."""

    @classmethod
    def setUpClass(cls):
        """Set up test data paths."""
        # Get the base directory (tests/data/privacy_test)
        cls.base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        cls.data_dir = os.path.join(cls.base_dir, 'data', 'privacy')
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
                        # Verify gender field if present
                        for vcard in vobject.readComponents(content):
                            if hasattr(vcard, 'gender'):
                                self.assertIsInstance(vcard.gender.value, str)
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

            # Check that no gender field exists
            self.assertFalse(hasattr(vcard, 'gender'))

    def test_test2_has_same_email(self):
        """Test that test2.vcf has the same email as test1 but different phone."""
        filepath = os.path.join(self.vcf_dir, 'test2.vcf')
        with open(filepath, 'r') as f:
            content = f.read()
            vcard = vobject.readOne(content)

            # Check fields
            self.assertEqual(vcard.uid.value, 'test2')
            self.assertEqual(vcard.fn.value, 'John Doe (Work)')
            self.assertEqual(vcard.email.value, 'john.doe.work@example.com')  # Same as test1
            self.assertEqual(vcard.tel.value, '+1987654321')  # Different from test1
            self.assertEqual(vcard.org.value, ['Another Company'])
            self.assertEqual(vcard.title.value, 'Senior Developer')

    def test_test3_has_same_phone(self):
        """Test that test3.vcf has the same phone as test1 but different email."""
        filepath = os.path.join(self.vcf_dir, 'test3.vcf')
        with open(filepath, 'r') as f:
            content = f.read()
            vcard = vobject.readOne(content)

            # Check fields
            self.assertEqual(vcard.uid.value, 'test3')
            self.assertEqual(vcard.fn.value, 'John Doe (Personal)')
            self.assertEqual(vcard.email.value, 'john.doe.personal@example.com')  # Different from test1
            self.assertEqual(vcard.tel.value, '+1234567890')  # Same as test1
            self.assertEqual(vcard.org.value, ['Personal Business'])
            self.assertEqual(vcard.title.value, 'Freelancer')

    def test_test4_has_photo_and_gender(self):
        """Test that test4.vcf contains photo and gender fields."""
        filepath = os.path.join(self.vcf_dir, 'test4.vcf')
        with open(filepath, 'r') as f:
            content = f.read()
            vcard = vobject.readOne(content)

            # Check fields
            self.assertEqual(vcard.uid.value, 'test4')
            self.assertEqual(vcard.fn.value, 'Jane Smith')
            self.assertEqual(vcard.email.value, 'jane.smith@example.com')
            self.assertEqual(vcard.tel.value, '+1122334455')
            self.assertTrue(hasattr(vcard, 'photo'))
            self.assertEqual(vcard.gender.value, 'F')
            self.assertEqual(vcard.bday.value, '1990-01-01')
            self.assertEqual(vcard.org.value, ['Photo Company'])
            self.assertEqual(vcard.title.value, 'Photographer')

    def test_test5_has_address(self):
        """Test that test5.vcf contains a full address."""
        filepath = os.path.join(self.vcf_dir, 'test5.vcf')
        with open(filepath, 'r') as f:
            content = f.read()
            vcard = vobject.readOne(content)

            # Check fields
            self.assertEqual(vcard.uid.value, 'test5')
            self.assertEqual(vcard.fn.value, 'Bob Wilson')
            self.assertEqual(vcard.email.value, 'bob.wilson@example.com')
            self.assertEqual(vcard.tel.value, '+1555666777')
            self.assertTrue(hasattr(vcard, 'adr'))
            self.assertEqual(vcard.adr.value.street, '123 Main St')
            self.assertEqual(vcard.adr.value.city, 'Springfield')
            self.assertEqual(vcard.adr.value.region, 'IL')
            self.assertEqual(vcard.adr.value.code, '62701')
            self.assertEqual(vcard.adr.value.country, 'USA')
            self.assertEqual(vcard.org.value, ['Address Company'])
            self.assertEqual(vcard.title.value, 'Manager')

    def test_test6_has_multiple_emails(self):
        """Test that test6.vcf contains multiple email addresses."""
        filepath = os.path.join(self.vcf_dir, 'test6.vcf')
        with open(filepath, 'r') as f:
            content = f.read()
            vcard = vobject.readOne(content)

            # Get all email values
            emails = [email.value for email in vcard.email_list]
            self.assertEqual(len(emails), 2)
            self.assertIn('alice.brown@example.com', emails)
            self.assertIn('alice@personal.com', emails)

            # Check other fields
            self.assertEqual(vcard.uid.value, 'test6')
            self.assertEqual(vcard.fn.value, 'Alice Brown')
            self.assertEqual(vcard.tel.value, '+1666777888')
            self.assertEqual(vcard.org.value, ['Multi Email Corp'])
            self.assertEqual(vcard.title.value, 'Marketing Manager')

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

            # Check other fields
            self.assertEqual(vcard.uid.value, 'test7')
            self.assertEqual(vcard.fn.value, 'Charlie Davis')
            self.assertEqual(vcard.email.value, 'charlie.davis@example.com')
            self.assertEqual(vcard.org.value, ['Multi Phone Inc'])
            self.assertEqual(vcard.title.value, 'Sales Director')

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
            self.assertEqual(vcard.gender.value, 'F')
            self.assertEqual(vcard.bday.value, '1985-06-15')
            self.assertTrue(hasattr(vcard, 'adr'))
            self.assertEqual(vcard.adr.value.street, '456 Business Ave')
            self.assertEqual(vcard.adr.value.city, 'Metropolis')
            self.assertEqual(vcard.adr.value.region, 'NY')
            self.assertEqual(vcard.adr.value.code, '10001')
            self.assertEqual(vcard.adr.value.country, 'USA')

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

            # Verify each vCard has the correct fields
            for vcard in vcards:
                uid = vcard.uid.value
                if uid == 'test1':
                    self.assertEqual(vcard.fn.value, 'John Doe')
                    self.assertEqual(vcard.email.value, 'john.doe@example.com')
                elif uid == 'test2':
                    self.assertEqual(vcard.fn.value, 'John Doe (Work)')
                    self.assertEqual(vcard.email.value, 'john.doe@example.com')
                elif uid == 'test3':
                    self.assertEqual(vcard.fn.value, 'John Doe (Personal)')
                    self.assertEqual(vcard.email.value, 'john.doe.personal@example.com')
                elif uid == 'test4':
                    self.assertEqual(vcard.fn.value, 'Jane Smith')
                    self.assertEqual(vcard.gender.value, 'F')
                elif uid == 'test5':
                    self.assertEqual(vcard.fn.value, 'Bob Wilson')
                    self.assertTrue(hasattr(vcard, 'adr'))
                elif uid == 'test6':
                    self.assertEqual(vcard.fn.value, 'Alice Brown')
                    self.assertEqual(len(vcard.email_list), 2)
                elif uid == 'test7':
                    self.assertEqual(vcard.fn.value, 'Charlie Davis')
                    self.assertEqual(len(vcard.contents.get('tel', [])), 2)
                elif uid == 'test8':
                    self.assertEqual(vcard.fn.value, 'Minimal Contact')
                    self.assertEqual(len(vcard.contents), 5)  # uid, fn, n, email, version
                elif uid == 'test9':
                    self.assertEqual(vcard.fn.value, 'Full Contact')
                    self.assertTrue(hasattr(vcard, 'photo'))
                    self.assertTrue(hasattr(vcard, 'gender'))
                    self.assertTrue(hasattr(vcard, 'adr'))


if __name__ == '__main__':
    unittest.main()
