import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';


import 'package:flutter_application_1/app/not_found_screen.dart';
import 'package:flutter_application_1/app/routes.dart';
import 'package:flutter_application_1/app/transitions.dart';
import 'package:flutter_application_1/features/auth/auth_controller.dart';
import 'package:flutter_application_1/features/auth/biometric_setup_screen.dart';
import 'package:flutter_application_1/features/auth/forgot_password_screen.dart';
import 'package:flutter_application_1/features/auth/login_screen.dart';
import 'package:flutter_application_1/features/auth/otp_screen.dart';
import 'package:flutter_application_1/features/auth/reset_password_screen.dart';
import 'package:flutter_application_1/features/auth/signup_screen.dart';
import 'package:flutter_application_1/features/history/history_detail_screen.dart';
import 'package:flutter_application_1/features/history/history_screen.dart';
import 'package:flutter_application_1/features/home/home_screen.dart';
import 'package:flutter_application_1/features/consumer_protection/ad_detector_screen.dart';
import 'package:flutter_application_1/features/consumer_protection/consumer_protection_screen.dart';
import 'package:flutter_application_1/features/consumer_protection/heatmap_screen.dart';
import 'package:flutter_application_1/features/consumer_protection/report_qr_screen.dart';
import 'package:flutter_application_1/features/notifications/notifications_screen.dart';
import 'package:flutter_application_1/features/products/product_detail_screen.dart';
import 'package:flutter_application_1/features/profile/profile_screen.dart';
import 'package:flutter_application_1/features/reports/compliance_report_screen.dart';
import 'package:flutter_application_1/features/reports/detailed_report_screen.dart';
import 'package:flutter_application_1/features/reports/regulatory_library_screen.dart';
import 'package:flutter_application_1/features/reports/report_detail_screen.dart';
import 'package:flutter_application_1/features/reports/report_issue_screen.dart';
import 'package:flutter_application_1/features/reports/saved_reports_screen.dart';
import 'package:flutter_application_1/features/scan/analysis_result_screen.dart';
import 'package:flutter_application_1/features/scan/evidence/evidence_viewer_args.dart';
import 'package:flutter_application_1/features/scan/evidence/evidence_viewer_screen.dart';
import 'package:flutter_application_1/features/scan/scan_capture_screen.dart';
import 'package:flutter_application_1/features/scan/scan_processing_screen.dart';
import 'package:flutter_application_1/features/scan/scan_screen.dart';
import 'package:flutter_application_1/features/search/search_screen.dart';
import 'package:flutter_application_1/features/settings/language_screen.dart';
import 'package:flutter_application_1/features/settings/settings_screen.dart';
import 'package:flutter_application_1/features/splash/splash_screen.dart';
import 'package:flutter_application_1/shell/app_shell.dart';

/// Root navigator key — used for top-level routes that present over the shell.
final rootNavigatorKey = GlobalKey<NavigatorState>();

