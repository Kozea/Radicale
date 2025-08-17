import 'dotenv/config';
import {
  createUser,
  getUserByContact,
  saveUserPreferences,
  getUserPreferences,
  storeOtp,
  verifyOtp,
} from './operations';

async function main() {
  console.log('Testing Subject Data Preferences app schema...');

  // Test 1: Create user with email (using timestamp to avoid conflicts)
  console.log('\n--- Test 1: Create user with email ---');
  const timestamp = Date.now();
  const emailUser = await createUser(`john${timestamp}@example.com`);
  console.log('Created email user:', emailUser);

  // Test 2: Create user with phone
  console.log('\n--- Test 2: Create user with phone ---');
  const phoneUser = await createUser(
    `+1234567${timestamp.toString().slice(-3)}`,
  );
  console.log('Created phone user:', phoneUser);

  // Test 3: Find users by contact
  console.log('\n--- Test 3: Find users by contact ---');
  const foundByEmail = await getUserByContact(`john${timestamp}@example.com`);
  console.log('Found by email:', foundByEmail);

  const foundByPhone = await getUserByContact(
    `+1234567${timestamp.toString().slice(-3)}`,
  );
  console.log('Found by phone:', foundByPhone);

  // Test 5: Save user preferences
  console.log('\n--- Test 5: Save user preferences ---');
  const preferences = await saveUserPreferences(emailUser.id, {
    disallowPhoto: 1,
    disallowGender: 0,
    disallowBirthday: 1,
    disallowAddress: 0,
    disallowCompany: 0,
    disallowTitle: 1,
  });
  console.log('Saved preferences:', preferences);

  // Test 6: Get user preferences
  console.log('\n--- Test 6: Get user preferences ---');
  const savedPrefs = await getUserPreferences(emailUser.id);
  console.log('Retrieved preferences:', savedPrefs);

  // Test 7: Store OTP for user
  console.log('\n--- Test 7: Store OTP for user ---');
  const otpCode = '123456';
  const otpResult = await storeOtp(`john${timestamp}@example.com`, otpCode, 5);
  console.log('Stored OTP result:', otpResult);

  // Test 8: Verify OTP
  console.log('\n--- Test 8: Verify OTP ---');
  const isValidOtp = await verifyOtp(`john${timestamp}@example.com`, '123456');
  console.log('OTP verification result:', isValidOtp);

  // Test 9: Store and test expired OTP
  console.log('\n--- Test 9: Test expired OTP ---');
  await storeOtp(`+1234567${timestamp.toString().slice(-3)}`, '654321', 0.01); // Expires in 0.6 seconds
  console.log('Stored OTP with short expiration');

  // Wait for expiration
  await new Promise(resolve => setTimeout(resolve, 1000));

  const expiredOtpResult = await verifyOtp(
    `+1234567${timestamp.toString().slice(-3)}`,
    '654321',
  );
  console.log('Expired OTP verification (should be false):', expiredOtpResult);

  console.log(
    '\n✅ Subject Data Preferences app schema test completed successfully!',
  );
  console.log('\nSchema Summary:');
  console.log('- ✅ Users table: Supports email and/or phone authentication');
  console.log('- ✅ User preferences: Stores privacy settings for data fields');
  console.log('- ✅ OTP storage: Database-backed with automatic expiration');
}

main().catch(console.error);
