import 'dart:convert';

import 'package:flutter/foundation.dart';
import 'package:http/http.dart' as http;

import 'compliance_analysis.dart';

class GeminiAIAnalysisService {
  GeminiAIAnalysisService({
    String? apiKey,
    this.model = 'gemini-3.6-flash',
    http.Client? client,
  })  : apiKey = apiKey ?? const String.fromEnvironment(
          'GEMINI_API_KEY',
          defaultValue: '',
        ),
        _client = client ?? http.Client();

  final String apiKey;
  final String model;
  final http.Client _client;

  Future<ComplianceAnalysis> analyzeProductLabel(
    String extractedText, {
    String legalContext = '',
  }) async {
    final trimmedText = extractedText.trim();

    if (trimmedText.isEmpty || trimmedText.toLowerCase().contains('no text detected')) {
      throw const AIAnalysisException(
        'No OCR text is available to analyze. Please capture a product image first.',
      );
    }

    if (apiKey.trim().isEmpty) {
      throw const AIAnalysisException(
        'Gemini API key is not configured. Use --dart-define=GEMINI_API_KEY=your_key_here',
      );
    }

    final response = await _client.post(
      Uri.https(
        'generativelanguage.googleapis.com',
        '/v1beta/models/$model:generateContent',
        {'key': apiKey},
      ),
      headers: const {'Content-Type': 'application/json'},
      body: jsonEncode({
        'contents': [
          {
            'parts': [
              {'text': _buildPrompt(trimmedText, legalContext)},
            ],
          },
        ],
        'generationConfig': {
          'temperature': 0.2,
          'responseMimeType': 'application/json',
        },
      }),
    );

    if (response.statusCode < 200 || response.statusCode >= 300) {
      throw AIAnalysisException(
        'Gemini API request failed with status ${response.statusCode}: ${response.body}',
      );
    }

    try {
      final decoded = jsonDecode(response.body);
      final candidates = decoded['candidates'] as List?;
      final parts = candidates?.first['content']?['parts'] as List?;
      final content = parts?.first['text'];

      if (content is! String || content.trim().isEmpty) {
        throw const AIAnalysisException('Gemini API returned no JSON content.');
      }

      final parsedJson = jsonDecode(content);
      if (parsedJson is! Map<String, dynamic>) {
        throw const AIAnalysisException('Gemini API returned unexpected JSON structure.');
      }

      final possibleIssues = parsedJson['possibleIssues'] is List
          ? List<dynamic>.from(parsedJson['possibleIssues'] as List)
          : const <dynamic>[];

      if (legalContext.trim().isNotEmpty) {
        final normalizedLegalContext = legalContext.trim();
        for (final issue in possibleIssues) {
          if (issue is! Map) continue;
          final issueTitle = issue['title']?.toString() ?? 'Untitled';
          final citedRules = issue['ruleNumbers'] is List
              ? List<dynamic>.from(issue['ruleNumbers'] as List)
              : const <dynamic>[];
          final validRules = citedRules
              .map((rule) => rule.toString())
              .where((rule) => rule.trim().isNotEmpty)
              .where((rule) => normalizedLegalContext.contains(rule.trim()))
              .toList();

          debugPrint(
            'RAG: Gemini cited rules for issue "$issueTitle" -> ${citedRules.map((entry) => entry.toString()).toList()}',
          );

          if (validRules.length != citedRules.length) {
            debugPrint(
              'RAG: Gemini rule restriction warning for "$issueTitle". Non-context rule numbers were removed.',
            );
          }

          issue['ruleNumbers'] = validRules;
          if (issue['ruleTitles'] is List) {
            final titles = List<dynamic>.from(issue['ruleTitles'] as List);
            final mappedTitles = <dynamic>[];
            for (var i = 0; i < validRules.length && i < titles.length; i++) {
              mappedTitles.add(titles[i]);
            }
            issue['ruleTitles'] = mappedTitles;
          }
        }
      }

      final analysis = ComplianceAnalysis.fromJson(parsedJson);

for (final issue in analysis.possibleIssues) {
  debugPrint('================================');
  debugPrint('ISSUE: ${issue.title}');
  debugPrint('VERIFICATION STATUS: ${issue.verificationStatus}');
  debugPrint('RULE NUMBERS: ${issue.ruleNumbers}');
  debugPrint('RULE TITLES: ${issue.ruleTitles}');
  debugPrint('LEGAL BASIS: ${issue.legalBasis}');
  debugPrint('OCR EVIDENCE: ${issue.ocrEvidence}');
  debugPrint('================================');
}

return analysis;
    } catch (error) {
      if (error is AIAnalysisException) {
        rethrow;
      }
      throw AIAnalysisException('Failed to parse Gemini response as JSON: $error');
    }
  }

