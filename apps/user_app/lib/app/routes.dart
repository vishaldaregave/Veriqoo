/// Centralized route paths and names for the user_app shell.
///
/// Paths are the literal locations GoRouter matches; names are stable
/// identifiers for `context.goNamed` / `pushNamed`. Keeping them here avoids
/// stringly-typed drift across the app.
abstract final class AppRoutes {
  const AppRoutes._();

  // Splash.
  static const splashPath = '/splash';
  static const splashName = 'splash';

  // Auth.
  static const loginPath = '/auth/login';
  static const loginName = 'login';
  static const signupPath = '/auth/signup';
  static const signupName = 'signup';
  static const otpPath = '/auth/otp';
  static const otpName = 'otp';
  static const forgotPasswordPath = '/auth/forgot-password';
  static const forgotPasswordName = 'forgotPassword';
  static const resetPasswordPath = '/auth/reset';
  static const resetPasswordName = 'resetPassword';

  // Shell branches.
  static const homePath = '/home';
  static const homeName = 'home';
  static const scanPath = '/scan';
  static const scanName = 'scan';
  static const consumerProtectionPath = '/consumer-protection';
  static const consumerProtectionName = 'consumerProtection';
  static const historyPath = '/history';
  static const historyName = 'history';
  static const profilePath = '/profile';
  static const profileName = 'profile';

  // Consumer Protection sub-routes
  static const adDetectorPath = '/consumer-protection/ad-detector';
  static const adDetectorName = 'adDetector';
  static const heatmapPath = '/consumer-protection/heatmap';
  static const heatmapName = 'heatmap';
  static const reportQrPath = '/consumer-protection/report-qr';
  static const reportQrName = 'reportQr';

  // Scan branch children (relative sub-paths + absolute helpers).
  static const scanCaptureSegment = 'capture';
  static const scanCapturePath = '/scan/capture';
  static const scanCaptureName = 'scanCapture';
  static const scanProcessingSegment = 'processing';
  static const scanProcessingPath = '/scan/processing';
  static const scanProcessingName = 'scanProcessing';
  static const scanResultSegment = 'result';
  static const scanResultPath = '/scan/result';
  static const scanResultName = 'scanResult';
  static const scanEvidenceSegment = 'evidence';
  static const scanEvidencePath = '/scan/evidence';
  static const scanEvidenceName = 'scanEvidence';

  // History branch child.
  static const historyDetailSegment = ':id';
  static const historyDetailName = 'historyDetail';
  static String historyDetail(String id) => '/history/$id';

  // Top-level routes over the shell.
  static const reportsPath = '/reports';
  static const reportsName = 'reports';
  static const regulatoryLibraryPath = '/regulatory-library';
  static const regulatoryLibraryName = 'regulatoryLibrary';
  static const complianceReportPath = '/compliance-report';
  static const complianceReportName = 'complianceReport';
  static const detailedReportPath = '/detailed-report';
  static const detailedReportName = 'detailedReport';

  static const productDetailPath = '/products/:id';
  static const productDetailName = 'productDetail';
  static String productDetail(String id) => '/products/$id';
  static const reportDetailPath = '/reports/:id';
  static const reportDetailName = 'reportDetail';
  static String reportDetail(String id) => '/reports/$id';
  static const reportIssuePath = '/report-issue';
  static const reportIssueName = 'reportIssue';
  static const settingsPath = '/settings';
  static const settingsName = 'settings';
  static const languagePath = '/language';
  static const languageName = 'language';
  static const notificationsPath = '/notifications';
  static const notificationsName = 'notifications';

  // Search — top-level, presented over the shell.
  static const searchPath = '/search';
  static const searchName = 'search';

  // Biometric setup — top-level (post-login) so the guard does not bounce it
  // off `/auth/*`.
  static const biometricSetupPath = '/biometric-setup';
  static const biometricSetupName = 'biometricSetup';
}

