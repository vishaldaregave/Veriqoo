import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

import 'package:flutter_application_1/features/auth/auth_strings.dart';
import 'package:flutter_application_1/features/auth/signup_screen.dart';

import 'auth_harness.dart';

void main() {
  testWidgets('SignupScreen pumps and accepts input without exceptions',
      (tester) async {
    await tester.pumpWidget(wrapScreen(const SignupScreen()));
    await tester.pump(const Duration(milliseconds: 800));

    final fields = find.byType(TextField);
    expect(fields, findsNWidgets(4));

    await tester.enterText(fields.at(0), 'Ada Lovelace');
    await tester.enterText(fields.at(1), 'ada@example.com');
    await tester.enterText(fields.at(2), 'hunter2password');
    await tester.enterText(fields.at(3), 'hunter2password');
    await tester.pump(const Duration(milliseconds: 50));

    expect(find.text(AuthStrings.signupCreateCta), findsWidgets);
    expect(tester.takeException(), isNull);
  });
}
