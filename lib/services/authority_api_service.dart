import 'dart:convert';
import 'package:http/http.dart' as http;
import 'package:supabase_flutter/supabase_flutter.dart';

/// Exception thrown when Authority API request fails.
class AuthorityApiException implements Exception {
  final int statusCode;
  final String code;
  final String message;
  final Map<String, dynamic> details;

  const AuthorityApiException({
    required this.statusCode,
    required this.code,
    required this.message,
    this.details = const {},
  });

  @override
  String toString() => 'AuthorityApiException($statusCode, $code): $message';
}

/// Models for Authority Case Management.
class AuthorityCaseSummary {
  final String id;
  final String userId;
  final String? inspectionId;
  final String? savedProductId;
  final String issueType;
  final String title;
  final String status;
  final String department;
  final String? stateCode;
  final String? districtCode;
  final bool jurisdictionVerified;
  final String? assignedOfficerId;
  final DateTime? assignedAt;
  final String? assignedBy;
  final DateTime createdAt;
  final DateTime updatedAt;

  const AuthorityCaseSummary({
    required this.id,
    required this.userId,
    this.inspectionId,
    this.savedProductId,
    required this.issueType,
    required this.title,
    required this.status,
    required this.department,
    this.stateCode,
    this.districtCode,
    required this.jurisdictionVerified,
    this.assignedOfficerId,
    this.assignedAt,
    this.assignedBy,
    required this.createdAt,
    required this.updatedAt,
  });

  factory AuthorityCaseSummary.fromJson(Map<String, dynamic> json) {
    return AuthorityCaseSummary(
      id: json['id'] as String,
      userId: json['user_id'] as String,
      inspectionId: json['inspection_id'] as String?,
      savedProductId: json['saved_product_id'] as String?,
      issueType: json['issue_type'] as String,
      title: json['title'] as String,
      status: json['status'] as String,
      department: json['department'] as String,
      stateCode: json['state_code'] as String?,
      districtCode: json['district_code'] as String?,
      jurisdictionVerified: json['jurisdiction_verified'] as bool? ?? false,
      assignedOfficerId: json['assigned_officer_id'] as String?,
      assignedAt: json['assigned_at'] != null ? DateTime.parse(json['assigned_at'] as String) : null,
      assignedBy: json['assigned_by'] as String?,
      createdAt: DateTime.parse(json['created_at'] as String),
      updatedAt: DateTime.parse(json['updated_at'] as String),
    );
  }
}

class AuthorityCaseDetail {
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
  final String? assignedOfficerId;
  final DateTime? assignedAt;
  final String? assignedBy;
  final DateTime createdAt;
  final DateTime updatedAt;

  const AuthorityCaseDetail({
    required this.id,
    required this.userId,
    this.inspectionId,
    this.savedProductId,
    required this.issueType,
    required this.title,
    required this.description,
    required this.status,
    this.resolutionNotes,
    required this.evidenceImages,
    required this.department,
    this.stateCode,
    this.districtCode,
    required this.jurisdictionVerified,
    this.assignedOfficerId,
    this.assignedAt,
    this.assignedBy,
    required this.createdAt,
    required this.updatedAt,
  });

  factory AuthorityCaseDetail.fromJson(Map<String, dynamic> json) {
    return AuthorityCaseDetail(
      id: json['id'] as String,
      userId: json['user_id'] as String,
      inspectionId: json['inspection_id'] as String?,
      savedProductId: json['saved_product_id'] as String?,
      issueType: json['issue_type'] as String,
      title: json['title'] as String,
      description: json['description'] as String? ?? '',
      status: json['status'] as String,
      resolutionNotes: json['resolution_notes'] as String?,
      evidenceImages: (json['evidence_images'] as List<dynamic>?) ?? const [],
      department: json['department'] as String,
      stateCode: json['state_code'] as String?,
      districtCode: json['district_code'] as String?,
      jurisdictionVerified: json['jurisdiction_verified'] as bool? ?? false,
      assignedOfficerId: json['assigned_officer_id'] as String?,
      assignedAt: json['assigned_at'] != null ? DateTime.parse(json['assigned_at'] as String) : null,
      assignedBy: json['assigned_by'] as String?,
      createdAt: DateTime.parse(json['created_at'] as String),
      updatedAt: DateTime.parse(json['updated_at'] as String),
    );
  }
}

