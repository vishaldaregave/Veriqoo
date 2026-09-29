import 'package:flutter_test/flutter_test.dart';
import 'package:flutter_application_1/services/compliance_analysis.dart';

void main() {
  group('ComplianceIssue compatibility', () {
    test('loads legacy issue JSON with only title, description and severity', () {
      final issue = ComplianceIssue.fromJson({
        'title': 'Missing MRP',
        'description': 'MRP is missing from the label.',
        'severity': 'high',
      });

      expect(issue.title, 'Missing MRP');
      expect(issue.description, 'MRP is missing from the label.');
      expect(issue.severity, 'high');
      expect(issue.ruleNumbers, isEmpty);
      expect(issue.ruleTitles, isEmpty);
      expect(issue.legalBasis, isNull);
      expect(issue.ocrEvidence, isNull);
    });

    test('round-trips new legal reference fields without breaking legacy format', () {
      final original = ComplianceIssue(
        title: 'Missing MRP',
        description: 'MRP is missing from the label.',
        severity: 'high',
        ruleNumbers: const ['R. 6(1)', 'R. 6(2)'],
        ruleTitles: const ['MRP declaration', 'Price declaration'],
        legalBasis: 'Rule 6 requires MRP declaration on packaged commodities.',
        ocrEvidence: 'OCR shows no MRP value on the front label.',
      );

      final json = original.toJson();
      final restored = ComplianceIssue.fromJson(json);

      expect(restored.title, original.title);
      expect(restored.description, original.description);
      expect(restored.severity, original.severity);
      expect(restored.ruleNumbers, original.ruleNumbers);
      expect(restored.ruleTitles, original.ruleTitles);
      expect(restored.legalBasis, original.legalBasis);
      expect(restored.ocrEvidence, original.ocrEvidence);
    });

    test('loads a full ComplianceAnalysis from older JSON shape', () {
      final analysis = ComplianceAnalysis.fromJson({
        'productName': 'Sample Product',
        'mrp': '₹199',
        'netQuantity': '500 g',
        'manufacturer': 'Sample Co',
        'address': 'Test address',
        'packingDate': '2025-01-01',
        'customerCare': '1800-000-000',
        'missingInformation': ['Missing MRP'],
        'possibleIssues': [
          {
            'title': 'Missing MRP',
            'description': 'MRP is missing from the label.',
            'severity': 'high',
          },
        ],
      });

      expect(analysis.possibleIssues, hasLength(1));
      expect(analysis.possibleIssues.first.ruleNumbers, isEmpty);
      expect(analysis.possibleIssues.first.ruleTitles, isEmpty);
      expect(analysis.possibleIssues.first.legalBasis, isNull);
      expect(analysis.possibleIssues.first.ocrEvidence, isNull);
    });
  });
}
