import 'package:flutter_test/flutter_test.dart';
import 'package:shared_core/services/compliance_analysis.dart';

import 'package:flutter_application_1/features/scan/result/compliance_score.dart';

import 'result_harness.dart';

void main() {
  group('ComplianceScore.fromAnalysis (D2 deterministic formula)', () {
    test('all-compliant fixture → 100, verified 7', () {
      final score = ComplianceScore.fromAnalysis(fixtureAllCompliant());
      // present=7 → base=100, no penalties.
      expect(score.score, 100);
      expect(score.verified, 7);
      expect(score.flagged, 0);
      expect(score.missing, 0);
      expect(score.mandatoryTotal, 7);
    });

    test('missing-only fixture → 11 (base 28.57 − 18)', () {
      final score = ComplianceScore.fromAnalysis(fixtureMissingOnly());
      // present=2 → base=2/7*100≈28.57; missingPenalty=6*3=18; → 10.57 → 11.
      expect(score.score, 11);
      expect(score.verified, 2);
      expect(score.flagged, 0);
      expect(score.missing, 3);
    });

    test('with-issues fixture → 75 (100 − 12 − 8 − 5)', () {
      final score = ComplianceScore.fromAnalysis(fixtureWithIssues());
      // present=7 → base=100; issuePenalty=high(12)+medium(8)+low(5)=25.
      expect(score.score, 75);
      expect(score.verified, 7);
      expect(score.flagged, 3);
      expect(score.missing, 0);
    });

    test('is deterministic — same analysis yields the same score', () {
      final a = ComplianceScore.fromAnalysis(fixtureWithIssues());
      final b = ComplianceScore.fromAnalysis(fixtureWithIssues());
      expect(a.score, b.score);
      expect(a.verified, b.verified);
    });

    test('severity weights map case-insensitively', () {
      expect(ComplianceScore.severityWeight('HIGH'), ComplianceScore.weightHigh);
      expect(
        ComplianceScore.severityWeight('critical'),
        ComplianceScore.weightHigh,
      );
      expect(
        ComplianceScore.severityWeight('Medium'),
        ComplianceScore.weightMedium,
      );
      expect(ComplianceScore.severityWeight('low'), ComplianceScore.weightLow);
      // Unknown severity falls back to the default weight.
      expect(
        ComplianceScore.severityWeight('nonsense'),
        ComplianceScore.weightDefault,
      );
    });

    test('score clamps to 0 and never goes negative', () {
      const heavilyNonCompliant = ComplianceAnalysis(
        productName: '',
        mrp: '',
        netQuantity: '',
        manufacturer: '',
        address: '',
        packingDate: '',
        customerCare: '',
        missingInformation: <String>['a', 'b', 'c', 'd', 'e'],
        possibleIssues: <ComplianceIssue>[
          ComplianceIssue(
            title: 'x',
            description: 'y',
            severity: 'high',
          ),
        ],
      );
      final score = ComplianceScore.fromAnalysis(heavilyNonCompliant);
      expect(score.score, 0);
      expect(score.verified, 0);
    });
  });
}
