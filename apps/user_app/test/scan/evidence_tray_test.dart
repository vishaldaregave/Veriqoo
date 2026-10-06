import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:shared_core/design_system/design_system.dart';

import 'package:flutter_application_1/features/scan/model/evidence_image.dart';
import 'package:flutter_application_1/features/scan/widgets/evidence_tray.dart';

import 'scan_harness.dart';

void main() {
  List<EvidenceImage> sampleEvidence() => <EvidenceImage>[
        EvidenceImage(
          file: stubImage('front.png'),
          role: EvidenceRole.front,
          sequence: 1,
          label: EvidenceRole.front.label,
        ),
        EvidenceImage(
          file: stubImage('back.png'),
          role: EvidenceRole.back,
          sequence: 2,
          label: EvidenceRole.back.label,
        ),
        EvidenceImage(
          file: stubImage('side.png'),
          role: EvidenceRole.side,
          sequence: 3,
          label: EvidenceRole.side.label,
        ),
      ];

  Future<void> pumpTray(
    WidgetTester tester, {
    required List<EvidenceImage> evidence,
    required int currentIndex,
    ValueChanged<int>? onSelect,
    ValueChanged<int>? onRetake,
    ValueChanged<int>? onDelete,
    VoidCallback? onAdd,
  }) async {
    await tester.pumpWidget(
      MaterialApp(
        theme: VeriqooTheme.dark,
        home: Scaffold(
          body: EvidenceTray(
            evidence: evidence,
            currentIndex: currentIndex,
            onSelect: onSelect ?? (_) {},
            onRetake: onRetake ?? (_) {},
            onDelete: onDelete ?? (_) {},
            onAdd: onAdd ?? () {},
          ),
        ),
      ),
    );
    await tester.pump();
    await tester.pump(const Duration(milliseconds: 20));
  }

  testWidgets('renders numbered tiles plus the add tile', (tester) async {
    await pumpTray(tester, evidence: sampleEvidence(), currentIndex: 0);

    expect(find.byKey(evidenceTileKey(0)), findsOneWidget);
    expect(find.byKey(evidenceTileKey(1)), findsOneWidget);
    expect(find.byKey(evidenceTileKey(2)), findsOneWidget);
    expect(find.byKey(kEvidenceAddTileKey), findsOneWidget);

    // Numbered 01/02/03.
    expect(find.text('01'), findsOneWidget);
    expect(find.text('02'), findsOneWidget);
    expect(find.text('03'), findsOneWidget);
    expect(tester.takeException(), isNull);
  });

  testWidgets('selecting a tile fires onSelect', (tester) async {
    int? selected;
    await pumpTray(
      tester,
      evidence: sampleEvidence(),
      currentIndex: 0,
      onSelect: (i) => selected = i,
    );

    await tester.tap(find.byKey(evidenceTileKey(1)));
    expect(selected, 1);
  });

  testWidgets('retake and delete callbacks fire', (tester) async {
    int? retaken;
    int? deleted;
    await pumpTray(
      tester,
      evidence: sampleEvidence(),
      currentIndex: 0,
      onRetake: (i) => retaken = i,
      onDelete: (i) => deleted = i,
    );

    await tester.tap(find.byKey(evidenceRetakeKey(2)));
    expect(retaken, 2);

    await tester.tap(find.byKey(evidenceDeleteKey(1)));
    expect(deleted, 1);
  });

  testWidgets('add tile fires onAdd', (tester) async {
    var added = false;
    await pumpTray(
      tester,
      evidence: sampleEvidence(),
      currentIndex: 0,
      onAdd: () => added = true,
    );

    await tester.tap(find.byKey(kEvidenceAddTileKey));
    expect(added, isTrue);
  });
}