class CaseNote {
  final String id;
  final String issueId;
  final String authorId;
  final String noteText;
  final bool isInternal;
  final DateTime createdAt;
  final DateTime updatedAt;

  const CaseNote({
    required this.id,
    required this.issueId,
    required this.authorId,
    required this.noteText,
    required this.isInternal,
    required this.createdAt,
    required this.updatedAt,
  });

  factory CaseNote.fromJson(Map<String, dynamic> json) {
    return CaseNote(
      id: json['id'] as String,
      issueId: json['issue_id'] as String,
      authorId: json['author_id'] as String,
      noteText: json['note_text'] as String,
      isInternal: json['is_internal'] as bool? ?? true,
      createdAt: DateTime.parse(json['created_at'] as String),
      updatedAt: DateTime.parse(json['updated_at'] as String),
    );
  }
}

class CaseAuditEvent {
  final String id;
  final String? issueId;
  final String actorId;
  final String action;
  final String? previousState;
  final String? newState;
  final Map<String, dynamic> metadata;
  final DateTime createdAt;

  const CaseAuditEvent({
    required this.id,
    this.issueId,
    required this.actorId,
    required this.action,
    this.previousState,
    this.newState,
    required this.metadata,
    required this.createdAt,
  });

  factory CaseAuditEvent.fromJson(Map<String, dynamic> json) {
    return CaseAuditEvent(
      id: json['id'] as String,
      issueId: json['issue_id'] as String?,
      actorId: json['actor_id'] as String,
      action: (json['action'] ?? json['event_type'] ?? 'EVENT') as String,
      previousState: json['previous_state'] as String?,
      newState: json['new_state'] as String?,
      metadata: (json['metadata'] as Map<String, dynamic>?) ?? const {},
      createdAt: DateTime.parse(json['created_at'] as String),
    );
  }
}

/// Service to interact with Veriqoo Authority Case Management API.
class AuthorityApiService {
  final String baseUrl;
  final http.Client _httpClient;
  final String? Function()? _authTokenProvider;

  AuthorityApiService({
    String? baseUrl,
    http.Client? httpClient,
    String? Function()? authTokenProvider,
  })  : baseUrl = baseUrl ?? const String.fromEnvironment('VERIQOO_API_URL', defaultValue: 'http://localhost:8000/api/v1'),
        _httpClient = httpClient ?? http.Client(),
        _authTokenProvider = authTokenProvider;

