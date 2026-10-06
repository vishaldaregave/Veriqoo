import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

import 'package:flutter_application_1/features/auth/auth_strings.dart';
import 'package:flutter_application_1/features/auth/forgot_password_screen.dart';

import 'auth_harness.dart';

void main() {
  testWidgets('ForgotPasswordScreen pumps and accepts input without exceptions',
      (tester) async {
    await tester.pumpWidget(wrapScreen(const ForgotPasswordScreen()));
    await tester.pump(const Duration(milliseconds: 800));

    final field = find.byType(TextField);
    expect(field, findsOneWidget);

    await tester.enterText(field, 'ada@example.com');
    await tester.pump(const Duration(milliseconds: 50));

    expect(find.text(AuthStrings.forgotSendCta), findsWidgets);
    expect(tester.takeException(), isNull);
  });
}
