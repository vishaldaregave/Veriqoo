import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:go_router/go_router.dart';
import 'package:shared_core/design_system/design_system.dart';

import 'package:flutter_application_1/app/routes.dart';
import 'package:flutter_application_1/features/auth/auth_actions.dart';
import 'package:flutter_application_1/features/auth/auth_strings.dart';
import 'package:flutter_application_1/features/settings/settings_screen.dart';
import 'package:flutter_application_1/features/settings/settings_strings.dart';

import '../auth/auth_actions_fake.dart';

/// Mounts [SettingsScreen] at `/settings` with placeholder `/language` and
/// `/biometric-setup` targets, returning the injected [FakeAuthActions].
Future<FakeAuthActions> _pumpSettings(WidgetTester tester) async {
  final fakeAuth = FakeAuthActions();
  final router = GoRouter(
    initialLocation: AppRoutes.settingsPath,
    routes: <RouteBase>[
      GoRoute(
        path: AppRoutes.settingsPath,
        builder: (_, __) => const SettingsScreen(),
      ),
      GoRoute(
        path: AppRoutes.languagePath,
        builder: (_, __) => const Placeholder(),
      ),
      GoRoute(
        path: AppRoutes.biometricSetupPath,
        builder: (_, __) => const Placeholder(),
      ),
    ],
  );

  await tester.pumpWidget(
    ProviderScope(
      overrides: [authActionsProvider.overrideWithValue(fakeAuth)],
      child: MaterialApp.router(
        theme: VeriqooTheme.dark,
        routerConfig: router,
      ),
    ),
  );
  await tester.pump();
  return fakeAuth;
}

Finder _checkIn(String rowLabel) => find.descendant(
      of: find.ancestor(
        of: find.text(rowLabel),
        matching: find.byType(InkWell),
      ),
      matching: find.byIcon(VeriqooIcons.check),
    );

Finder _switchIn(String rowLabel) => find.descendant(
      of: find.ancestor(of: find.text(rowLabel), matching: find.byType(Row))
          .first,
      matching: find.byType(Switch),
    );

void main() {
  group('SettingsScreen', () {
    testWidgets('renders all five section headers', (tester) async {
      await _pumpSettings(tester);

      expect(find.text(SettingsStrings.appearanceSection.toUpperCase()),
          findsOneWidget);
      expect(find.text(SettingsStrings.languageSection.toUpperCase()),
          findsOneWidget);
      expect(find.text(SettingsStrings.notificationsSection.toUpperCase()),
          findsOneWidget);
      expect(find.text(SettingsStrings.privacySection.toUpperCase()),
          findsOneWidget);
      expect(find.text(AuthStrings.securitySection.toUpperCase()),
          findsOneWidget);
    });

    testWidgets('tapping Light moves the selected theme check', (tester) async {
      await _pumpSettings(tester);

      // Default mode is dark.
      expect(_checkIn(SettingsStrings.themeDark), findsOneWidget);
      expect(_checkIn(SettingsStrings.themeLight), findsNothing);

      await tester.tap(find.text(SettingsStrings.themeLight));
      await tester.pump();

      expect(_checkIn(SettingsStrings.themeLight), findsOneWidget);
      expect(_checkIn(SettingsStrings.themeDark), findsNothing);
    });

    testWidgets('shows the current language and navigates to the selector',
        (tester) async {
      await _pumpSettings(tester);

      // Default locale is English; the row shows the endonym (uppercased).
      expect(find.text('ENGLISH'), findsOneWidget);

      await tester.tap(find.text(SettingsStrings.languageRowLabel));
      await tester.pump();
      await tester.pump(const Duration(milliseconds: 50));

      expect(find.byType(Placeholder), findsOneWidget);
      expect(find.byType(SettingsScreen), findsNothing);
    });

    testWidgets('toggling a privacy switch flips its value', (tester) async {
      await _pumpSettings(tester);

      final shareSwitch = _switchIn(SettingsStrings.shareDiagnostics);
      expect(tester.widget<Switch>(shareSwitch).value, isFalse);

      await tester.tap(shareSwitch);
      await tester.pump();

      expect(tester.widget<Switch>(shareSwitch).value, isTrue);
    });

    testWidgets('tapping Sign out invokes the injected AuthActions',
        (tester) async {
      final fakeAuth = await _pumpSettings(tester);

      await tester.tap(find.text(AuthStrings.signOutCta));
      await tester.pump();

      expect(fakeAuth.signOutCount, 1);
    });
  });
}
