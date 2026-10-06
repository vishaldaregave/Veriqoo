import 'package:flutter/widgets.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:shared_core/design_system/design_system.dart';

import 'package:flutter_application_1/app/app.dart';
import 'package:flutter_application_1/features/auth/auth_controller.dart';
import 'package:flutter_application_1/features/auth/biometric_service.dart';
import 'package:flutter_application_1/features/auth/login_screen.dart';
import 'package:flutter_application_1/features/history/history_screen.dart';
import 'package:flutter_application_1/features/home/home_screen.dart';
import 'package:flutter_application_1/features/scan/scan_screen.dart';
import 'package:flutter_application_1/features/splash/splash_screen.dart';

import 'auth/auth_harness.dart';

/// Auth controller stand-in: returns an injected state from [build] and makes
/// [resolve] a no-op so the shell tests never touch `Supabase.instance`.
class FakeAuthController extends AuthController {
  FakeAuthController(this._initial);

  final AuthState _initial;

  @override
  AuthState build() => _initial;

  @override
  void resolve() {}
}

ProviderContainer _containerFor(AuthState initial) {
  return ProviderContainer(
    overrides: [
      authControllerProvider.overrideWith(() => FakeAuthController(initial)),
      // The splash now reads the biometric service; keep it disabled + off a
      // platform channel so the shell tests stay hermetic.
      biometricServiceProvider.overrideWithValue(FakeBiometricService()),
    ],
  );
}

Widget _appWith(ProviderContainer container) {
  return UncontrolledProviderScope(
    container: container,
    child: const VeriqooApp(),
  );
}

Finder _navLabel(String upperLabel) => find.descendant(
      of: find.byType(VeriqooNavigationBar),
      matching: find.text(upperLabel),
    );

void main() {
  testWidgets('boots to splash, then redirects to login with no session',
      (tester) async {
    final container = _containerFor(AuthState.unknown);
    addTearDown(container.dispose);

    await tester.pumpWidget(_appWith(container));
    await tester.pump();

    // Unknown auth holds on the splash — no login flash.
    expect(find.byType(SplashScreen), findsOneWidget);
    expect(find.byType(LoginScreen), findsNothing);

    // Session resolves to "no session": redirect to the login screen.
    container
        .read(authControllerProvider.notifier)
        .set(AuthState.unauthenticated);
    await tester.pump();
    await tester.pump(const Duration(milliseconds: 400));

    expect(find.byType(LoginScreen), findsOneWidget);
    expect(find.byType(SplashScreen), findsNothing);
  });

  testWidgets('authenticated boot lands on home (no splash flash)',
      (tester) async {
    final container = _containerFor(AuthState.authenticated);
    addTearDown(container.dispose);

    await tester.pumpWidget(_appWith(container));
    await tester.pump();
    await tester.pump(const Duration(milliseconds: 400));

    expect(find.byType(HomeScreen), findsOneWidget);
  });

  testWidgets('nav bar switches branches (and mounts the scan pipeline)',
      (tester) async {
    final container = _containerFor(AuthState.authenticated);
    addTearDown(container.dispose);

    await tester.pumpWidget(_appWith(container));
    await tester.pump();
    await tester.pump(const Duration(milliseconds: 400));
    expect(find.byType(HomeScreen), findsOneWidget);

    // Home -> History.
    await tester.tap(_navLabel('HISTORY'));
    await tester.pump();
    await tester.pump(const Duration(milliseconds: 400));
    expect(find.byType(HistoryScreen), findsOneWidget);

    // History -> Scan. Proves the carried-forward ScanScreen mounts at /scan.
    await tester.tap(_navLabel('SCAN'));
    await tester.pump();
    await tester.pump(const Duration(milliseconds: 400));
    expect(find.byType(ScanScreen), findsOneWidget);
  });
}
