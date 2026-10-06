import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:shared_core/design_system/design_system.dart';

void main() {
  group('VERIQOO design gallery', () {
    testWidgets('DesignGallery pumps without throwing', (tester) async {
      await tester.pumpWidget(
        MaterialApp(
          theme: VeriqooTheme.dark,
          home: const DesignGallery(),
        ),
      );

      // Let the count-up / scan / painter animations run a frame or so.
      await tester.pump(const Duration(seconds: 1));

      expect(tester.takeException(), isNull);
    });

    testWidgets('core components pump without throwing', (tester) async {
      await tester.pumpWidget(
        MaterialApp(
          theme: VeriqooTheme.dark,
          home: Scaffold(
            body: SingleChildScrollView(
              child: Column(
                children: [
                  VeriqooButton(label: 'Verify', onPressed: () {}),
                  const VeriqooScore(value: 87),
                  const VeriqooStatus(kind: VeriqooStatusKind.verified),
                  const VeriqooStatus(kind: VeriqooStatusKind.flag),
                  const VeriqooStatus(kind: VeriqooStatusKind.missing),
                  const VeriqooStatus(kind: VeriqooStatusKind.violation),
                  const SizedBox(
                    width: 300,
                    height: 300,
                    child: VeriqooScannerOverlay(),
                  ),
                ],
              ),
            ),
          ),
        ),
      );

      await tester.pump(const Duration(seconds: 1));

      expect(tester.takeException(), isNull);
    });
  });
}
