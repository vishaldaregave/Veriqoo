import 'dart:convert';
import 'package:http/http.dart' as http;
import 'package:supabase_flutter/supabase_flutter.dart';

/// Exception thrown when a Consumer Issue API request fails.
class ConsumerIssueApiException implements Exception {
  final int statusCode;
  final String code;
  final String message;
  final Map<String, dynamic> details;

  const ConsumerIssueApiException({
    required this.statusCode,
    required this.code,
    required this.message,
    this.details = const {},
  });

  @override
  String toString() => 'ConsumerIssueApiException($statusCode, $code): $message';
}

/// Model representing a submitted consumer complaint / issue report.
class ConsumerIssueReport {
  final String id;
  final String userId;
  final String? inspectionId;
  final String? savedProductId;
  final String issueType;
  final String title;
  final String description;
  final String status;
  final String? resolutionNotes;
  final List<dynamic> evidenceImages;
  final String department;
  final String? stateCode;
  final String? districtCode;
  final bool jurisdictionVerified;
  final DateTime createdAt;
  final DateTime updatedAt;

  const ConsumerIssueReport({
    required this.id,
    required this.userId,
    this.inspectionId,
    this.savedProductId,
    required this.issueType,
    required this.title,
    required this.description,
    required this.status,
    this.resolutionNotes,
    this.evidenceImages = const [],
    required this.department,
    this.stateCode,
    this.districtCode,
    required this.jurisdictionVerified,
    required this.createdAt,
    required this.updatedAt,
  });

  factory ConsumerIssueReport.fromJson(Map<String, dynamic> json) {
    return ConsumerIssueReport(
      id: json['id'] as String,
      userId: json['user_id'] as String,
      inspectionId: json['inspection_id'] as String?,
      savedProductId: json['saved_product_id'] as String?,
      issueType: json['issue_type'] as String,
      title: json['title'] as String,
      description: json['description'] as String,
      status: json['status'] as String,
      resolutionNotes: json['resolution_notes'] as String?,
      evidenceImages: (json['evidence_images'] as List<dynamic>?) ?? const [],
      department: (json['department'] as String?) ?? 'LEGAL_METROLOGY',
      stateCode: json['state_code'] as String?,
      districtCode: json['district_code'] as String?,
      jurisdictionVerified: (json['jurisdiction_verified'] as bool?) ?? false,
      createdAt: DateTime.parse(json['created_at'] as String),
      updatedAt: DateTime.parse(json['updated_at'] as String),
    );
  }
}

/// Client service for the FastAPI Consumer Issue Reporting endpoints.
class ConsumerIssueApiService {
  final String baseUrl;
  final http.Client _httpClient;
  final String? Function()? _authTokenProvider;

  ConsumerIssueApiService({
    String? baseUrl,
    http.Client? httpClient,
    String? Function()? authTokenProvider,
  })  : baseUrl = baseUrl ??
            const String.fromEnvironment(
              'VERIQOO_API_URL',
              defaultValue: 'http://localhost:8000/api/v1',
            ),
        _httpClient = httpClient ?? http.Client(),
        _authTokenProvider = authTokenProvider;

  String? getToken() {
    final provider = _authTokenProvider;
    if (provider != null) {
      return provider();
    }
    try {
      return Supabase.instance.client.auth.currentSession?.accessToken;
    } catch (_) {
      return null;
    }
  }

  Map<String, String> _buildHeaders() {
    final headers = <String, String>{
      'Content-Type': 'application/json',
      'Accept': 'application/json',
    };
    final token = getToken();
    if (token != null && token.isNotEmpty) {
      headers['Authorization'] = 'Bearer $token';
    }
    return headers;
  }