  String? _getToken() {
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
    final token = _getToken();
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
          if (detail is Map<String, dynamic>) {
            code = detail['code'] as String? ?? code;
            message = detail['message'] as String? ?? message;
            details = (detail['details'] as Map<String, dynamic>?) ?? details;
          } else if (detail is String) {
            message = detail;
          }
        }
      }
    } catch (_) {
      message = response.body.isNotEmpty ? response.body : message;
    }

    throw AuthorityApiException(
      statusCode: statusCode,
      code: code,
      message: message,
      details: details,
    );
  }

  /// Lists complaints authorized within the authority officer's jurisdiction.
  Future<List<AuthorityCaseSummary>> listCases({
    String? status,
    String? issueType,
    bool? assigned,
    bool myCases = false,
    int limit = 20,
    int offset = 0,
  }) async {
    final uri = Uri.parse('$baseUrl/authority/cases').replace(
      queryParameters: {
        if (status != null && status.isNotEmpty) 'status': status,
        if (issueType != null && issueType.isNotEmpty) 'issue_type': issueType,
        if (assigned != null) 'assigned': assigned.toString(),
        if (myCases) 'my_cases': 'true',
        'limit': limit.toString(),
        'offset': offset.toString(),
      },
    );

    final response = await _httpClient.get(uri, headers: _buildHeaders());
    if (response.statusCode == 200) {
      final decoded = jsonDecode(response.body) as Map<String, dynamic>;
      final items = (decoded['items'] as List<dynamic>?) ?? [];
      return items.map((e) => AuthorityCaseSummary.fromJson(e as Map<String, dynamic>)).toList();
    }
    _handleErrorResponse(response);
  }

  /// Retrieves full case details.
  Future<AuthorityCaseDetail> getCaseDetails(String caseId) async {
    final uri = Uri.parse('$baseUrl/authority/cases/$caseId');
    final response = await _httpClient.get(uri, headers: _buildHeaders());
    if (response.statusCode == 200) {
      final decoded = jsonDecode(response.body) as Map<String, dynamic>;
      return AuthorityCaseDetail.fromJson(decoded);
    }
    _handleErrorResponse(response);
  }

  /// Assigns officer to case. Respects concurrency precondition.
  /// Self-assignment only (targetOfficerId can be null or current officer UUID).
  Future<Map<String, dynamic>> assignOfficer({
    required String caseId,
    String? targetOfficerId,
    String? expectedAssignedOfficerId,
    bool expectUnassigned = false,
  }) async {
    final uri = Uri.parse('$baseUrl/authority/cases/$caseId/assign');
    final body = <String, dynamic>{
      'expect_unassigned': expectUnassigned,
    };
    if (targetOfficerId != null) {
      body['officer_user_id'] = targetOfficerId;
    }
    if (expectedAssignedOfficerId != null) {
      body['expected_assigned_officer_id'] = expectedAssignedOfficerId;
    }

    final response = await _httpClient.post(
      uri,
      headers: _buildHeaders(),
      body: jsonEncode(body),
    );
    if (response.statusCode == 200) {
      return jsonDecode(response.body) as Map<String, dynamic>;
    }
    _handleErrorResponse(response);
  }

  /// Lists confidential investigation notes for a case.
  Future<List<CaseNote>> listNotes(String caseId) async {
    final uri = Uri.parse('$baseUrl/authority/cases/$caseId/notes');
    final response = await _httpClient.get(uri, headers: _buildHeaders());
    if (response.statusCode == 200) {
      final decoded = jsonDecode(response.body) as Map<String, dynamic>;
      final items = (decoded['items'] as List<dynamic>?) ?? [];
      return items.map((e) => CaseNote.fromJson(e as Map<String, dynamic>)).toList();
    }
    _handleErrorResponse(response);
  }

  /// Adds a confidential internal investigation note (1-5000 characters).
  Future<CaseNote> addNote({
    required String caseId,
    required String noteText,
  }) async {
    final uri = Uri.parse('$baseUrl/authority/cases/$caseId/notes');
    final response = await _httpClient.post(
      uri,
      headers: _buildHeaders(),
      body: jsonEncode({'note_text': noteText}),
    );
    if (response.statusCode == 201) {
      final decoded = jsonDecode(response.body) as Map<String, dynamic>;
      return CaseNote.fromJson(decoded);
    }
    _handleErrorResponse(response);
  }

  /// Transitions case status with mandatory optimistic locking check (expectedStatus).
  Future<Map<String, dynamic>> transitionStatus({
    required String caseId,
    required String newStatus,
    required String expectedStatus,
    String? resolutionNotes,
  }) async {
    final uri = Uri.parse('$baseUrl/authority/cases/$caseId/status');
    final body = <String, dynamic>{
      'new_status': newStatus,
      'expected_status': expectedStatus,
    };
    if (resolutionNotes != null && resolutionNotes.isNotEmpty) {
      body['resolution_notes'] = resolutionNotes;
    }

    final response = await _httpClient.patch(
      uri,
      headers: _buildHeaders(),
      body: jsonEncode(body),
    );
    if (response.statusCode == 200) {
      return jsonDecode(response.body) as Map<String, dynamic>;
    }
    _handleErrorResponse(response);
  }

  /// Retrieves chronological audit timeline for a case.
  Future<List<CaseAuditEvent>> getAuditTimeline(String caseId) async {
    final uri = Uri.parse('$baseUrl/authority/cases/$caseId/audit-timeline');
    final response = await _httpClient.get(uri, headers: _buildHeaders());
    if (response.statusCode == 200) {
      final decoded = jsonDecode(response.body) as Map<String, dynamic>;
      final items = (decoded['items'] as List<dynamic>?) ?? (decoded['events'] as List<dynamic>?) ?? [];
      return items.map((e) => CaseAuditEvent.fromJson(e as Map<String, dynamic>)).toList();
    }
    _handleErrorResponse(response);
  }
}