  String _buildPrompt(String extractedText, String legalContext) {
    final hasLegalContext = legalContext.trim().isNotEmpty;
    debugPrint('RAG: Gemini legal context passed = $hasLegalContext');
    final contextBlock = hasLegalContext
        ? legalContext
        : 'No legal context was retrieved. Apply the existing analysis behavior, but do not claim any legal verification without support from the retrieved rules.';

    return '''
You are an expert legal metrology compliance assistant.
Analyze the product label text and return valid JSON only, without markdown fences.

Rules for evidence and legal verification:
1. Extract only facts present in the OCR text. Use an empty string when a value is missing or unclear.
2. Add missing or unclear mandatory declarations to missingInformation.
3. For possibleIssues, distinguish clearly between:
   - "legally verified violation": a specific issue supported by one or more retrieved legal rules in LEGAL CONTEXT.
   - "observation or possible concern": a suspicious condition or possible risk that is not clearly supported by a retrieved rule. Do not label this as a legally verified violation.
4. If legal context is available, every legally verified violation must cite the specific rule number(s) and title(s) from the supplied LEGAL CONTEXT only. Never invent rule numbers or titles.
5. If no retrieved rule supports the issue, it may only be listed as a general observation or possible concern, and it must not be presented as a confirmed legal violation.
6. Use OCR evidence directly from the product text for every supported violation or observation.
7. Include a concise legalBasis explaining how the retrieved rule applies to the OCR evidence.
8. Use severity values: low, medium, or high.
9. Never include rule numbers or titles not present in LEGAL CONTEXT.
10. Every possible issue MUST contain verificationStatus.

Use exactly one of these values:

- "legally_verified":
  Use ONLY when a specific rule from LEGAL CONTEXT supports the issue
  AND the OCR evidence clearly supports the finding.

- "possible_concern":
  Use when a retrieved rule may be relevant, but the OCR evidence is
  incomplete, unclear, or insufficient to confirm a violation.

- "cannot_determine":
  Use when the OCR/product information is insufficient to determine
  whether compliance with a relevant rule can be verified.

- "general_observation":
  Use when the finding is only an observation and no retrieved legal
  rule clearly supports it.

11. If verificationStatus is "legally_verified", ruleNumbers and
ruleTitles MUST NOT be empty.

12. Never mark an issue as "legally_verified" unless BOTH:
    - a retrieved rule supports it, AND
    - OCR evidence supports it.

13. If no retrieved rule supports the issue, use either
"general_observation" or "possible_concern". Never use
"legally_verified".
Return exactly this JSON shape:
{
  "productName": "",
  "mrp": "",
  "netQuantity": "",
  "manufacturer": "",
  "address": "",
  "packingDate": "",
  "customerCare": "",
  "missingInformation": [],
  "possibleIssues": [
    {
      "title": "",
      "description": "",
      "severity": "low",
"verificationStatus": "general_observation",
"ruleNumbers": [""],
      "ruleTitles": [""],
      "legalBasis": "",
      "ocrEvidence": ""
    }
  ]
}

Important output requirements:
- For each supported legal violation, include ruleNumbers and ruleTitles as arrays of strings copied exactly from LEGAL CONTEXT.
- If multiple rules support the same issue, include all relevant rule numbers and titles.
- If no rule is supported by LEGAL CONTEXT, set ruleNumbers and ruleTitles to [] and put the finding in description as an observation or possible concern rather than a legally verified violation.
- The legalBasis field must explain the legal rule's requirement using the retrieved rule text.
- The ocrEvidence field must quote or paraphrase the relevant OCR/product information.
- The title should be a short issue label, while the description should clearly distinguish between a legally verified violation and an observation or possible concern.
- Every possible issue must include verificationStatus.
- The verificationStatus must exactly match one of:
  legally_verified, possible_concern, cannot_determine,
  general_observation.
- Only legally_verified issues should be presented as confirmed legal violations.
OCR text:
$extractedText

LEGAL CONTEXT:
$contextBlock
''';
  }

  void dispose() => _client.close();
}
