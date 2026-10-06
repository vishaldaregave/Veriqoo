import 'dart:convert';

import 'package:flutter/foundation.dart';
import 'package:http/http.dart' as http;

import 'compliance_analysis.dart';

const String kDefaultGeminiApiKey = 'AIzaSyC1TxpUISiSwxOVO6Ti_3iWYFcWbISxgco';

class GeminiAIAnalysisService {
  GeminiAIAnalysisService({
    String? apiKey,
    this.model = 'gemini-flash-lite-latest',
    this.timeoutSeconds = 15,
    http.Client? client,
  })  : apiKey = (apiKey != null && apiKey.isNotEmpty)
            ? apiKey
            : const String.fromEnvironment(
                'GEMINI_API_KEY',
                defaultValue: kDefaultGeminiApiKey,
              ),
        _client = client ?? http.Client();

  final String apiKey;
  final String model;
  final int timeoutSeconds;
  final http.Client _client;

  Future<ComplianceAnalysis> analyzeProductLabel(
    String extractedText, {
    String legalContext = '',
    List<String>? imageBase64List,
  }) async {
    final trimmedText = extractedText.trim();
    final hasImages = imageBase64List != null && imageBase64List.isNotEmpty;

    // Remove section headers and placeholder notices to check if substantive text exists
    final substantiveText = trimmedText
        .replaceAll(RegExp(r'=+ IMAGE \d+.*=+'), '')
        .replaceAll(RegExp(r'no text detected[^\n]*', caseSensitive: false), '')
        .replaceAll(RegExp(r'ocr failed[^\n]*', caseSensitive: false), '')
        .trim();

    if (substantiveText.isEmpty && !hasImages) {
      throw const AIAnalysisException(
        'No OCR text or product images are available to analyze. Please capture a product image first.',
      );
    }

    if (apiKey.trim().isEmpty) {
      throw const AIAnalysisException(
        'Gemini API key is not configured. Use --dart-define=GEMINI_API_KEY=your_key_here',
      );
    }

    // Build multimodal parts: attach base64 images if available, followed by prompt text
    final parts = <Map<String, dynamic>>[];
    if (imageBase64List != null && imageBase64List.isNotEmpty) {
      for (final b64 in imageBase64List) {
        parts.add({
          'inline_data': {
            'mime_type': 'image/jpeg',
            'data': b64,
          }
        });
      }
    }
    parts.add({
      'text': _buildPrompt(
        trimmedText.isNotEmpty ? trimmedText : 'Analyze the product package images directly for Legal Metrology compliance.',
        legalContext,
      ),
    });

    final response = await _client
        .post(
          Uri.https(
            'generativelanguage.googleapis.com',
            '/v1beta/models/$model:generateContent',
            {'key': apiKey},
          ),
          headers: const {'Content-Type': 'application/json'},
          body: jsonEncode({
            'contents': [
              {
                'parts': parts,
              },
            ],
            'generationConfig': {
              'temperature': 0.2,
              // NOTE: Do NOT set responseMimeType here — it causes empty output
              // on thinking-capable models (gemini-2.5-flash). We extract JSON
              // manually from the text response instead.
            },
          }),
        )
        .timeout(
          Duration(seconds: timeoutSeconds),
          onTimeout: () => throw const AIAnalysisException(
            'Gemini API request timed out. The model took too long to respond. Please try again.',
          ),
        );

    if (response.statusCode < 200 || response.statusCode >= 300) {
      throw AIAnalysisException(
        'Gemini API request failed with status ${response.statusCode}: ${response.body}',
      );
    }

    try {
      final decoded = jsonDecode(response.body);
      final candidates = decoded['candidates'] as List?;

      // Check for safety or content filter blocks
      if (candidates == null || candidates.isEmpty) {
        final blockReason = decoded['promptFeedback']?['blockReason'];
        if (blockReason != null) {
          throw AIAnalysisException('Gemini blocked the request: $blockReason');
        }
        throw const AIAnalysisException('Gemini API returned no candidates in response.');
      }

      final rawParts = candidates.first['content']?['parts'] as List?;
      final content = rawParts?.first['text'];

      if (content is! String || content.trim().isEmpty) {
        // Try to get finish reason for better error messages
        final finishReason = candidates.first['finishReason'];
        throw AIAnalysisException(
          'Gemini API returned no text content (finishReason: $finishReason). '
          'This can happen with large images or strict safety filters.',
        );
      }

      // Strip markdown code fences if present (e.g. ```json ... ```)
      var jsonText = content.trim();
      final fenceRegex = RegExp(r'^```(?:json)?\s*([\s\S]*?)\s*```$');
      final fenceMatch = fenceRegex.firstMatch(jsonText);
      if (fenceMatch != null) {
        jsonText = fenceMatch.group(1)!.trim();
      }

      // Extract first JSON object if there's surrounding text
      final jsonStartIndex = jsonText.indexOf('{');
      final jsonEndIndex = jsonText.lastIndexOf('}');
      if (jsonStartIndex != -1 && jsonEndIndex != -1 && jsonEndIndex > jsonStartIndex) {
        jsonText = jsonText.substring(jsonStartIndex, jsonEndIndex + 1);
      }

      final parsedJson = jsonDecode(jsonText);
      if (parsedJson is! Map<String, dynamic>) {
        throw const AIAnalysisException('Gemini API returned unexpected JSON structure.');
      }

      // --- PRODUCT PACKAGE VALIDATION ---
      // If Gemini determined this is not a product package, throw a specific exception
      final isProductPackage = parsedJson['isProductPackage'];
      if (isProductPackage == false) {
        final reason = parsedJson['notProductReason']?.toString() ??
            'The image does not appear to contain a packaged product label.';
        throw NotAProductException(reason);
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
              .map((rule) => rule.toString().trim())
              .where((rule) => rule.isNotEmpty)
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
You are an expert legal metrology compliance assistant for Indian packaged commodities.

FIRST: Determine if the provided image(s) and/or OCR text actually show a PACKAGED PRODUCT LABEL or packaging (such as food packets, bottles, boxes, jars, pouches, cans, or any retail product with a printed label).

If the image does NOT show a packaged product (e.g., it shows a person, landscape, document, screenshot, electronics, furniture, vehicle, blank surface, or anything that is not a retail product package), you MUST return:
{
  "isProductPackage": false,
  "notProductReason": "<brief one-sentence explanation of what the image actually shows>"
}

If the image DOES show a packaged product label, analyze it and return the FULL compliance JSON below. Always include "isProductPackage": true in that case.

Rules for evidence and legal verification:
1. Visually examine EVERY provided product package image thoroughly. Read all printed typography directly from the image (including small font, dot-matrix manufacturing dates, batch codes, net weight/volume, manufacturer physical address, MRP, and consumer care phone/email). Combine what you see in the images with the OCR text for 100% extraction accuracy.
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

Use exactly one of these values for verificationStatus:

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

Return exactly this JSON shape for a valid product:
{
  "isProductPackage": true,
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
