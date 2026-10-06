/// Centralized, user-facing copy for the six-screen authentication family.
///
/// Phase 8 will localize the app. To keep that migration mechanical, every
/// string the auth flow renders lives here as a flat `static const` — no copy
/// is hard-coded inside a screen. Members are grouped by screen with a clear
/// prefix (`login*`, `signup*`, `otp*`, `forgot*`, `reset*`, `biometric*`) plus
/// a shared `err*` group for inline error messaging.
///
/// Keep button labels and field labels SHORT: [VeriqooButton] ellipsizes and
/// `Text` wraps, so longer translations degrade gracefully rather than breaking
/// layout. Avoid baking width assumptions into any string here.
abstract final class AuthStrings {
  const AuthStrings._();

  // --- Brand ---
  static const String wordmark = 'VERIQOO';
  static const String tagline = 'Packaged-product compliance verification.';

  // --- Login ---
  static const String loginTitle = 'Sign in';
  static const String loginSubtitle = 'Welcome back. Verify with confidence.';
  static const String loginEmailLabel = 'Email';
  static const String loginEmailHint = 'you@example.com';
  static const String loginPasswordLabel = 'Password';
  static const String loginPasswordHint = 'Your password';
  static const String loginForgotCta = 'Forgot password?';
  static const String loginSignInCta = 'Sign in';
  static const String loginGoogleCta = 'Continue with Google';
  static const String loginOrDivider = 'OR';
  static const String loginCreateAccountCta = 'Create an account';

  // --- Signup ---
  static const String signupTitle = 'Create account';
  static const String signupSubtitle = 'Set up your VERIQOO identity.';
  static const String signupNameLabel = 'Name';
  static const String signupNameHint = 'Your full name';
  static const String signupEmailLabel = 'Email';
  static const String signupEmailHint = 'you@example.com';
  static const String signupPasswordLabel = 'Password';
  static const String signupPasswordHint = 'At least 8 characters';
  static const String signupConfirmLabel = 'Confirm password';
  static const String signupConfirmHint = 'Re-enter your password';
  static const String signupCreateCta = 'Create account';
  static const String signupHaveAccountCta = 'Already have an account? Sign in';
  static const String signupCheckEmailTitle = 'Check your email';
  static const String signupCheckEmailBody =
      'We sent a confirmation link to your inbox. Open it to finish setting '
      'up your account.';

  // --- OTP verification ---
  static const String otpTitle = 'VERIFY YOUR IDENTITY';
  static const String otpSubtitle =
      'Enter the six-digit code we sent to your email.';
  static const String otpVerifyCta = 'Verify';
  static const String otpResendCta = 'Resend code';
  static const String otpResendIn = 'Resend code in';
  static const String otpChangeEmailCta = 'Change email';
  static const String otpMissingEmail =
      'We could not determine which email to verify. Go back and try again.';

  // --- Forgot password ---
  static const String forgotTitle = 'Reset password';
  static const String forgotSubtitle =
      'Enter your email and we will send a reset link.';
  static const String forgotEmailLabel = 'Email';
  static const String forgotEmailHint = 'you@example.com';
  static const String forgotSendCta = 'Send reset link';
  static const String forgotSentTitle = 'Check your email';
  static const String forgotSentBody =
      'If an account exists for that address, a password reset link is on its '
      'way.';
  static const String forgotBackToSignInCta = 'Back to sign in';

  // --- Reset password ---
  static const String resetTitle = 'New password';
  static const String resetSubtitle = 'Choose a new password for your account.';
  static const String resetNewPasswordLabel = 'New password';
  static const String resetNewPasswordHint = 'At least 8 characters';
  static const String resetConfirmLabel = 'Confirm password';
  static const String resetConfirmHint = 'Re-enter your new password';
  static const String resetUpdateCta = 'Update password';
  static const String resetSuccessTitle = 'Password updated';
  static const String resetSuccessBody =
      'Your password has been changed. You can now sign in with it.';
  static const String resetContinueCta = 'Continue';

  // --- Biometric setup / unlock ---
  static const String biometricTitle = 'Biometric unlock';
  static const String biometricEnableBody =
      'Use your fingerprint or face to unlock VERIQOO faster next time.';
  static const String biometricEnableCta = 'Enable biometric unlock';
  static const String biometricSkipCta = 'Not now';
  static const String biometricUnavailableTitle = 'Not available';
  static const String biometricUnavailableBody =
      'This device does not have biometric unlock set up. You can enable it '
      'later from Settings once a fingerprint or face is enrolled.';
  static const String biometricEnabledTitle = 'Biometric unlock on';
  static const String biometricEnabledBody =
      'You can now unlock VERIQOO with your fingerprint or face.';
  static const String biometricReason = 'Verify your identity to continue';
  static const String biometricUnlockCta = 'Unlock with biometrics';
  static const String biometricDoneCta = 'Done';

  // --- Settings: security section (auth-adjacent entries) ---
  static const String securitySection = 'Security';
  static const String signOutCta = 'Sign out';

  // --- Inline errors ---
  static const String errGeneric = 'Something went wrong. Please try again.';
  static const String errEmptyFields = 'Please fill in all fields.';
  static const String errInvalidEmail = 'Enter a valid email address.';
  static const String errNameRequired = 'Enter your name.';
  static const String errPasswordTooShort =
      'Password must be at least 8 characters.';
  static const String errWeakPassword =
      'That password is too weak. Try a longer one.';
  static const String errPasswordMismatch = 'Passwords do not match.';
  static const String errOtpIncomplete = 'Enter the full six-digit code.';
  static const String errOauthUnavailable =
      'Google sign-in is not available right now. Please use email instead.';
  static const String errBiometricFailed =
      'Could not verify. Please try again.';
}
