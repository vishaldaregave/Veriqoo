import 'dart:convert';

import 'package:flutter/foundation.dart';
import 'package:http/http.dart' as http;
import 'package:supabase_flutter/supabase_flutter.dart';

class LegalRulesRetrievalService {
  LegalRulesRetrievalService({
    String? apiKey,
    SupabaseClient? client,
    http.Client? httpClient,
  })  : apiKey = apiKey ??
            const String.fromEnvironment('GEMINI_API_KEY', defaultValue: ''),
        _client = client ?? Supabase.instance.client,
        _httpClient = httpClient ?? http.Client();

  static const model = 'gemini-embedding-001';
  static const vectorDimension = 3072;

  final String apiKey;
  final SupabaseClient _client;
  final http.Client _httpClient;

  Future<LegalRulesContext> retrieveLegalContext(String ocrText) async {
    final query = _buildQuery(ocrText);
    debugPrint('RAG: retrieval query generated (${query.length} characters)');
    final embedding = await _generateQueryEmbedding(query);
    final totalResponse = await _client
        .from('legal_rules')
        .select('rule_number')
        .not('embedding', 'is', null)
        .count(CountOption.exact);
    debugPrint('RAG: total embedded legal rules available = ${totalResponse.count}');
    final response = await _client.rpc(
      'match_legal_rules',
      params: {
        'query_embedding': embedding,
        'match_count': 51,
      },
    );
    final rules = List<Map<String, dynamic>>.from(response as List);
    debugPrint('RAG: rules retrieved = ${rules.length}');
    if (rules.isEmpty) return const LegalRulesContext.empty();

    final candidates = rules.map(LegalRule.fromJson).toList();
    final applicability = await _classifyApplicability(ocrText, candidates);
    final applicable = <LegalRule>[];
    final cannotDetermine = <LegalRule>[];
    for (final decision in applicability) {
      if (decision.status == RuleApplicability.applicable) {
        applicable.add(decision.rule);
      } else if (decision.status == RuleApplicability.cannotDetermine) {
        cannotDetermine.add(decision.rule);
      }
    }
    debugPrint('RAG: rules classified as applicable = ${applicable.length}');
    debugPrint('RAG: rules classified as not applicable = ${candidates.length - applicable.length - cannotDetermine.length}');
    debugPrint('RAG: rules classified as cannot determine = ${cannotDetermine.length}');

    return LegalRulesContext(
      applicable: applicable,
      cannotDetermine: cannotDetermine,
    );
  }

  Future<List<_ApplicabilityDecision>> _classifyApplicability(
    String ocrText,
    List<LegalRule> rules,
  ) async {
    if (apiKey.trim().isEmpty) {
      throw const LegalRulesRetrievalException('GEMINI_API_KEY is not configured.');
    }
    final response = await _httpClient.post(
      Uri.https(
        'generativelanguage.googleapis.com',
        '/v1beta/models/gemini-3.6-flash:generateContent',
        {'key': apiKey},
      ),
      headers: const {'Content-Type': 'application/json'},
      body: jsonEncode({
        'contents': [
          {
            'parts': [
              {'text': _buildApplicabilityPrompt(ocrText, rules)},
            ],
          },
        ],
        'generationConfig': {
          'temperature': 0.0,
          'responseMimeType': 'application/json',
        },
      }),
    );
    if (response.statusCode < 200 || response.statusCode >= 300) {
      throw LegalRulesRetrievalException(
        'Applicability request failed with status ${response.statusCode}: ${response.body}',
      );
    }
    final decoded = jsonDecode(response.body);
    final text = decoded['candidates']?[0]?['content']?['parts']?[0]?['text'];
    if (text is! String || text.trim().isEmpty) {
      throw const LegalRulesRetrievalException('Applicability response was empty.');
    }
    final decisions = jsonDecode(text)['decisions'];
    if (decisions is! List) {
      throw const LegalRulesRetrievalException('Applicability response had no decisions.');
    }
    final byRule = {for (final rule in rules) rule.ruleNumber: rule};
    final classified = decisions.map((item) {
      final map = Map<String, dynamic>.from(item as Map);
      final rule = byRule[map['rule_number']?.toString()];
      if (rule == null) return null;
      return _ApplicabilityDecision(
        rule: rule,
        status: RuleApplicability.fromValue(map['status']?.toString()),
      );
    }).whereType<_ApplicabilityDecision>().toList();
    final classifiedNumbers = classified.map((decision) => decision.rule.ruleNumber).toSet();
    classified.addAll(
      rules
          .where((rule) => !classifiedNumbers.contains(rule.ruleNumber))
          .map((rule) => _ApplicabilityDecision(
                rule: rule,
                status: RuleApplicability.cannotDetermine,
              )),
    );
    return classified;
  }

