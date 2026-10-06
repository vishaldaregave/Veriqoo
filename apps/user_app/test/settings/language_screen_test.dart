import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:shared_core/design_system/design_system.dart';

import 'package:flutter_application_1/core/providers/locale_provider.dart';
import 'package:flutter_application_1/features/settings/language_screen.dart';

Future<void> _pumpLanguage(WidgetTester tester) async {
  // A tall surface so all ten rows are laid out (and findable).
  await tester.binding.setSurfaceSize(const Size(600, 1400));
  addTearDown(() => tester.binding.setSurfaceSize(null));

  await tester.pumpWidget(
    const ProviderScope(
      child: MaterialApp(
        home: LanguageScreen(),
      ),
    ),
  );
  await tester.pump();
}

Finder _checkIn(String endonym) => find.descendant(
      of: find.ancestor(of: find.text(endonym), matching: find.byType(InkWell)),
      matching: find.byIcon(VeriqooIcons.check),
    );

void main() {
  group('LanguageScreen', () {
    testWidgets('lists every supported language by its endonym',
        (tester) async {
      await _pumpLanguage(tester);

      for (final language in kSupportedLanguages) {
        expect(
          find.text(language.endonym),
          findsOneWidget,
          reason: 'missing ${language.englishName}',
        );
      }
    });

    testWidgets('marks English as the initial selection', (tester) async {
      await _pumpLanguage(tester);

      expect(_checkIn('English'), findsOneWidget);
      // Only one language is marked.
      expect(find.byIcon(VeriqooIcons.check), findsOneWidget);
    });

    testWidgets('selecting Hindi moves the active check', (tester) async {
      await _pumpLanguage(tester);

      await tester.tap(find.text('हिन्दी'));
      await tester.pump();

      expect(_checkIn('हिन्दी'), findsOneWidget);
      expect(_checkIn('English'), findsNothing);
      expect(find.byIcon(VeriqooIcons.check), findsOneWidget);
    });
  });
}
