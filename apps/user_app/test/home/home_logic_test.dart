import 'package:flutter_test/flutter_test.dart';
import 'package:shared_core/design_system/design_system.dart';

import 'package:flutter_application_1/features/home/home_strings.dart';
import 'package:flutter_application_1/features/home/home_user.dart';
import 'package:flutter_application_1/features/inspections/inspection_record.dart';

void main() {
  group('deriveScore', () {
    test('compliant is a perfect 100', () {
      expect(
        deriveScore(isCompliant: true, issueCount: 3, missingCount: 2),
        100,
      );
    });

    test('non-compliant deducts and caps at 95', () {
      expect(
        deriveScore(isCompliant: false, issueCount: 0, missingCount: 0),
        95,
      );
      expect(
        deriveScore(isCompliant: null, issueCount: 1, missingCount: 1),
        75,
      );
    });

    test('floors at 0', () {
      expect(
        deriveScore(isCompliant: false, issueCount: 10, missingCount: 10),
        0,
      );
    });
  });

  group('deriveStatus', () {
    test('compliant wins outright', () {
      expect(
        deriveStatus(
          isCompliant: true,
          issueCount: 5,
          violationCount: 2,
          missingCount: 1,
        ),
        VeriqooStatusKind.verified,
      );
    });

    test('severe issue is a violation', () {
      expect(
        deriveStatus(
          isCompliant: false,
          issueCount: 2,
          violationCount: 1,
          missingCount: 0,
        ),
        VeriqooStatusKind.violation,
      );
    });

    test('non-severe issue is a flag', () {
      expect(
        deriveStatus(
          isCompliant: false,
          issueCount: 1,
          violationCount: 0,
          missingCount: 0,
        ),
        VeriqooStatusKind.flag,
      );
    });

    test('otherwise not-detected', () {
      expect(
        deriveStatus(
          isCompliant: null,
          issueCount: 0,
          violationCount: 0,
          missingCount: 0,
        ),
        VeriqooStatusKind.missing,
      );
    });
  });

  group('greetingFor / greetingLine', () {
    test('maps the hour to a time-of-day prefix', () {
      expect(greetingFor(DateTime(2026, 1, 1, 8)), HomeStrings.goodMorning);
      expect(greetingFor(DateTime(2026, 1, 1, 11, 59)), HomeStrings.goodMorning);
      expect(greetingFor(DateTime(2026, 1, 1, 12)), HomeStrings.goodAfternoon);
      expect(greetingFor(DateTime(2026, 1, 1, 16, 59)), HomeStrings.goodAfternoon);
      expect(greetingFor(DateTime(2026, 1, 1, 17)), HomeStrings.goodEvening);
      expect(greetingFor(DateTime(2026, 1, 1, 23)), HomeStrings.goodEvening);
    });

    test('appends the name, or falls back to the bare prefix', () {
      final morning = DateTime(2026, 1, 1, 8);
      expect(
        greetingLine(const HomeUser(name: 'Ada'), morning),
        '${HomeStrings.goodMorning}, Ada',
      );
      expect(greetingLine(null, morning), HomeStrings.goodMorning);
      expect(
        greetingLine(const HomeUser(email: 'bob@example.com'), morning),
        '${HomeStrings.goodMorning}, bob',
      );
    });
  });

  group('displayNameFor', () {
    test('prefers the metadata name', () {
      expect(displayNameFor(const HomeUser(name: 'Ada', email: 'a@x.com')), 'Ada');
    });

    test('falls back to the email local-part, then the raw email', () {
      expect(displayNameFor(const HomeUser(email: 'bob@example.com')), 'bob');
      expect(displayNameFor(const HomeUser(email: 'weird')), 'weird');
    });

    test('null when nothing is available', () {
      expect(displayNameFor(null), isNull);
      expect(displayNameFor(const HomeUser()), isNull);
    });
  });

  group('InspectionRecord.fromMap', () {
    test('fills safe defaults for an empty row', () {
      final r = InspectionRecord.fromMap(const <String, dynamic>{});
      expect(r.id, 'row-0');
      expect(r.productName, 'Unknown product');
      expect(r.inspectedAt, isNull);
      expect(r.isCompliant, isNull);
      expect(r.missingInformation, isEmpty);
      expect(r.issueCount, 0);
      expect(r.violationCount, 0);
      expect(r.score, 95);
      expect(r.status, VeriqooStatusKind.missing);
      expect(r.timestampLabel, '—');
      expect(r.displayId, 'VRQ-00000000-0000');
    });

    test('tolerates wrongly-typed columns', () {
      final r = InspectionRecord.fromMap(const <String, dynamic>{
        'product_name': 123,
        'inspected_at': 456,
        'is_compliant': 'yes',
        'missing_information': 'oops',
        'possible_issues': <String, dynamic>{'a': 1},
      });
      expect(r.productName, 'Unknown product');
      expect(r.inspectedAt, isNull);
      expect(r.isCompliant, isNull);
      expect(r.missingInformation, isEmpty);
      expect(r.issueCount, 0);
    });

    test('parses a well-formed row and derives score/status/labels', () {
      final r = InspectionRecord.fromMap(const <String, dynamic>{
        'id': 'abcd1234',
        'product_name': 'Milk 500ml',
        'inspected_at': '2026-01-02T09:05:00', // no Z -> parsed as local
        'is_compliant': false,
        'possible_issues': <Map<String, dynamic>>[
          <String, dynamic>{'severity': 'critical'},
          <String, dynamic>{'severity': 'low'},
        ],
        'missing_information': <String>['MRP', 'BATCH'],
      });
      expect(r.productName, 'Milk 500ml');
      expect(r.timestampLabel, '2026-01-02 09:05');
      expect(r.displayId, 'VRQ-20260102-1234');
      expect(r.issueCount, 2);
      expect(r.violationCount, 1);
      expect(r.status, VeriqooStatusKind.violation);
      expect(r.score, 50);
    });
  });
}
