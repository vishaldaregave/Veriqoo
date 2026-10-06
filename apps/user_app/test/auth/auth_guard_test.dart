import 'package:flutter/widgets.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';

import 'package:flutter_application_1/app/app.dart';
import 'package:flutter_application_1/features/auth/auth_controller.dart';
import 'package:flutter_application_1/features/auth/auth_strings.dart';
import 'package:flutter_application_1/features/auth/biometric_service.dart';
import 'package:flutter_application_1/features/auth/login_screen.dart';
import 'package:flutter_application_1/features/home/home_screen.dart';

import 'auth_harness.dart';

/// Auth controller stand-in: returns an injected state from [build] and makes
/// [resolve] a no-op so the guard tests never touch `Supabase.instance`.
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

void main() {
  testWidgets('unauthenticated boot routes to login', (tester) async {
    final container = _containerFor(AuthState.unauthenticated);
    addTearDown(container.dispose);

    await tester.pumpWidget(_appWith(container));
    await tester.pump();
    await tester.pump(const Duration(milliseconds: 400));

    expect(find.byType(LoginScreen), findsOneWidget);
    expect(find.byType(HomeScreen), findsNothing);
  });

  testWidgets('authenticated boot routes to home', (tester) async {
    final container = _containerFor(AuthState.authenticated);
    addTearDown(container.dispose);

    await tester.pumpWidget(_appWith(container));
    await tester.pump();
    await tester.pump(const Duration(milliseconds: 400));

    expect(find.byType(HomeScreen), findsOneWidget);
    expect(find.byType(LoginScreen), findsNothing);
  });

  testWidgets('sign-out transition redirects back to login', (tester) async {
    final container = _containerFor(AuthState.authenticated);
    addTearDown(container.dispose);

    await tester.pumpWidget(_appWith(container));
    await tester.pump();
    await tester.pump(const Duration(milliseconds: 400));
    expect(find.byType(HomeScreen), findsOneWidget);

    // Simulate sign-out: the controller flips to unauthenticated and the guard
    // redirect returns to the login screen.
    container
        .read(authControllerProvider.notifier)
        .set(AuthState.unauthenticated);
    await tester.pump();
    await tester.pump(const Duration(milliseconds: 400));

    expect(find.byType(LoginScreen), findsOneWidget);
    expect(find.byType(HomeScreen), findsNothing);
  });

  testWidgets('login screen has no dev bypass control', (tester) async {
    final container = _containerFor(AuthState.unauthenticated);
    addTearDown(container.dispose);

    await tester.pumpWidget(_appWith(container));
    await tester.pump();
    await tester.pump(const Duration(milliseconds: 400));

    expect(find.byType(LoginScreen), findsOneWidget);
    expect(find.text('Enter app (dev)'), findsNothing);
    expect(find.text(AuthStrings.loginSignInCta), findsWidgets);
    expect(find.text(AuthStrings.loginGoogleCta), findsOneWidget);
    expect(find.text(AuthStrings.loginCreateAccountCta), findsOneWidget);
  });
}
