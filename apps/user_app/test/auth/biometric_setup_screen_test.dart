import 'package:flutter_test/flutter_test.dart';

import 'package:flutter_application_1/features/auth/auth_strings.dart';
import 'package:flutter_application_1/features/auth/biometric_setup_screen.dart';

import 'auth_harness.dart';

void main() {
  testWidgets('BiometricSetupScreen shows the enable state when available',
      (tester) async {
    await tester.pumpWidget(
      wrapScreen(
        const BiometricSetupScreen(),
        biometric: FakeBiometricService(available: true),
      ),
    );
    // Resolve the async availability check + the entrance animation.
    await tester.pump();
    await tester.pump(const Duration(milliseconds: 800));

    expect(find.text(AuthStrings.biometricEnableCta), findsOneWidget);
    expect(find.text(AuthStrings.biometricSkipCta), findsWidgets);
    expect(tester.takeException(), isNull);
  });

  testWidgets('BiometricSetupScreen shows the unavailable state gracefully',
      (tester) async {
    await tester.pumpWidget(
      wrapScreen(
        const BiometricSetupScreen(),
        biometric: FakeBiometricService(),
      ),
    );
    await tester.pump();
    await tester.pump(const Duration(milliseconds: 800));

    expect(find.text(AuthStrings.biometricUnavailableTitle), findsOneWidget);
    expect(tester.takeException(), isNull);
  });
}