  String _buildApplicabilityPrompt(String ocrText, List<LegalRule> rules) {
    final ruleText = rules.map((rule) => '''Rule number: ${rule.ruleNumber}
Title: ${rule.title}
Category: ${rule.category}
Content:
${rule.content}''').join('\n\n');
    return '''Determine whether each legal rule is applicable to this inspected packaged product based only on the OCR/product information.

Use exactly one status for every rule:
- applicable: the rule clearly governs this package or a declaration that can be assessed for it.
- not_applicable: the rule clearly concerns a different commodity, package type, or circumstance.
- cannot_determine: available OCR/image information is insufficient to decide.

Never call a rule applicable merely because its topic is generally related. Return JSON only:
{"decisions":[{"rule_number":"...","status":"applicable|not_applicable|cannot_determine"}]}

OCR/product information:
$ocrText

Retrieved legal rules:
$ruleText''';
  }

  String _buildQuery(String ocrText) => '''Determine which Legal Metrology (Packaged Commodities) Rules, 2011 provisions are relevant to this packaged-product label and its declarations. Pay particular attention to manufacturer, packer, importer, net quantity, MRP, dates, consumer-care details, unit sale price, and missing declarations.

Product label OCR:
${ocrText.trim()}''';

  Future<List<double>> _generateQueryEmbedding(String query) async {
    if (apiKey.trim().isEmpty) {
      throw const LegalRulesRetrievalException('GEMINI_API_KEY is not configured.');
    }
    final response = await _httpClient.post(
      Uri.https(
        'generativelanguage.googleapis.com',
        '/v1beta/models/$model:embedContent',
        {'key': apiKey},
      ),
      headers: const {'Content-Type': 'application/json'},
      body: jsonEncode({
        'content': {'parts': [{'text': query}]},
        'taskType': 'RETRIEVAL_QUERY',
      }),
    );
    if (response.statusCode < 200 || response.statusCode >= 300) {
      throw LegalRulesRetrievalException(
        'Gemini embedding request failed with status ${response.statusCode}: ${response.body}',
      );
    }
    final values = jsonDecode(response.body)['embedding']?['values'];
    if (values is! List || values.length != vectorDimension) {
      throw LegalRulesRetrievalException(
        'Expected $vectorDimension embedding values, received ${values is List ? values.length : 'none'}.',
      );
    }
    return values.map<double>((value) => (value as num).toDouble()).toList();
  }

  void dispose() => _httpClient.close();
}

class LegalRulesRetrievalException implements Exception {
  const LegalRulesRetrievalException(this.message);
  final String message;
  @override
  String toString() => message;
}

class LegalRulesContext {
  const LegalRulesContext({required this.applicable, required this.cannotDetermine});
  const LegalRulesContext.empty()
      : applicable = const [],
        cannotDetermine = const [];

  final List<LegalRule> applicable;
  final List<LegalRule> cannotDetermine;

  String get formatted {
    final sections = <String>[];
    for (final rule in applicable) {
      sections.add(rule.format('APPLICABLE'));
    }
    for (final rule in cannotDetermine) {
      sections.add(rule.format('APPLICABILITY UNCERTAIN'));
    }
    return sections.join('\n\n');
  }
}

class LegalRule {
  const LegalRule({required this.ruleNumber, required this.title, required this.category, required this.content});

  factory LegalRule.fromJson(Map<String, dynamic> json) => LegalRule(
        ruleNumber: json['rule_number']?.toString() ?? 'unknown',
        title: json['title']?.toString() ?? 'Untitled rule',
        category: json['category']?.toString() ?? 'uncategorized',
        content: json['content']?.toString() ?? '',
      );

  final String ruleNumber;
  final String title;
  final String category;
  final String content;

  String format(String status) => '''Rule number: $ruleNumber
Title: $title
Category: $category
Applicability: $status
Content:
$content''';
}

enum RuleApplicability { applicable, notApplicable, cannotDetermine;
  static RuleApplicability fromValue(String? value) {
    switch (value) {
      case 'applicable':
        return applicable;
      case 'not_applicable':
        return notApplicable;
      default:
        return cannotDetermine;
    }
  }
}

class _ApplicabilityDecision {
  const _ApplicabilityDecision({required this.rule, required this.status});
  final LegalRule rule;
  final RuleApplicability status;
}