  Never _handleErrorResponse(http.Response response) {
    int statusCode = response.statusCode;
    String code = 'UNKNOWN_ERROR';
    String message = 'An unexpected server error occurred.';
    Map<String, dynamic> details = {};

    try {
      final decoded = jsonDecode(response.body);
      if (decoded is Map<String, dynamic>) {
        if (decoded.containsKey('error') && decoded['error'] is Map) {
          final errMap = decoded['error'] as Map<String, dynamic>;
          code = (errMap['code'] as String?) ?? code;
          message = (errMap['message'] as String?) ?? message;
          details = (errMap['details'] as Map<String, dynamic>?) ?? details;
        } else if (decoded.containsKey('detail')) {
          final detail = decoded['detail'];
          if (detail is Map) {
            final detailMap = Map<String, dynamic>.from(detail);
            code = (detailMap['code'] as String?) ?? code;
            message = (detailMap['message'] as String?) ?? message;
            details = (detailMap['details'] as Map<String, dynamic>?) ?? details;
          } else if (detail is String) {
            message = detail;
          }
        }
      }
    } catch (_) {
      message = response.body.isNotEmpty ? response.body : response.reasonPhrase ?? message;
    }

    if (statusCode == 401 && code == 'UNKNOWN_ERROR') {
      code = 'AUTHENTICATION_REQUIRED';
      message = 'Authentication required. Please sign in.';
    } else if (statusCode == 409 && code == 'UNKNOWN_ERROR') {
      code = 'DUPLICATE_CONSUMER_ISSUE';
      message = 'A complaint for this issue type has already been submitted for this inspection.';
    }

    throw ConsumerIssueApiException(
      statusCode: statusCode,
      code: code,
      message: message,
      details: details,
    );
  }

  /// Ensures a persistent inspection session exists on the backend.
  /// If [productName] or other metadata is provided, initializes an inspection container.
  Future<String> ensureInspectionSession({
    required String productName,
    Map<String, dynamic>? metadata,
  }) async {
    final token = getToken();
    if (token == null || token.isEmpty) {
      throw const ConsumerIssueApiException(
        statusCode: 401,
        code: 'AUTHENTICATION_REQUIRED',
        message: 'Authentication required. Please sign in to submit a complaint.',
      );
    }

    final url = Uri.parse('$baseUrl/inspections');
    final meta = Map<String, dynamic>.from(metadata ?? {});
    meta['product_name'] = productName;

    try {
      final response = await _httpClient.post(
        url,
        headers: _buildHeaders(),
        body: jsonEncode({'metadata': meta}),
      );

      if (response.statusCode >= 200 && response.statusCode < 300) {
        final decoded = jsonDecode(response.body) as Map<String, dynamic>;
        final inspectionId = decoded['inspection_id'] as String?;
        if (inspectionId != null && inspectionId.isNotEmpty) {
          return inspectionId;
        }
      }
      _handleErrorResponse(response);
    } on http.ClientException catch (e) {
      throw ConsumerIssueApiException(
        statusCode: 0,
        code: 'NETWORK_ERROR',
        message: 'Could not connect to the Veriqoo server: ${e.message}',
      );
    }
  }

  /// Submit a verified consumer issue report to POST /api/v1/consumer-issues.
  Future<ConsumerIssueReport> submitIssue({
    required String inspectionId,
    required String issueType,
    required String title,
    required String description,
    String? savedProductId,
    List<String> evidenceImageIds = const [],
  }) async {
    final token = getToken();
    if (token == null || token.isEmpty) {
      throw const ConsumerIssueApiException(
        statusCode: 401,
        code: 'AUTHENTICATION_REQUIRED',
        message: 'Authentication required. Please sign in to submit a complaint.',
      );
    }

    final url = Uri.parse('$baseUrl/consumer-issues');
    final payload = <String, dynamic>{
      'inspection_id': inspectionId,
      'saved_product_id': savedProductId,
      'issue_type': issueType,
      'title': title.trim(),
      'description': description.trim(),
      'evidence_image_ids': evidenceImageIds,
    };

    try {
      final response = await _httpClient.post(
        url,
        headers: _buildHeaders(),
        body: jsonEncode(payload),
      );

      if (response.statusCode == 201) {
        final decoded = jsonDecode(response.body) as Map<String, dynamic>;
        return ConsumerIssueReport.fromJson(decoded);
      }
      _handleErrorResponse(response);
    } on http.ClientException catch (e) {
      throw ConsumerIssueApiException(
        statusCode: 0,
        code: 'NETWORK_ERROR',
        message: 'Could not connect to the Veriqoo server: ${e.message}',
      );
    }
  }
}
