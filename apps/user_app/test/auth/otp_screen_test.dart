import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

import 'package:flutter_application_1/features/auth/auth_strings.dart';
import 'package:flutter_application_1/features/auth/otp_screen.dart';

import 'auth_harness.dart';

void main() {
  testWidgets('OtpScreen pumps and accepts a six-digit code without exceptions',
      (tester) async {
    await tester.pumpWidget(
      wrapScreen(const OtpScreen(email: 'ada@example.com')),
    );
    await tester.pump(const Duration(milliseconds: 800));

    expect(find.text(AuthStrings.otpTitle), findsOneWidget);

    // Enter the full code; onCompleted only stores it — it must NOT auto-submit
    // (so Supabase is never contacted here).
    final field = find.byType(TextField);
    expect(field, findsOneWidget);
    await tester.enterText(field, '123456');
    await tester.pump(const Duration(milliseconds: 50));

    expect(find.text(AuthStrings.otpVerifyCta), findsWidgets);
    expect(tester.takeException(), isNull);
  });
}
