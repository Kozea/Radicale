# Inter-dependent Privacy in Radicale

## Technical Architecture

### Server-Side Components (ownership: Rémy)
- Extend Radicale's core functionality to implement privacy-aware contact management
- Develop RESTful HTTP APIs to expose privacy management features
- Integrate with the existing CardDAV protocol stack while maintaining compatibility
- Implement server-side hashing algorithms for identity protection
- Store privacy preferences in a structured format with appropriate access controls

### Client Components (ownership: Bertil)
- **Web Interface**: Develop a React-based single-page application that communicates with Radicale's HTTP APIs
- **Desktop Integration**: Ensure compatibility with Thunderbird as the primary desktop client for vCards

## User Stories

### External User Authentication

- As an external user, I want to authenticate to Radicale without creating a regular account:
  - I will provide my email or phone number in a form
  - The server will send me a one-time password (OTP)
  - I will enter the OTP in a form
  - I will then be authenticated
  - My email or phone number should be hashed by the server to prevent identification based on my external user account

### Privacy Settings Management

- As an authenticated external user, I want to manage my privacy settings:
  - I want to control which personal information others can store about me (e.g., pronouns, company, job title, photo, birthday, address)
  - Radicale needs an API to save privacy settings for authenticated external users
  - Privacy settings should be stored on the filesystem in a simple format
  - The hashed email or phone number should serve as the key to identify my user settings
  - **Question**: Should we support multiple identifiers per user?
    - One identity linked to one settings profile
    - Multiple identities (email/phone) linked to one settings profile
    - Enable users to associate additional emails and phone numbers to their existing settings

### Personal Information Disclosure

- As an authenticated external user, I want to view what information has been stored about me on the Radicale server:
  - Implement viewing formats according to the mockups
  - First implement full disclosure format, then develop aggregated formats
  - This feature requires scanning and reading all vCard files stored on the Radicale server

### Personal Information Control

- As an authenticated external user, I want to clean or modify cards containing my information based on my privacy settings:
  - This feature requires scanning and modifying all vCard files stored on the Radicale server that contain my information

### Privacy Enforcement

- As a regular user saving contact information, the Radicale server should enforce others' privacy preferences:
  - The server should prevent me from saving information that others have marked as private
  - Investigate the CardDAV protocol to determine appropriate HTTP error responses (e.g., 400 Bad Request, 403 Forbidden, 406 Not Acceptable) when privacy violations occur


## Implementation Notes

- Module `/radicale/storage/multifilesystem/upload.py` is responsible for saving vCard files (VCF) to the filesystem
- Privacy rules enforcement should intercept the card saving process before it reaches the filesystem
- User identification through email/phone should use cryptographic hashing with appropriate salt
- Performance considerations needed for scanning large contact databases

## MVP Implementation Plan

### Phase 0: Create a dataset of cards for testing and validation

### Phase 1: Basic Authentication & Privacy Settings

1. **Simple Email Authentication**
   - Create a basic email-based authentication in `radicale/auth/email_auth.py`
   - Implement a simple OTP generation and validation mechanism
   - Use email for OTP delivery (skip SMS for MVP)
   - Store temporary authentication tokens in a simple file-based system

2. **Basic Privacy Settings Storage**
   - Create a simple JSON file structure to store privacy settings
   - Implement a basic hashing function for email identifiers
   - Store settings in `.Radicale.privacy/{hashed_email}.json` format
   - Support a fixed set of vCard fields that can be marked as private

### Phase 2: VCF Processing & Privacy Enforcement

1. **VCF Interception**
   - Modify `radicale/storage/multifilesystem/upload.py` to intercept vCard uploads
   - Add a pre-processing step that checks vCards against privacy rules
   - For the MVP, focus on the most common vCard fields (name, email, phone, company, etc.)
   - Implement simple field validation based on privacy settings

2. **Simple Query Functionality**
   - Create a basic function to scan vCards for a given identity
   - For MVP, focus on exact matches rather than fuzzy matching
   - Implement minimal indexing based on email/phone properties

3. **Basic Privacy Enforcement**
   - Implement rejection of vCard uploads that violate privacy settings
   - Return appropriate error messages to the client
   - For MVP, use HTTP 400 (Bad Request) for all privacy violations

### Phase 3: Information Disclosure

1. **Basic Disclosure API**
   - Create a simple endpoint to retrieve information about the authenticated user
   - Return a list of vCards and fields that match the user's identity
   - Use basic authentication to protect the API

2. **Simple Privacy Dashboard**
   - Create a minimal dashboard showing what information is stored about the user
   - Implement a basic interface to view cards containing user's information
   - Add simple controls to modify privacy settings

### Phase 4: Testing with Real Clients

1. **Thunderbird Compatibility**
   - Test the MVP with Thunderbird to ensure basic compatibility
   - Document any issues or limitations
   - Focus on ensuring core functionality works rather than perfect integration

2. **Basic Documentation**
   - Create minimal documentation explaining how to use the privacy features
   - Document API endpoints and expected responses
   - Include setup instructions for testing purposes

### Comments

We should first implement the features as utilities in python and validate them with unit test.
Then, these utilities will be exposed through an HTTP api.