/// The app router. Exposed as a provider so the guard can read Riverpod auth
/// state; a [ValueNotifier] bumped on auth-state changes refreshes the redirect
/// without rebuilding the whole router (which would drop navigation state).
final goRouterProvider = Provider<GoRouter>((ref) {
  final refresh = ValueNotifier<int>(0);
  ref.onDispose(refresh.dispose);
  ref.listen(authControllerProvider, (_, __) => refresh.value++);

  return GoRouter(
    navigatorKey: rootNavigatorKey,
    initialLocation: AppRoutes.splashPath,
    refreshListenable: refresh,
    redirect: (context, state) {
      final loc = state.matchedLocation;
      final onSplash = loc == AppRoutes.splashPath;
      final onAuth = loc.startsWith('/auth');

      if (onSplash || onAuth) {
        return AppRoutes.homePath;
      }
      return null;
    },
    errorBuilder: (context, state) =>
        NotFoundScreen(location: state.uri.toString()),
    routes: [
      // --- Splash ---
      GoRoute(
        path: AppRoutes.splashPath,
        name: AppRoutes.splashName,
        builder: (context, state) => const SplashScreen(),
      ),

      // --- Auth (top-level) ---
      GoRoute(
        path: AppRoutes.loginPath,
        name: AppRoutes.loginName,
        builder: (context, state) => const LoginScreen(),
      ),
      GoRoute(
        path: AppRoutes.signupPath,
        name: AppRoutes.signupName,
        builder: (context, state) => const SignupScreen(),
      ),
      GoRoute(
        path: AppRoutes.otpPath,
        name: AppRoutes.otpName,
        builder: (context, state) =>
            OtpScreen(email: state.uri.queryParameters['email']),
      ),
      GoRoute(
        path: AppRoutes.forgotPasswordPath,
        name: AppRoutes.forgotPasswordName,
        builder: (context, state) => const ForgotPasswordScreen(),
      ),
      GoRoute(
        path: AppRoutes.resetPasswordPath,
        name: AppRoutes.resetPasswordName,
        builder: (context, state) => const ResetPasswordScreen(),
      ),

      // --- Top-level routes presented over the shell ---
      GoRoute(
        path: AppRoutes.regulatoryLibraryPath,
        name: AppRoutes.regulatoryLibraryName,
        builder: (context, state) => const RegulatoryLibraryScreen(),
      ),
      GoRoute(
        path: AppRoutes.complianceReportPath,
        name: AppRoutes.complianceReportName,
        builder: (context, state) => ComplianceReportScreen(
          args: state.extra as AnalysisResultArgs?,
        ),
      ),
      GoRoute(
        path: AppRoutes.detailedReportPath,
        name: AppRoutes.detailedReportName,
        builder: (context, state) {
          final args = state.extra as AnalysisResultArgs?;
          if (args != null) {
            return DetailedReportScreen(args: args);
          }
          return const _ScanResultPlaceholder();
        },
      ),
      GoRoute(
        path: AppRoutes.productDetailPath,
        name: AppRoutes.productDetailName,
        pageBuilder: (context, state) => sharedAxisPage(
          context: context,
          key: state.pageKey,
          child: ProductDetailScreen(id: state.pathParameters['id'] ?? ''),
        ),
      ),
      GoRoute(
        path: AppRoutes.reportDetailPath,
        name: AppRoutes.reportDetailName,
        pageBuilder: (context, state) => sharedAxisPage(
          context: context,
          key: state.pageKey,
          child: ReportDetailScreen(id: state.pathParameters['id'] ?? ''),
        ),
      ),
      GoRoute(
        path: AppRoutes.reportIssuePath,
        name: AppRoutes.reportIssueName,
        builder: (context, state) => const ReportIssueScreen(),
      ),
      GoRoute(
        path: AppRoutes.settingsPath,
        name: AppRoutes.settingsName,
        builder: (context, state) => const SettingsScreen(),
      ),
      GoRoute(
        path: AppRoutes.languagePath,
        name: AppRoutes.languageName,
        builder: (context, state) => const LanguageScreen(),
      ),
      GoRoute(
        path: AppRoutes.biometricSetupPath,
        name: AppRoutes.biometricSetupName,
        builder: (context, state) => const BiometricSetupScreen(),
      ),
      GoRoute(
        path: AppRoutes.notificationsPath,
        name: AppRoutes.notificationsName,
        builder: (context, state) => const NotificationsScreen(),
      ),
      GoRoute(
        path: AppRoutes.searchPath,
        name: AppRoutes.searchName,
        pageBuilder: (context, state) => sharedAxisPage(
          context: context,
          key: state.pageKey,
          child: const SearchScreen(),
        ),
      ),

      // --- Dedicated Scanner Instrument (Top-level full-screen modal) ---
      GoRoute(
        path: AppRoutes.scanPath,
        name: AppRoutes.scanName,
        builder: (context, state) => const ScanScreen(),
        routes: [
          GoRoute(
            path: AppRoutes.scanCaptureSegment,
            name: AppRoutes.scanCaptureName,
            builder: (context, state) => const ScanCaptureScreen(),
          ),
          GoRoute(
            path: AppRoutes.scanProcessingSegment,
            name: AppRoutes.scanProcessingName,
            builder: (context, state) => const ScanProcessingScreen(),
          ),
          GoRoute(
            path: AppRoutes.scanResultSegment,
            name: AppRoutes.scanResultName,
            builder: (context, state) {
              final args = state.extra as AnalysisResultArgs?;
              if (args != null) {
                return AnalysisResultScreen(args: args);
              }
              return const _ScanResultPlaceholder();
            },
          ),
          GoRoute(
            path: AppRoutes.scanEvidenceSegment,
            name: AppRoutes.scanEvidenceName,
            builder: (context, state) => EvidenceViewerScreen(
              args: state.extra as EvidenceViewerArgs? ??
                  const EvidenceViewerArgs(),
            ),
          ),
        ],
      ),

      // --- Dedicated Consumer Protection Hub ---
      GoRoute(
        path: AppRoutes.consumerProtectionPath,
        name: AppRoutes.consumerProtectionName,
        builder: (context, state) => const ConsumerProtectionScreen(),
        routes: [
          GoRoute(
            path: 'ad-detector',
            name: AppRoutes.adDetectorName,
            builder: (context, state) => const AdDetectorScreen(),
          ),
          GoRoute(
            path: 'heatmap',
            name: AppRoutes.heatmapName,
            builder: (context, state) => const HeatmapScreen(),
          ),
          GoRoute(
            path: 'report-qr',
            name: AppRoutes.reportQrName,
            builder: (context, state) => const ReportQrScreen(),
          ),
        ],
      ),

      // --- The four-branch bottom-nav shell matching the design board ---
      StatefulShellRoute.indexedStack(
        builder: (context, state, navigationShell) =>
            AppShell(navigationShell: navigationShell),
        branches: [
          // Branch 0 — Home
          StatefulShellBranch(
            routes: [
              GoRoute(
                path: AppRoutes.homePath,
                name: AppRoutes.homeName,
                pageBuilder: (context, state) => fadePage(
                  context: context,
                  key: state.pageKey,
                  child: const HomeScreen(),
                ),
              ),
            ],
          ),

          // Branch 1 — History (+ nested detail)
          StatefulShellBranch(
            routes: [
              GoRoute(
                path: AppRoutes.historyPath,
                name: AppRoutes.historyName,
                builder: (context, state) => const HistoryScreen(),
                routes: [
                  GoRoute(
                    path: AppRoutes.historyDetailSegment,
                    name: AppRoutes.historyDetailName,
                    pageBuilder: (context, state) => sharedAxisPage(
                      context: context,
                      key: state.pageKey,
                      child: HistoryDetailScreen(
                        id: state.pathParameters['id'] ?? '',
                      ),
                    ),
                  ),
                ],
              ),
            ],
          ),

          // Branch 2 — Reports (Saved compliance reports / dossiers)
          StatefulShellBranch(
            routes: [
              GoRoute(
                path: AppRoutes.reportsPath,
                name: AppRoutes.reportsName,
                builder: (context, state) => const SavedReportsScreen(),
              ),
            ],
          ),

          // Branch 3 — More / Profile
          StatefulShellBranch(
            routes: [
              GoRoute(
                path: AppRoutes.profilePath,
                name: AppRoutes.profileName,
                builder: (context, state) => const ProfileScreen(),
              ),
            ],
          ),
        ],
      ),
    ],
  );
});

/// Shown at `/scan/result` when navigated to without analysis args.
class _ScanResultPlaceholder extends StatelessWidget {
  const _ScanResultPlaceholder();

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: Colors.white,
      appBar: AppBar(title: const Text('Analysis')),
      body: const SafeArea(
        child: Center(
          child: Text('Run a scan to see results here.'),
        ),
      ),
    );
  }
}
