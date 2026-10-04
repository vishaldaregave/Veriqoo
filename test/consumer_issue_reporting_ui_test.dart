import 'dart:async';
import 'dart:convert';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';
import 'package:flutter_application_1/main.dart';
import 'package:flutter_application_1/screens/dashboard/report_violation_dialog.dart';
import 'package:flutter_application_1/services/compliance_analysis.dart';
import 'package:flutter_application_1/services/consumer_issue_api_service.dart';

void main() {
  const dummyAnalysis = ComplianceAnalysis(
    productName: 'Britannia Good Day Biscuits',
    mrp: '₹30.00',
    netQuantity: '100g',
    manufacturer: 'Britannia Industries Ltd',
    address: 'Kolkata, WB',
    packingDate: '01/2026',
    customerCare: 'care@britannia.co.in',
    missingInformation: ['Consumer Care Address'],
    possibleIssues: [
      ComplianceIssue(
        title: 'Price Tampering',
        description: 'Dual MRP sticker observed over original MRP declaration',
        severity: 'HIGH',
        ruleNumbers: ['Rule 18(2)'],
        ruleTitles: ['Dual MRP Prohibition'],
        legalBasis: 'Legal Metrology (Packaged Commodities) Rules, 2011',
        ocrEvidence: 'MRP Rs. 35 pasted over Rs. 30',
        verificationStatus: LegalVerificationStatus.legallyVerified,
      ),
    ],
  );

  group('ConsumerIssueApiService Unit Tests', () {
    test('ensureInspectionSession calls POST /inspections and returns inspection_id', () async {
      final mockClient = MockClient((request) async {
        expect(request.url.path, '/api/v1/inspections');
        expect(request.headers['Authorization'], 'Bearer valid-jwt-token');
        final body = jsonDecode(request.body) as Map<String, dynamic>;
        expect(body['metadata']['product_name'], 'Britannia Good Day Biscuits');

        return http.Response(
          jsonEncode({
            'inspection_id': 'insp-sess-5555',
            'created_at': '2026-10-05T01:00:00Z',
          }),
          200,
          headers: {'content-type': 'application/json'},
        );
      });

      final service = ConsumerIssueApiService(
        baseUrl: 'http://localhost:8000/api/v1',
        httpClient: mockClient,
        authTokenProvider: () => 'valid-jwt-token',
      );

      final inspId = await service.ensureInspectionSession(
        productName: 'Britannia Good Day Biscuits',
        metadata: {'mrp': '₹30.00'},
      );

      expect(inspId, 'insp-sess-5555');
    });

    test('submitIssue posts correct payload and parses ConsumerIssueReport', () async {
      final mockClient = MockClient((request) async {
        expect(request.url.path, '/api/v1/consumer-issues');
        expect(request.headers['Authorization'], 'Bearer valid-jwt-token');

        final payload = jsonDecode(request.body) as Map<String, dynamic>;
        expect(payload['inspection_id'], 'insp-sess-5555');
        expect(payload['issue_type'], 'PRICE_TAMPERING');
        expect(payload['title'], 'Price Tampering on Biscuits');
        expect(payload['description'], 'Dual MRP sticker detected.');

        final responseBody = {
          'id': 'issue-9999',
          'user_id': 'user-1111',
          'inspection_id': 'insp-sess-5555',
          'saved_product_id': null,
          'issue_type': 'PRICE_TAMPERING',
          'title': 'Price Tampering on Biscuits',
          'description': 'Dual MRP sticker detected.',
          'status': 'SUBMITTED',
          'resolution_notes': null,
          'evidence_images': [],
          'department': 'LEGAL_METROLOGY',
          'state_code': null,
          'district_code': null,
          'jurisdiction_verified': false,
          'created_at': '2026-10-05T01:05:00Z',
          'updated_at': '2026-10-05T01:05:00Z',
        };
        return http.Response(jsonEncode(responseBody), 201, headers: {'content-type': 'application/json'});
      });

      final service = ConsumerIssueApiService(
        baseUrl: 'http://localhost:8000/api/v1',
        httpClient: mockClient,
        authTokenProvider: () => 'valid-jwt-token',
      );

      final report = await service.submitIssue(
        inspectionId: 'insp-sess-5555',
        issueType: 'PRICE_TAMPERING',
        title: 'Price Tampering on Biscuits',
        description: 'Dual MRP sticker detected.',
      );

      expect(report.id, 'issue-9999');
      expect(report.status, 'SUBMITTED');
      expect(report.jurisdictionVerified, isFalse);
      expect(report.department, 'LEGAL_METROLOGY');
    });

    test('submitIssue throws 401 when token is missing', () async {
      final service = ConsumerIssueApiService(
        baseUrl: 'http://localhost:8000/api/v1',
        authTokenProvider: () => null,
      );

      expect(
        () => service.submitIssue(
          inspectionId: 'insp-1',
          issueType: 'MISLEADING_LABEL',
          title: 'Test',
          description: 'Test',
        ),
        throwsA(
          isA<ConsumerIssueApiException>()
              .having((e) => e.statusCode, 'statusCode', 401)
              .having((e) => e.code, 'code', 'AUTHENTICATION_REQUIRED'),
        ),
      );
    });

    test('submitIssue throws 409 DUPLICATE_CONSUMER_ISSUE on conflict', () async {
      final mockClient = MockClient((request) async {
        return http.Response(
          jsonEncode({
            'detail': {
              'code': 'DUPLICATE_CONSUMER_ISSUE',
              'message': 'A consumer issue with this type already exists for this inspection.',
            }
          }),
          409,
          headers: {'content-type': 'application/json'},
        );
      });

      final service = ConsumerIssueApiService(
        baseUrl: 'http://localhost:8000/api/v1',
        httpClient: mockClient,
        authTokenProvider: () => 'valid-jwt-token',
      );

      expect(
        () => service.submitIssue(
          inspectionId: 'insp-1',
          issueType: 'PRICE_TAMPERING',
          title: 'Test',
          description: 'Test',
        ),
        throwsA(
          isA<ConsumerIssueApiException>()
              .having((e) => e.statusCode, 'statusCode', 409)
              .having((e) => e.code, 'code', 'DUPLICATE_CONSUMER_ISSUE'),
        ),
      );
    });

    test('submitIssue handles network exception gracefully', () async {
      final mockClient = MockClient((request) async {
        throw http.ClientException('Connection refused');
      });

      final service = ConsumerIssueApiService(
        baseUrl: 'http://localhost:8000/api/v1',
        httpClient: mockClient,
        authTokenProvider: () => 'valid-jwt-token',
      );

      expect(
        () => service.submitIssue(
          inspectionId: 'insp-1',
          issueType: 'PRICE_TAMPERING',
          title: 'Test',
          description: 'Test',
        ),
        throwsA(
          isA<ConsumerIssueApiException>()
              .having((e) => e.code, 'code', 'NETWORK_ERROR'),
        ),
      );
    });
  });

  group('ReportViolationDialog Widget Tests', () {
    testWidgets('renders form fields with preselected issue type and product info', (tester) async {
      final service = ConsumerIssueApiService(
        authTokenProvider: () => 'valid-token',
      );

      await tester.pumpWidget(
        MaterialApp(
          home: Scaffold(
            body: ReportViolationDialog(
              analysis: dummyAnalysis,
              inspectionId: 'insp-sess-1234',
              ocrText: 'Sample OCR raw text',
              apiService: service,
            ),
          ),
        ),
      );

      expect(find.text('Report Violation'), findsOneWidget);
      expect(find.text('Legal Metrology Department Complaint'), findsOneWidget);
      expect(find.text('Target Product: Britannia Good Day Biscuits'), findsOneWidget);
      expect(find.byKey(const Key('issue_type_dropdown')), findsOneWidget);
      expect(find.byKey(const Key('issue_title_input')), findsOneWidget);
      expect(find.byKey(const Key('issue_description_input')), findsOneWidget);
      expect(find.byKey(const Key('submit_complaint_button')), findsOneWidget);

      // Verify inferred issue type for "Price Tampering"
      expect(find.text('Price Tampering / Dual MRP'), findsOneWidget);
    });

    testWidgets('shows validation error when title or description is empty', (tester) async {
      final service = ConsumerIssueApiService(
        authTokenProvider: () => 'valid-token',
      );

      await tester.pumpWidget(
        MaterialApp(
          home: Scaffold(
            body: ReportViolationDialog(
              analysis: dummyAnalysis,
              inspectionId: 'insp-sess-1234',
              ocrText: 'Sample OCR raw text',
              apiService: service,
            ),
          ),
        ),
      );

      // Clear title
      await tester.enterText(find.byKey(const Key('issue_title_input')), '');
      await tester.ensureVisible(find.byKey(const Key('submit_complaint_button')));
      await tester.tap(find.byKey(const Key('submit_complaint_button')));
      await tester.pump();

      expect(find.byKey(const Key('report_error_banner')), findsOneWidget);
      expect(find.text('Please provide a short summary title.'), findsOneWidget);

      // Set title, clear description
      await tester.enterText(find.byKey(const Key('issue_title_input')), 'Valid Title');
      await tester.enterText(find.byKey(const Key('issue_description_input')), '');
      await tester.ensureVisible(find.byKey(const Key('submit_complaint_button')));
      await tester.tap(find.byKey(const Key('submit_complaint_button')));
      await tester.pump();

      expect(find.byKey(const Key('report_error_banner')), findsOneWidget);
      expect(find.text('Please describe the observed violation.'), findsOneWidget);
    });

    testWidgets('submits complaint successfully and shows unverified jurisdiction message', (tester) async {
      final issueCompleter = Completer<http.Response>();

      final mockClient = MockClient((request) async {
        if (request.url.path.endsWith('/inspections')) {
          return http.Response(
            jsonEncode({'inspection_id': 'auto-session-777'}),
            200,
            headers: {'content-type': 'application/json'},
          );
        }
        if (request.url.path.endsWith('/consumer-issues')) {
          return issueCompleter.future;
        }
        return http.Response('Not Found', 404);
      });

      final service = ConsumerIssueApiService(
        baseUrl: 'http://localhost:8000/api/v1',
        httpClient: mockClient,
        authTokenProvider: () => 'valid-token',
      );

      await tester.pumpWidget(
        MaterialApp(
          home: Scaffold(
            body: ReportViolationDialog(
              analysis: dummyAnalysis,
              inspectionId: null, // Test auto-creation of inspection session
              ocrText: 'Sample OCR raw text',
              apiService: service,
            ),
          ),
        ),
      );

      await tester.ensureVisible(find.byKey(const Key('submit_complaint_button')));
      await tester.tap(find.byKey(const Key('submit_complaint_button')));
      await tester.pump();

      // In-flight progress indicator is displayed
      expect(find.byType(CircularProgressIndicator), findsOneWidget);

      issueCompleter.complete(
        http.Response(
          jsonEncode({
            'id': 'issue-comp-42',
            'user_id': 'user-111',
            'inspection_id': 'auto-session-777',
            'saved_product_id': null,
            'issue_type': 'PRICE_TAMPERING',
            'title': 'Violation on Britannia Good Day Biscuits',
            'description': 'Dual MRP observed',
            'status': 'SUBMITTED',
            'resolution_notes': null,
            'evidence_images': [],
            'department': 'LEGAL_METROLOGY',
            'state_code': null,
            'district_code': null,
            'jurisdiction_verified': false,
            'created_at': '2026-10-05T01:10:00Z',
            'updated_at': '2026-10-05T01:10:00Z',
          }),
          201,
          headers: {'content-type': 'application/json'},
        ),
      );

      await tester.pumpAndSettle();

      // Success view displayed
      expect(find.text('Complaint Filed Successfully'), findsOneWidget);
      expect(find.text('Reference ID: issue-comp-42'), findsOneWidget);
      expect(find.text('Status: SUBMITTED'), findsOneWidget);
      expect(find.text('Jurisdiction Pending Verification'), findsOneWidget);
      expect(
        find.text(
          'Your complaint has been securely submitted. It will be routed to the appropriate Legal Metrology enforcement queue once retail premises jurisdiction is verified.',
        ),
        findsOneWidget,
      );
    });

    testWidgets('shows verified jurisdiction message when jurisdiction_verified is true', (tester) async {
      final mockClient = MockClient((request) async {
        return http.Response(
          jsonEncode({
            'id': 'issue-comp-99',
            'user_id': 'user-111',
            'inspection_id': 'insp-verified-1',
            'saved_product_id': null,
            'issue_type': 'PRICE_TAMPERING',
            'title': 'Verified Complaint',
            'description': 'Verified description',
            'status': 'SUBMITTED',
            'resolution_notes': null,
            'evidence_images': [],
            'department': 'LEGAL_METROLOGY',
            'state_code': 'MH',
            'district_code': 'PUNE',
            'jurisdiction_verified': true,
            'created_at': '2026-10-05T01:10:00Z',
            'updated_at': '2026-10-05T01:10:00Z',
          }),
          201,
          headers: {'content-type': 'application/json'},
        );
      });

      final service = ConsumerIssueApiService(
        baseUrl: 'http://localhost:8000/api/v1',
        httpClient: mockClient,
        authTokenProvider: () => 'valid-token',
      );

      await tester.pumpWidget(
        MaterialApp(
          home: Scaffold(
            body: ReportViolationDialog(
              analysis: dummyAnalysis,
              inspectionId: 'insp-verified-1',
              ocrText: 'Sample OCR raw text',
              apiService: service,
            ),
          ),
        ),
      );

      await tester.ensureVisible(find.byKey(const Key('submit_complaint_button')));
      await tester.tap(find.byKey(const Key('submit_complaint_button')));
      await tester.pumpAndSettle();

      expect(find.text('Jurisdiction Verified'), findsOneWidget);
      expect(
        find.text('Routed to LEGAL_METROLOGY Department (MH / PUNE).'),
        findsOneWidget,
      );
    });

    testWidgets('handles duplicate complaint error (409) with friendly banner', (tester) async {
      final mockClient = MockClient((request) async {
        return http.Response(
          jsonEncode({
            'detail': {
              'code': 'DUPLICATE_CONSUMER_ISSUE',
              'message': 'Duplicate issue.',
            }
          }),
          409,
          headers: {'content-type': 'application/json'},
        );
      });

      final service = ConsumerIssueApiService(
        baseUrl: 'http://localhost:8000/api/v1',
        httpClient: mockClient,
        authTokenProvider: () => 'valid-token',
      );

      await tester.pumpWidget(
        MaterialApp(
          home: Scaffold(
            body: ReportViolationDialog(
              analysis: dummyAnalysis,
              inspectionId: 'insp-sess-dup',
              ocrText: 'Sample OCR raw text',
              apiService: service,
            ),
          ),
        ),
      );

      await tester.ensureVisible(find.byKey(const Key('submit_complaint_button')));
      await tester.tap(find.byKey(const Key('submit_complaint_button')));
      await tester.pumpAndSettle();

      expect(find.byKey(const Key('report_error_banner')), findsOneWidget);
      expect(
        find.text(
          'Duplicate Complaint: A complaint for this issue type has already been submitted for this product.',
        ),
        findsOneWidget,
      );
    });

    testWidgets('handles 401 authentication error gracefully', (tester) async {
      final mockClient = MockClient((request) async {
        return http.Response(
          jsonEncode({'detail': 'Not authenticated'}),
          401,
          headers: {'content-type': 'application/json'},
        );
      });

      final service = ConsumerIssueApiService(
        baseUrl: 'http://localhost:8000/api/v1',
        httpClient: mockClient,
        authTokenProvider: () => 'expired-token',
      );

      await tester.pumpWidget(
        MaterialApp(
          home: Scaffold(
            body: ReportViolationDialog(
              analysis: dummyAnalysis,
              inspectionId: 'insp-sess-auth',
              ocrText: 'Sample OCR raw text',
              apiService: service,
            ),
          ),
        ),
      );

      await tester.ensureVisible(find.byKey(const Key('submit_complaint_button')));
      await tester.tap(find.byKey(const Key('submit_complaint_button')));
      await tester.pumpAndSettle();

      expect(find.byKey(const Key('report_error_banner')), findsOneWidget);
      expect(
        find.text('Authentication required. Please sign in to file a complaint.'),
        findsOneWidget,
      );
    });

    testWidgets('re-uses established inspection session ID on retry without creating duplicate sessions', (tester) async {
      int inspectionCreationCalls = 0;
      int issueSubmissionCalls = 0;
      String? firstInspectionIdSent;
      String? secondInspectionIdSent;

      final mockClient = MockClient((request) async {
        if (request.url.path.endsWith('/inspections')) {
          inspectionCreationCalls++;
          return http.Response(
            jsonEncode({'inspection_id': 'sess-reuse-123'}),
            200,
            headers: {'content-type': 'application/json'},
          );
        }
        if (request.url.path.endsWith('/consumer-issues')) {
          issueSubmissionCalls++;
          final body = jsonDecode(request.body) as Map<String, dynamic>;
          if (issueSubmissionCalls == 1) {
            firstInspectionIdSent = body['inspection_id'] as String?;
            // First submit attempt fails due to network glitch
            throw http.ClientException('Socket connection timeout');
          } else {
            secondInspectionIdSent = body['inspection_id'] as String?;
            return http.Response(
              jsonEncode({
                'id': 'issue-comp-retry-ok',
                'user_id': 'user-111',
                'inspection_id': secondInspectionIdSent,
                'saved_product_id': null,
                'issue_type': 'PRICE_TAMPERING',
                'title': 'Violation on Britannia Good Day Biscuits',
                'description': 'Dual MRP observed',
                'status': 'SUBMITTED',
                'resolution_notes': null,
                'evidence_images': [],
                'department': 'LEGAL_METROLOGY',
                'state_code': null,
                'district_code': null,
                'jurisdiction_verified': false,
                'created_at': '2026-10-05T01:10:00Z',
                'updated_at': '2026-10-05T01:10:00Z',
              }),
              201,
              headers: {'content-type': 'application/json'},
            );
          }
        }
        return http.Response('Not Found', 404);
      });

      final service = ConsumerIssueApiService(
        baseUrl: 'http://localhost:8000/api/v1',
        httpClient: mockClient,
        authTokenProvider: () => 'valid-token',
      );

      await tester.pumpWidget(
        MaterialApp(
          home: Scaffold(
            body: ReportViolationDialog(
              analysis: dummyAnalysis,
              inspectionId: null, // Test auto-creation and reuse
              ocrText: 'Sample OCR raw text',
              apiService: service,
            ),
          ),
        ),
      );

      // Attempt 1: First submit attempt
      await tester.ensureVisible(find.byKey(const Key('submit_complaint_button')));
      await tester.tap(find.byKey(const Key('submit_complaint_button')));
      await tester.pumpAndSettle();

      // Verify attempt 1 failure handled
      expect(find.byKey(const Key('report_error_banner')), findsOneWidget);
      expect(inspectionCreationCalls, 1);
      expect(issueSubmissionCalls, 1);
      expect(firstInspectionIdSent, 'sess-reuse-123');

      // Attempt 2: Retry submit
      await tester.ensureVisible(find.byKey(const Key('submit_complaint_button')));
      await tester.tap(find.byKey(const Key('submit_complaint_button')));
      await tester.pumpAndSettle();

      // Verify inspection creation was NOT called a second time
      expect(inspectionCreationCalls, 1);
      expect(issueSubmissionCalls, 2);
      expect(secondInspectionIdSent, 'sess-reuse-123');

      // Verify success screen displayed
      expect(find.text('Complaint Filed Successfully'), findsOneWidget);
      expect(find.text('Reference ID: issue-comp-retry-ok'), findsOneWidget);
    });
  });

  group('AnalysisResultScreen Report Violation Integration Tests', () {
    testWidgets('renders Report Violation button on AnalysisResultScreen', (tester) async {
      final service = ConsumerIssueApiService(
        authTokenProvider: () => 'valid-token',
      );

      await tester.pumpWidget(
        MaterialApp(
          home: AnalysisResultScreen(
            analysis: dummyAnalysis,
            ocrText: 'Sample OCR text',
            apiService: service,
          ),
        ),
      );

      expect(find.byKey(const Key('report_violation_button')), findsOneWidget);
      expect(find.text('Report Violation to Legal Metrology'), findsOneWidget);
    });

    testWidgets('shows auth required SnackBar when user is not authenticated', (tester) async {
      final service = ConsumerIssueApiService(
        authTokenProvider: () => null, // Unauthenticated
      );

      await tester.pumpWidget(
        MaterialApp(
          home: AnalysisResultScreen(
            analysis: dummyAnalysis,
            ocrText: 'Sample OCR text',
            apiService: service,
          ),
        ),
      );

      await tester.ensureVisible(find.byKey(const Key('report_violation_button')));
      await tester.tap(find.byKey(const Key('report_violation_button')));
      await tester.pump();

      expect(
        find.text('Authentication required. Please sign in to report a violation.'),
        findsOneWidget,
      );
    });

    testWidgets('opens ReportViolationDialog when user is authenticated', (tester) async {
      final service = ConsumerIssueApiService(
        authTokenProvider: () => 'valid-token',
      );

      await tester.pumpWidget(
        MaterialApp(
          home: AnalysisResultScreen(
            analysis: dummyAnalysis,
            ocrText: 'Sample OCR text',
            inspectionId: 'insp-sess-screen-test',
            apiService: service,
          ),
        ),
      );

      await tester.ensureVisible(find.byKey(const Key('report_violation_button')));
      await tester.tap(find.byKey(const Key('report_violation_button')));
      await tester.pumpAndSettle();

      expect(find.byType(ReportViolationDialog), findsOneWidget);
      expect(find.text('Report Violation'), findsOneWidget);
    });
  });
}
