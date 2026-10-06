import 'dart:ui' show Rect;

import 'package:flutter_test/flutter_test.dart';
import 'package:shared_core/design_system/design_system.dart' show VeriqooStatusKind;
import 'package:shared_core/services/compliance_analysis.dart';

import 'package:flutter_application_1/features/scan/model/detected_field.dart';
import 'package:flutter_application_1/features/scan/result/report_finding.dart';

void main() {
  group('ReportFinding.fromAnalysis', () {
    test('emits missing declarations first, then issues, numbered 1-based', () {
      const analysis = ComplianceAnalysis(
        productName: 'X',
        mrp: '',
        netQuantity: '',
        manufacturer: '',
        address: '',
        packingDate: '',
        customerCare: '',
        missingInformation: <String>['MRP', 'Net quantity'],
        possibleIssues: <ComplianceIssue>[
          ComplianceIssue(
            title: 'Verified issue',
            description: 'd',
            severity: 'high',
            verificationStatus: LegalVerificationStatus.legallyVerified,
          ),
          ComplianceIssue(
            title: 'Observed issue',
            description: 'd',
            severity: 'low',
            verificationStatus: LegalVerificationStatus.generalObservation,
          ),
        ],
      );

      final findings = ReportFinding.fromAnalysis(analysis);
      expect(findings, hasLength(4));

      expect(findings[0].number, 1);
      expect(findings[0].kind, ReportFindingKind.missingDeclaration);
      expect(findings[0].status, VeriqooStatusKind.missing);
      expect(findings[0].missingField, 'MRP');

      expect(findings[1].number, 2);
      expect(findings[1].kind, ReportFindingKind.missingDeclaration);

      // Legally-verified issue → violation; general observation → flag.
      expect(findings[2].number, 3);
      expect(findings[2].kind, ReportFindingKind.potentialViolation);
      expect(findings[2].status, VeriqooStatusKind.violation);

      expect(findings[3].number, 4);
      expect(findings[3].status, VeriqooStatusKind.flag);

      expect(findings[0].twoDigit, '01');
      expect(findings[3].twoDigit, '04');
    });

    test('all-compliant analysis yields no findings', () {
      const analysis = ComplianceAnalysis(
        productName: 'X',
        mrp: '1',
        netQuantity: '1',
        manufacturer: '1',
        address: '1',
        packingDate: '1',
        customerCare: '1',
        missingInformation: <String>[],
        possibleIssues: <ComplianceIssue>[],
      );
      expect(ReportFinding.fromAnalysis(analysis), isEmpty);
    });
  });

  group('targetFieldLabel keyword mapping', () {
    test('maps keywords to the correct detection label', () {
      expect(targetFieldLabel('MRP missing'), DetectedFieldLabels.mrp);
      expect(targetFieldLabel('price not shown'), DetectedFieldLabels.mrp);
      expect(
        targetFieldLabel('net quantity'),
        DetectedFieldLabels.mandatoryDeclaration,
      );
      expect(
        targetFieldLabel('declared qty'),
        DetectedFieldLabels.mandatoryDeclaration,
      );
      expect(
        targetFieldLabel('manufactured by'),
        DetectedFieldLabels.manufacturer,
      );
      expect(targetFieldLabel('mfg date'), DetectedFieldLabels.manufacturer);
      expect(targetFieldLabel('batch number'), DetectedFieldLabels.batch);
      expect(targetFieldLabel('lot code'), DetectedFieldLabels.batch);
      // Anything unmatched defaults to product name.
      expect(
        targetFieldLabel('something unrelated'),
        DetectedFieldLabels.productName,
      );
    });
  });

  group('linkFinding (best-effort, always DERIVED)', () {
    const detected = <DetectedField>[
      DetectedField(
        rectNormalized: Rect.fromLTWH(0.1, 0.3, 0.3, 0.07),
        label: DetectedFieldLabels.mrp,
        text: 'MRP ₹120',
      ),
    ];

    test('matches a keyword to a detected region and carries its rect', () {
      const finding = ReportFinding(
        number: 1,
        kind: ReportFindingKind.missingDeclaration,
        title: 'MRP',
        status: VeriqooStatusKind.missing,
        missingField: 'MRP',
      );
      final link = linkFinding(finding, detectedFields: detected, evidenceCount: 2);
      expect(link.derived, isTrue);
      expect(link.field, isNotNull);
      expect(link.field!.label, DetectedFieldLabels.mrp);
      expect(link.imageIndex, 0);
    });

    test('falls back to primary image (field null) when nothing matches', () {
      const finding = ReportFinding(
        number: 1,
        kind: ReportFindingKind.missingDeclaration,
        title: 'Customer care details',
        status: VeriqooStatusKind.missing,
        missingField: 'Customer care details',
      );
      // 'customer care' maps to PRODUCT NAME, which is absent from [detected].
      final link = linkFinding(finding, detectedFields: detected, evidenceCount: 2);
      expect(link.derived, isTrue);
      expect(link.field, isNull);
      expect(link.imageIndex, 0);
    });

    test('is always DERIVED even with no evidence', () {
      const finding = ReportFinding(
        number: 1,
        kind: ReportFindingKind.potentialViolation,
        title: 'Issue',
        status: VeriqooStatusKind.flag,
      );
      final link = linkFinding(
        finding,
        detectedFields: const <DetectedField>[],
        evidenceCount: 0,
      );
      expect(link.derived, isTrue);
      expect(link.field, isNull);
      expect(link.imageIndex, 0);
    });
  });
}
