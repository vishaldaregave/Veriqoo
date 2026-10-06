import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

import 'package:flutter_application_1/features/auth/auth_strings.dart';
import 'package:flutter_application_1/features/auth/login_screen.dart';

import 'auth_harness.dart';

void main() {
  testWidgets('LoginScreen pumps and accepts input without exceptions',
      (tester) async {
    await tester.pumpWidget(wrapScreen(const LoginScreen()));
    // Advance past the entrance animation without settling (the cinematic
    // background loops forever, so pumpAndSettle would hang).
    await tester.pump(const Duration(milliseconds: 800));

    final fields = find.byType(TextField);
    expect(fields, findsNWidgets(2));

    await tester.enterText(fields.first, 'user@example.com');
    await tester.enterText(fields.last, 'hunter2password');
    await tester.pump(const Duration(milliseconds: 50));

    // Never tapped submit, so Supabase was never contacted.
    expect(tester.takeException(), isNull);
  });

  testWidgets('LoginScreen shows real controls and no dev bypass',
      (tester) async {
    await tester.pumpWidget(wrapScreen(const LoginScreen()));
    await tester.pump(const Duration(milliseconds: 800));

    // The Phase 2 TEMP dev bypass must be gone.
    expect(find.text('Enter app (dev)'), findsNothing);

    // The real auth controls are present.
    expect(find.text(AuthStrings.loginSignInCta), findsWidgets);
    expect(find.text(AuthStrings.loginGoogleCta), findsOneWidget);
    expect(find.text(AuthStrings.loginCreateAccountCta), findsOneWidget);
    expect(find.text(AuthStrings.loginForgotCta), findsOneWidget);
  });
}
