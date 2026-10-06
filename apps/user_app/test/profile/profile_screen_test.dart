import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:go_router/go_router.dart';
import 'package:shared_core/design_system/design_system.dart';

import 'package:flutter_application_1/app/routes.dart';
import 'package:flutter_application_1/features/auth/auth_actions.dart';
import 'package:flutter_application_1/features/home/home_user.dart';
import 'package:flutter_application_1/features/inspections/inspections_providers.dart';
import 'package:flutter_application_1/features/profile/profile_providers.dart';
import 'package:flutter_application_1/features/profile/profile_screen.dart';
import 'package:flutter_application_1/features/profile/profile_strings.dart';

import '../auth/auth_actions_fake.dart';
import '../home/home_harness.dart';

/// Mounts [ProfileScreen] at `/profile` under a minimal router with
/// placeholder navigation targets. Never `pumpAndSettle` — the
/// VerificationPulse backdrop loops forever.
Future<FakeAuthActions> _pumpProfile(
  WidgetTester tester, {
  bool verified = true,
}) async {
  final fakeAuth = FakeAuthActions();
  final router = GoRouter(
    initialLocation: AppRoutes.profilePath,
    routes: <RouteBase>[
      GoRoute(
        path: AppRoutes.profilePath,
        builder: (_, __) => const ProfileScreen(),
      ),
      GoRoute(
        path: AppRoutes.historyPath,
        builder: (_, __) => const Placeholder(),
      ),
      GoRoute(
        path: AppRoutes.notificationsPath,
        builder: (_, __) => const Placeholder(),
      ),
      GoRoute(
        path: AppRoutes.settingsPath,
        builder: (_, __) => const Placeholder(),
      ),
    ],
  );

  await tester.pumpWidget(
    ProviderScope(
      overrides: [
        currentUserProvider.overrideWithValue(
          const HomeUser(name: 'Ada Lovelace', email: 'ada@example.com'),
        ),
        accountVerifiedProvider.overrideWithValue(verified),
        authActionsProvider.overrideWithValue(fakeAuth),
        inspectionsRepositoryProvider
            .overrideWithValue(FakeInspectionsRepository()),
      ],
      child: MaterialApp.router(
        theme: VeriqooTheme.dark,
        routerConfig: router,
      ),
    ),
  );
  await tester.pump();
  await tester.pump(const Duration(milliseconds: 50));
  return fakeAuth;
}

void main() {
  group('ProfileScreen', () {
    testWidgets('renders the signed-in identity', (tester) async {
      await _pumpProfile(tester);

      expect(find.text('Ada Lovelace'), findsOneWidget);
      expect(find.text('ada@example.com'), findsOneWidget);
      expect(tester.takeException(), isNull);
    });

    testWidgets('shows the VERIFIED chip when the account is verified',
        (tester) async {
      await _pumpProfile(tester, verified: true);

      expect(find.byType(VeriqooStatus), findsOneWidget);
      expect(find.text(VeriqooStatusKind.verified.label), findsOneWidget);
      expect(find.text(ProfileStrings.verifiedCaption), findsOneWidget);
    });

    testWidgets('shows the FLAG chip when the account is unverified',
        (tester) async {
      await _pumpProfile(tester, verified: false);

      expect(find.text(VeriqooStatusKind.flag.label), findsOneWidget);
      expect(find.text(ProfileStrings.unverifiedCaption), findsOneWidget);
    });

    testWidgets('renders every navigation row label', (tester) async {
      await _pumpProfile(tester);

      expect(find.text(ProfileStrings.myProducts), findsOneWidget);
      expect(find.text(ProfileStrings.inspectionHistory), findsOneWidget);
      expect(find.text(ProfileStrings.notifications), findsOneWidget);
      expect(find.text(ProfileStrings.settings), findsOneWidget);
      expect(find.text(ProfileStrings.help), findsOneWidget);
      expect(find.text(ProfileStrings.signOut), findsOneWidget);
    });

    testWidgets('tapping Sign out invokes the injected AuthActions',
        (tester) async {
      final fakeAuth = await _pumpProfile(tester);

      await tester.tap(find.text(ProfileStrings.signOut));
      await tester.pump();

      expect(fakeAuth.signOutCount, 1);
    });
  });
}
