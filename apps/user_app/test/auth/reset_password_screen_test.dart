import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

import 'package:flutter_application_1/features/auth/auth_strings.dart';
import 'package:flutter_application_1/features/auth/reset_password_screen.dart';

import 'auth_harness.dart';

void main() {
  testWidgets('ResetPasswordScreen pumps and accepts input without exceptions',
      (tester) async {
    await tester.pumpWidget(wrapScreen(const ResetPasswordScreen()));
    await tester.pump(const Duration(milliseconds: 800));

    final fields = find.byType(TextField);
    expect(fields, findsNWidgets(2));

    await tester.enterText(fields.first, 'newpassword123');
    await tester.enterText(fields.last, 'newpassword123');
    await tester.pump(const Duration(milliseconds: 50));

    expect(find.text(AuthStrings.resetUpdateCta), findsWidgets);
    expect(tester.takeException(), isNull);
  });
}
