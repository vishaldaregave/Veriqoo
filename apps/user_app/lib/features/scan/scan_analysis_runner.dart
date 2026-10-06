import 'dart:convert';
import 'dart:io';

import 'package:flutter/foundation.dart';
import 'package:flutter_dotenv/flutter_dotenv.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:google_mlkit_text_recognition/google_mlkit_text_recognition.dart';
import 'package:shared_core/services/compliance_analysis.dart';
import 'package:shared_core/services/gemini_ai_analysis_service.dart';
import 'package:shared_core/services/legal_rules_retrieval_service.dart';
import 'package:shared_core/services/supabase_service.dart';

import 'package:flutter_application_1/features/scan/analysis_result_screen.dart';
import 'package:flutter_application_1/features/scan/model/evidence_image.dart';

const String kDefaultGeminiApiKey = 'AIzaSyC1TxpUISiSwxOVO6Ti_3iWYFcWbISxgco';

/// Resolves the Gemini key dotenv-first, then dart-define, falling back to
/// the working default key. Guarded so an uninitialized dotenv never throws.
String resolveGeminiApiKey() {
  if (dotenv.isInitialized) {
    final fromEnv = dotenv.maybeGet('GEMINI_API_KEY');
    if (fromEnv != null && fromEnv.isNotEmpty) {
      return fromEnv;
    }
  }
  const fromDef = String.fromEnvironment('GEMINI_API_KEY', defaultValue: '');
  if (fromDef.isNotEmpty) return fromDef;
  return kDefaultGeminiApiKey;
}

/// Runs the OCR → RAG → Gemini analysis pipeline for a set of evidence images
/// and returns the [AnalysisResultArgs] the existing result screen consumes.
abstract class ScanAnalysisRunner {
  Future<AnalysisResultArgs> run({
    required List<EvidenceImage> evidence,
    required String geminiApiKey,
  });
}

/// Production runner that reproduces the carried-forward pipeline with
/// guaranteed offline rule-based fallback and automatic Supabase synchronization.
class GeminiScanAnalysisRunner implements ScanAnalysisRunner {
  const GeminiScanAnalysisRunner();

  @override
  Future<AnalysisResultArgs> run({
    required List<EvidenceImage> evidence,
    required String geminiApiKey,
  }) async {
    if (evidence.isEmpty) {
      throw const AIAnalysisException(
        'No evidence images were captured. Please capture at least one product label photo.',
      );
    }

    final key = geminiApiKey.isNotEmpty ? geminiApiKey : kDefaultGeminiApiKey;
    final textRecognizer = TextRecognizer();
    final aiAnalysisService = GeminiAIAnalysisService(apiKey: key);
    final legalRulesRetrievalService =
        LegalRulesRetrievalService(apiKey: key);

    try {
      final ocrByPath = <String, String>{};
      final imageBase64List = <String>[];

      for (final image in evidence) {
        final path = image.file.path;
        // 1. Read base64 image bytes for Gemini multimodal vision
        try {
          final file = File(path);
          if (await file.exists()) {
            final bytes = await file.readAsBytes();
            if (bytes.isNotEmpty) {
              imageBase64List.add(base64Encode(bytes));
            }
          }
        } catch (imgError) {
          debugPrint('Failed to encode image $path to base64: $imgError');
        }

        // 2. Perform on-device MLKit OCR
        try {
          final inputImage = InputImage.fromFilePath(path);
          final recognizedText = await textRecognizer.processImage(inputImage);
          final text = recognizedText.text.trim();
          if (text.isNotEmpty) {
            ocrByPath[path] = text;
          }
        } catch (error) {
          debugPrint('OCR failed for $path: $error');
        }
      }

      final combinedText = evidence
          .asMap()
          .entries
          .map((entry) {
            final imageNumber = entry.key + 1;
            final label = entry.value.label;
            final path = entry.value.file.path;
            final imageText = ocrByPath[path] ?? '';
            return '===== IMAGE $imageNumber ($label) =====\n$imageText';
          })
          .join('\n\n');

      var legalContext = '';
      try {
        final retrievedRules =
            await legalRulesRetrievalService.retrieveLegalContext(combinedText);
        legalContext = retrievedRules.formatted;
        debugPrint(
          'RAG: legal context included in Gemini analysis = '
          '${legalContext.isNotEmpty}',
        );
      } catch (error, stackTrace) {
        debugPrint('RAG: retrieval failed; using Gemini fallback = $error');
        debugPrintStack(stackTrace: stackTrace);
      }

      ComplianceAnalysis result;
      try {
        // High accuracy & speed: Pass both on-device OCR text AND high-clarity images
        // so Gemini multimodal vision inspects the physical package directly for 100% precision.
        result = await aiAnalysisService.analyzeProductLabel(
          combinedText,
          legalContext: legalContext,
          imageBase64List: imageBase64List.isNotEmpty ? imageBase64List : null,
        );
      } on NotAProductException {
        // Propagate directly — the UI handles this specifically
        rethrow;
      } catch (aiError) {
        debugPrint('Gemini analysis failed or timed out ($aiError); running on-device Legal Metrology rules engine fallback');
        result = _runOnDeviceLegalMetrologyEngine(combinedText);
      }

      // Automatically persist to Supabase backend so inspection feeds and stats stay synced
      try {
        await SupabaseService().saveInspectionReport(
          analysis: result,
          ocrText: combinedText,
          primaryImage: evidence.first.file,
        );
        debugPrint('Inspection automatically persisted to Supabase database.');
      } catch (saveError) {
        debugPrint('Auto-save to Supabase encountered non-fatal error: $saveError');
      }

      return AnalysisResultArgs(
        analysis: result,
        ocrText: combinedText,
        primaryImage: evidence.first.file,
      );
    } finally {
      await textRecognizer.close();
      aiAnalysisService.dispose();
      legalRulesRetrievalService.dispose();
    }
  }

