import 'dart:convert';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';
import 'package:flutter_application_1/services/authority_api_service.dart';

void main() {
  group('AuthorityApiService Unit Tests', () {
    test('listCases parses successfully and builds correct query parameters', () async {
      final mockClient = MockClient((request) async {
        expect(request.url.path, '/api/v1/authority/cases');
        expect(request.url.queryParameters['status'], 'UNDER_REVIEW');
        expect(request.url.queryParameters['my_cases'], 'true');
        expect(request.headers['Authorization'], 'Bearer test-jwt-token');

        final responseBody = {
          'items': [
            {
              'id': 'case-1111',
              'user_id': 'user-1111',
              'issue_type': 'PACKAGING_DEFECT',
              'title': 'Incorrect Net Quantity',
              'status': 'UNDER_REVIEW',
              'department': 'LEGAL_METROLOGY',
              'state_code': 'MH',
              'district_code': 'PUNE',
              'jurisdiction_verified': true,
              'assigned_officer_id': 'officer-1111',
              'assigned_at': '2026-10-05T00:00:00Z',
              'assigned_by': 'officer-1111',
              'created_at': '2026-10-04T12:00:00Z',
              'updated_at': '2026-10-05T00:00:00Z',
            }
          ],
          'total': 1,
          'limit': 20,
          'offset': 0,
        };
        return http.Response(jsonEncode(responseBody), 200, headers: {'content-type': 'application/json'});
      });

      final api = AuthorityApiService(
        baseUrl: 'http://localhost:8000/api/v1',
        httpClient: mockClient,
        authTokenProvider: () => 'test-jwt-token',
      );

      final cases = await api.listCases(status: 'UNDER_REVIEW', myCases: true);
      expect(cases, hasLength(1));
      expect(cases.first.id, 'case-1111');
      expect(cases.first.title, 'Incorrect Net Quantity');
      expect(cases.first.jurisdictionVerified, isTrue);
      expect(cases.first.department, 'LEGAL_METROLOGY');
    });

    test('listCases throws AuthorityApiException on 403 Forbidden', () async {
      final mockClient = MockClient((request) async {
        return http.Response(
          jsonEncode({
            'detail': {
              'code': 'FORBIDDEN',
              'message': 'Access denied: User has role consumer, required authority',
              'details': {},
            }
          }),
          403,
          headers: {'content-type': 'application/json'},
        );
      });

      final api = AuthorityApiService(
        baseUrl: 'http://localhost:8000/api/v1',
        httpClient: mockClient,
        authTokenProvider: () => 'consumer-token',
      );

      expect(
        () async => await api.listCases(),
        throwsA(
          isA<AuthorityApiException>()
              .having((e) => e.statusCode, 'statusCode', 403)
              .having((e) => e.code, 'code', 'FORBIDDEN'),
        ),
      );
    });

    test('assignOfficer sends precondition and handles 409 Conflict', () async {
      final mockClient = MockClient((request) async {
        expect(request.url.path, '/api/v1/authority/cases/case-123/assign');
        final body = jsonDecode(request.body) as Map<String, dynamic>;
        expect(body['expect_unassigned'], isTrue);

        return http.Response(
          jsonEncode({
            'detail': {
              'code': 'INVALID_INSPECTION_STATE',
              'message': 'Assignment concurrency conflict: Expected case to be unassigned',
              'details': {},
            }
          }),
          409,
          headers: {'content-type': 'application/json'},
        );
      });

      final api = AuthorityApiService(
        baseUrl: 'http://localhost:8000/api/v1',
        httpClient: mockClient,
        authTokenProvider: () => 'officer-token',
      );

      expect(
        () async => await api.assignOfficer(caseId: 'case-123', expectUnassigned: true),
        throwsA(
          isA<AuthorityApiException>()
              .having((e) => e.statusCode, 'statusCode', 409)
              .having((e) => e.message, 'message', contains('concurrency conflict')),
        ),
      );
    });

    test('error handling parses error envelope from FastAPI global exception handler', () async {
      final mockClient = MockClient((request) async {
        return http.Response(
          jsonEncode({
            'error': {
              'code': 'CONCURRENT_UPDATE_CONFLICT',
              'message': 'Establishment review concurrency token mismatch',
              'details': {'conflict': true},
            }
          }),
          409,
          headers: {'content-type': 'application/json'},
        );
      });

      final api = AuthorityApiService(
        baseUrl: 'http://localhost:8000/api/v1',
        httpClient: mockClient,
        authTokenProvider: () => 'officer-token',
      );

      expect(
        () async => await api.listCases(),
        throwsA(
          isA<AuthorityApiException>()
              .having((e) => e.statusCode, 'statusCode', 409)
              .having((e) => e.code, 'code', 'CONCURRENT_UPDATE_CONFLICT')
              .having((e) => e.message, 'message', contains('concurrency token mismatch')),
        ),
      );
    });

    test('transitionStatus includes expected_status token and resolution_notes', () async {
      final mockClient = MockClient((request) async {
        expect(request.url.path, '/api/v1/authority/cases/case-456/status');
        final body = jsonDecode(request.body) as Map<String, dynamic>;
        expect(body['new_status'], 'RESOLVED');
        expect(body['expected_status'], 'ACTION_TAKEN');
        expect(body['resolution_notes'], 'Inspection complete, penalty levied.');

        return http.Response(
          jsonEncode({
            'case_id': 'case-456',
            'previous_status': 'ACTION_TAKEN',
            'new_status': 'RESOLVED',
            'resolution_notes': 'Inspection complete, penalty levied.',
            'updated_at': '2026-10-05T00:10:00Z',
            'event_id': 'evt-999',
          }),
          200,
          headers: {'content-type': 'application/json'},
        );
      });

      final api = AuthorityApiService(
        baseUrl: 'http://localhost:8000/api/v1',
        httpClient: mockClient,
        authTokenProvider: () => 'officer-token',
      );

      final res = await api.transitionStatus(
        caseId: 'case-456',
        newStatus: 'RESOLVED',
        expectedStatus: 'ACTION_TAKEN',
        resolutionNotes: 'Inspection complete, penalty levied.',
      );

      expect(res['new_status'], 'RESOLVED');
      expect(res['previous_status'], 'ACTION_TAKEN');
    });

    test('addNote validates and posts note via atomic path', () async {
      final mockClient = MockClient((request) async {
        expect(request.url.path, '/api/v1/authority/cases/case-789/notes');
        final body = jsonDecode(request.body) as Map<String, dynamic>;
        expect(body['note_text'], 'Sample internal note');

        return http.Response(
          jsonEncode({
            'id': 'note-1',
            'issue_id': 'case-789',
            'author_id': 'officer-1',
            'note_text': 'Sample internal note',
            'is_internal': true,
            'created_at': '2026-10-05T00:10:00Z',
            'updated_at': '2026-10-05T00:10:00Z',
          }),
          201,
          headers: {'content-type': 'application/json'},
        );
      });

      final api = AuthorityApiService(
        baseUrl: 'http://localhost:8000/api/v1',
        httpClient: mockClient,
        authTokenProvider: () => 'officer-token',
      );

      final note = await api.addNote(caseId: 'case-789', noteText: 'Sample internal note');
      expect(note.id, 'note-1');
      expect(note.isInternal, isTrue);
      expect(note.noteText, 'Sample internal note');
    });

    test('getCaseDetails retrieves and parses full details including evidence', () async {
      final mockClient = MockClient((request) async {
        expect(request.url.path, '/api/v1/authority/cases/case-1234');
        return http.Response(
          jsonEncode({
            'id': 'case-1234',
            'user_id': 'user-1',
            'issue_type': 'PACKAGING_DEFECT',
            'title': 'Defective Label',
            'description': 'Description text',
            'status': 'SUBMITTED',
            'evidence_images': [{'url': 'https://example.com/evidence1.jpg'}],
            'department': 'LEGAL_METROLOGY',
            'state_code': 'MH',
            'district_code': 'PUNE',
            'jurisdiction_verified': true,
            'assigned_officer_id': null,
            'created_at': '2026-10-04T12:00:00Z',
            'updated_at': '2026-10-04T12:00:00Z',
          }),
          200,
          headers: {'content-type': 'application/json'},
        );
      });

      final api = AuthorityApiService(
        baseUrl: 'http://localhost:8000/api/v1',
        httpClient: mockClient,
        authTokenProvider: () => 'officer-token',
      );

      final detail = await api.getCaseDetails('case-1234');
      expect(detail.id, 'case-1234');
      expect(detail.evidenceImages, hasLength(1));
      expect(detail.jurisdictionVerified, isTrue);
    });

    test('listNotes parses note list envelope', () async {
      final mockClient = MockClient((request) async {
        expect(request.url.path, '/api/v1/authority/cases/case-1234/notes');
        return http.Response(
          jsonEncode({
            'items': [
              {
                'id': 'note-1',
                'issue_id': 'case-1234',
                'author_id': 'officer-1',
                'note_text': 'First inspection note',
                'is_internal': true,
                'created_at': '2026-10-05T00:00:00Z',
                'updated_at': '2026-10-05T00:00:00Z',
              }
            ],
            'total': 1,
          }),
          200,
          headers: {'content-type': 'application/json'},
        );
      });

      final api = AuthorityApiService(
        baseUrl: 'http://localhost:8000/api/v1',
        httpClient: mockClient,
        authTokenProvider: () => 'officer-token',
      );

      final notes = await api.listNotes('case-1234');
      expect(notes, hasLength(1));
      expect(notes.first.noteText, 'First inspection note');
    });

    test('getAuditTimeline parses items envelope and event_type fallback', () async {
      final mockClient = MockClient((request) async {
        expect(request.url.path, '/api/v1/authority/cases/case-1234/audit-timeline');
        return http.Response(
          jsonEncode({
            'items': [
              {
                'id': 'evt-1',
                'issue_id': 'case-1234',
                'actor_id': 'officer-1',
                'event_type': 'NOTE_ADDED',
                'previous_state': null,
                'new_state': null,
                'metadata': {'note_id': 'n-1'},
                'created_at': '2026-10-05T00:00:00Z',
              }
            ],
            'total': 1,
          }),
          200,
          headers: {'content-type': 'application/json'},
        );
      });

      final api = AuthorityApiService(
        baseUrl: 'http://localhost:8000/api/v1',
        httpClient: mockClient,
        authTokenProvider: () => 'officer-token',
      );

      final events = await api.getAuditTimeline('case-1234');
      expect(events, hasLength(1));
      expect(events.first.action, 'NOTE_ADDED');
      expect(events.first.actorId, 'officer-1');
    });
  });
}
