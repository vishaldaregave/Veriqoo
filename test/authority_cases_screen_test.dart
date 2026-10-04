import 'dart:convert';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';
import 'package:flutter_application_1/screens/dashboard/authority_cases_screen.dart';
import 'package:flutter_application_1/services/authority_api_service.dart';

void main() {
  group('AuthorityCasesScreen Widget Tests', () {
    testWidgets('renders loading state and then case queue on success', (tester) async {
      final mockClient = MockClient((request) async {
        if (request.url.path.endsWith('/authority/cases')) {
          final responseBody = {
            'items': [
              {
                'id': 'case-abc-1234',
                'user_id': 'user-1111',
                'issue_type': 'PACKAGING_DEFECT',
                'title': 'Missing Mandatory MRP',
                'status': 'SUBMITTED',
                'department': 'LEGAL_METROLOGY',
                'state_code': 'MH',
                'district_code': 'PUNE',
                'jurisdiction_verified': true,
                'assigned_officer_id': null,
                'created_at': '2026-10-04T12:00:00Z',
                'updated_at': '2026-10-04T12:00:00Z',
              }
            ],
            'total': 1,
            'limit': 20,
            'offset': 0,
          };
          return http.Response(jsonEncode(responseBody), 200, headers: {'content-type': 'application/json'});
        }
        return http.Response('Not Found', 404);
      });

      final apiService = AuthorityApiService(
        baseUrl: 'http://localhost:8000/api/v1',
        httpClient: mockClient,
        authTokenProvider: () => 'valid-authority-token',
      );

      await tester.pumpWidget(
        MaterialApp(
          home: AuthorityCasesScreen(apiService: apiService),
        ),
      );

      expect(find.byType(CircularProgressIndicator), findsOneWidget);

      await tester.pumpAndSettle();

      expect(find.text('Authority Case Queue'), findsOneWidget);
      expect(find.text('Missing Mandatory MRP'), findsOneWidget);
      expect(find.text('SUBMITTED'), findsWidgets);
      expect(find.text('LEGAL_METROLOGY'), findsOneWidget);
      expect(find.text('Unassigned'), findsOneWidget);
    });

    testWidgets('renders Access Denied state on 403 Forbidden without leaking case data', (tester) async {
      final mockClient = MockClient((request) async {
        return http.Response(
          jsonEncode({
            'detail': {
              'code': 'FORBIDDEN',
              'message': 'Access denied: User lacks active authority profile for this department',
              'details': {},
            }
          }),
          403,
          headers: {'content-type': 'application/json'},
        );
      });

      final apiService = AuthorityApiService(
        baseUrl: 'http://localhost:8000/api/v1',
        httpClient: mockClient,
        authTokenProvider: () => 'consumer-token',
      );

      await tester.pumpWidget(
        MaterialApp(
          home: AuthorityCasesScreen(apiService: apiService),
        ),
      );

      await tester.pumpAndSettle();

      expect(find.text('Access Denied'), findsOneWidget);
      expect(find.textContaining('lacks active authority profile'), findsOneWidget);
      expect(find.byIcon(Icons.gpp_bad_outlined), findsOneWidget);
      expect(find.text('Missing Mandatory MRP'), findsNothing);
    });

    testWidgets('renders empty state when no cases returned in jurisdiction queue', (tester) async {
      final mockClient = MockClient((request) async {
        return http.Response(
          jsonEncode({'items': [], 'total': 0, 'limit': 20, 'offset': 0}),
          200,
          headers: {'content-type': 'application/json'},
        );
      });

      final apiService = AuthorityApiService(
        baseUrl: 'http://localhost:8000/api/v1',
        httpClient: mockClient,
        authTokenProvider: () => 'officer-token',
      );

      await tester.pumpWidget(
        MaterialApp(
          home: AuthorityCasesScreen(apiService: apiService),
        ),
      );

      await tester.pumpAndSettle();

      expect(find.text('No cases found in this jurisdiction queue.'), findsOneWidget);
      expect(find.byIcon(Icons.inbox_outlined), findsOneWidget);
    });
  });

  group('AuthorityCaseDetailScreen Widget Tests', () {
    testWidgets('renders case detail, evidence, actions, notes, and audit timeline', (tester) async {
      final mockClient = MockClient((request) async {
        final path = request.url.path;
        if (path.endsWith('/authority/cases/case-999')) {
          return http.Response(
            jsonEncode({
              'id': 'case-999-uuid',
              'user_id': 'user-1111',
              'issue_type': 'NON_STANDARD_UNIT',
              'title': 'Non-standard measurement unit',
              'description': 'Product displays net weight in ounces without standard SI metric declaration.',
              'status': 'UNDER_REVIEW',
              'department': 'LEGAL_METROLOGY',
              'state_code': 'MH',
              'district_code': 'PUNE',
              'jurisdiction_verified': true,
              'assigned_officer_id': 'officer-1111',
              'evidence_images': [],
              'created_at': '2026-10-04T12:00:00Z',
              'updated_at': '2026-10-04T12:00:00Z',
            }),
            200,
            headers: {'content-type': 'application/json'},
          );
        } else if (path.endsWith('/notes')) {
          return http.Response(
            jsonEncode({
              'items': [
                {
                  'id': 'note-1',
                  'issue_id': 'case-999-uuid',
                  'author_id': 'officer-1111',
                  'note_text': 'Field inspection scheduled for tomorrow.',
                  'is_internal': true,
                  'created_at': '2026-10-05T01:00:00Z',
                  'updated_at': '2026-10-05T01:00:00Z',
                }
              ],
              'total': 1,
            }),
            200,
            headers: {'content-type': 'application/json'},
          );
        } else if (path.endsWith('/audit-timeline')) {
          return http.Response(
            jsonEncode({
              'events': [
                {
                  'id': 'evt-1',
                  'actor_id': 'officer-1111',
                  'action': 'STATUS_CHANGE',
                  'previous_state': 'SUBMITTED',
                  'new_state': 'UNDER_REVIEW',
                  'metadata': {},
                  'created_at': '2026-10-05T00:30:00Z',
                }
              ]
            }),
            200,
            headers: {'content-type': 'application/json'},
          );
        }
        return http.Response('Not Found', 404);
      });

      final apiService = AuthorityApiService(
        baseUrl: 'http://localhost:8000/api/v1',
        httpClient: mockClient,
        authTokenProvider: () => 'valid-authority-token',
      );

      await tester.pumpWidget(
        MaterialApp(
          home: AuthorityCaseDetailScreen(
            caseId: 'case-999',
            apiService: apiService,
          ),
        ),
      );

      await tester.pumpAndSettle();

      expect(find.text('Investigation Case Details'), findsOneWidget);
      expect(find.text('Non-standard measurement unit'), findsOneWidget);
      expect(find.text('Confidential Investigation Notes'), findsOneWidget);
      expect(find.text('INTERNAL ONLY'), findsOneWidget);
      expect(find.text('Field inspection scheduled for tomorrow.'), findsOneWidget);
      expect(find.text('Case Audit Timeline'), findsOneWidget);
      expect(find.text('STATUS_CHANGE'), findsOneWidget);
      expect(find.text('Update Status'), findsOneWidget);
      expect(find.text('Reassign to Me'), findsOneWidget);
    });
  });
}