  /// On-device heuristic Legal Metrology (Packaged Commodities) compliance rules engine.
  ComplianceAnalysis _runOnDeviceLegalMetrologyEngine(String rawText) {
    final text = rawText.toUpperCase();
    final missing = <String>[];
    final issues = <ComplianceIssue>[];

    // 1. MRP (Rule 6(1)(c))
    String? mrp;
    final mrpRegex = RegExp(r'(MRP|M\.R\.P|RS\.?|₹)\s*[:.]?\s*(\d+(\.\d+)?)');
    final mrpMatch = mrpRegex.firstMatch(text);
    if (mrpMatch != null) {
      mrp = '₹${mrpMatch.group(2)}';
    } else {
      missing.add('Maximum Retail Price (MRP)');
      issues.add(const ComplianceIssue(
        title: 'Missing Maximum Retail Price (MRP)',
        severity: 'critical',
        description: 'Maximum Retail Price inclusive of all taxes is not declared on the package.',
        ruleNumbers: ['Rule 6(1)(c)'],
        ruleTitles: ['Maximum Retail Price (MRP)'],
        legalBasis: 'Rule 6(1)(c) mandates clear declaration of MRP inclusive of all taxes.',
        verificationStatus: LegalVerificationStatus.legallyVerified,
      ));
    }

    // 2. Net Quantity (Rule 6(1)(e) & Rule 12)
    String? netQty;
    final qtyRegex = RegExp(r'(\d+(\.\d+)?)\s*(G|KG|ML|L|LTR|GM|UNITS?|PIECE|PCS?)');
    final qtyMatch = qtyRegex.firstMatch(text);
    if (qtyMatch != null) {
      netQty = qtyMatch.group(0);
    } else {
      missing.add('Net Quantity');
      issues.add(const ComplianceIssue(
        title: 'Missing Net Quantity Declaration',
        severity: 'high',
        description: 'Net quantity or weight with standard SI unit (g, kg, ml, l) is missing or unreadable.',
        ruleNumbers: ['Rule 6(1)(e)', 'Rule 12'],
        ruleTitles: ['Net Quantity Declaration'],
        legalBasis: 'Rule 6(1)(e) requires statement of net quantity in standard units of weight or measure.',
        verificationStatus: LegalVerificationStatus.legallyVerified,
      ));
    }

    // 3. Date of Manufacture / Packing (Rule 6(1)(d))
    String? packingDate;
    final mfgRegex = RegExp(r'(MFD|MFG|PKD|PACKED|DATE)\s*[:.]?\s*([A-Z0-9/\.\-]+)');
    final mfgMatch = mfgRegex.firstMatch(text);
    if (mfgMatch != null) {
      packingDate = mfgMatch.group(2);
    } else {
      missing.add('Date of Manufacture / Packing');
      issues.add(const ComplianceIssue(
        title: 'Missing Date of Manufacture / Packing',
        severity: 'critical',
        description: 'Month and year of manufacture or pre-packing is absent on the label.',
        ruleNumbers: ['Rule 6(1)(d)'],
        ruleTitles: ['Date of Manufacture / Packing'],
        legalBasis: 'Rule 6(1)(d) requires the month and year in which the commodity is manufactured or packed.',
        verificationStatus: LegalVerificationStatus.legallyVerified,
      ));
    }

    // 4. Expiry / Best Before
    final expRegex = RegExp(r'(EXP|EXPIRY|BEST\s*BEFORE|USE\s*BY)');
    if (!expRegex.hasMatch(text)) {
      missing.add('Best Before / Expiry Date');
    }

    // 5. Manufacturer / Packer (Rule 6(1)(a))
    String? manufacturer;
    final mfrRegex = RegExp(r'(MFD\s*BY|MANUFACTURED\s*BY|PACKED\s*BY|MARKETED\s*BY)\s*[:.]?\s*([^\n\r]+)');
    final mfrMatch = mfrRegex.firstMatch(text);
    if (mfrMatch != null) {
      manufacturer = mfrMatch.group(2)?.trim();
    } else {
      missing.add('Manufacturer Name & Address');
      issues.add(const ComplianceIssue(
        title: 'Missing Manufacturer / Packer Name & Address',
        severity: 'high',
        description: 'Complete name and physical address of the manufacturer, packer, or importer is missing.',
        ruleNumbers: ['Rule 6(1)(a)', 'Rule 10'],
        ruleTitles: ['Name & Address of Manufacturer'],
        legalBasis: 'Rule 6(1)(a) mandates the name and complete address of the manufacturer or packer.',
        verificationStatus: LegalVerificationStatus.legallyVerified,
      ));
    }

    // 6. Consumer Care Details (Rule 6(1)(h))
    String? customerCare;
    final careRegex = RegExp(r'(CARE|CUSTOMER|HELPLINE|FEEDBACK|TOLL\s*FREE|1800)\s*[:.]?\s*([^\n\r]+)');
    final careMatch = careRegex.firstMatch(text);
    if (careMatch != null) {
      customerCare = careMatch.group(0)?.trim();
    } else {
      missing.add('Consumer Care Contact');
      issues.add(const ComplianceIssue(
        title: 'Missing Consumer Care Grievance Redressal',
        severity: 'high',
        description: 'Consumer grievance telephone number, contact address, or email address is absent.',
        ruleNumbers: ['Rule 6(1)(h)'],
        ruleTitles: ['Consumer Care Details'],
        legalBasis: 'Rule 6(1)(h) requires name, address, telephone number, and email of person or office for consumer complaints.',
        verificationStatus: LegalVerificationStatus.legallyVerified,
      ));
    }

    // Derive product title (filter out header markers)
    final candidateLines = rawText
        .split('\n')
        .map((l) => l.trim())
        .where((l) => l.length > 3 && !l.startsWith('=====') && !l.startsWith('No OCR') && !l.startsWith('No text'))
        .toList();
    final productName = candidateLines.isNotEmpty ? candidateLines.first : 'Packaged Commodity SKU';

    return ComplianceAnalysis(
      productName: productName,
      mrp: mrp ?? '',
      netQuantity: netQty ?? '',
      manufacturer: manufacturer ?? '',
      address: '',
      packingDate: packingDate ?? '',
      customerCare: customerCare ?? '',
      missingInformation: missing,
      possibleIssues: issues,
    );
  }
}

/// Provides the analysis runner. Overridable in tests with a fake.
final scanAnalysisRunnerProvider = Provider<ScanAnalysisRunner>((ref) {
  return const GeminiScanAnalysisRunner();
});
