/// Centralized, user-facing copy for the Profile screen.
///
/// Every string the Profile screen renders lives here as a flat `static const`
/// (matching `auth_strings.dart`) so a later localization phase can migrate
/// copy mechanically. Keep labels short — nav rows ellipsize.
abstract final class ProfileStrings {
  const ProfileStrings._();

  // --- Screen ---
  static const String title = 'Profile';

  // --- Identity ---
  static const String fallbackName = 'VERIQOO inspector';
  static const String verifiedCaption = 'Email verified';
  static const String unverifiedCaption = 'Email not verified';

  // --- Section headers (uppercased by VeriqooSectionHeader) ---
  static const String activitySection = 'Activity';
  static const String generalSection = 'General';
  static const String supportSection = 'Support';

  // --- Nav row labels ---
  static const String myProducts = 'My products';
  static const String inspectionHistory = 'Inspection history';
  static const String notifications = 'Notifications';
  static const String settings = 'Settings';
  static const String help = 'Help & support';
  static const String signOut = 'Sign out';

  // --- Help & Support sheet ---
  static const String helpSheetTitle = 'Help & support';
  static const String helpSheetBody =
      'Scan a product to verify its packaged-compliance details, then review '
      'the report. Flag anything that looks off and an authority can respond.';
  static const String helpSheetContact =
      'Need a hand? Reach the VERIQOO team at support@veriqoo.app.';
}
