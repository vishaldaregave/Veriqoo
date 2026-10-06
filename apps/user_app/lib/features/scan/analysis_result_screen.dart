import 'dart:io';

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:share_plus/share_plus.dart';
import 'package:shared_core/services/compliance_analysis.dart';
import 'package:shared_core/services/supabase_service.dart';
import 'package:flutter_application_1/app/routes.dart';
import 'package:flutter_application_1/core/theme/pro_palette.dart';
import 'package:flutter_application_1/features/reports/detailed_report_screen.dart';
import 'package:flutter_application_1/features/scan/model/evidence_image.dart';

/// Arguments passed to [AnalysisResultScreen]
class AnalysisResultArgs {
  const AnalysisResultArgs({
    required this.analysis,
    required this.ocrText,
    this.primaryImage,
    this.imageUrl,
    this.evidence = const <EvidenceImage>[],
    this.category = 'Packaged Commodity',
  });

  final ComplianceAnalysis analysis;
  final String ocrText;
  final XFile? primaryImage;
  final String? imageUrl;
  final List<EvidenceImage> evidence;
  final String category;
}

/// Screen 5: Scan Result Overview Screen matching the design board.
///
/// Displays:
/// - Product pack hero
/// - Big Status Banner: "✓ Compliant" (or Non-Compliant)
/// - Product Card (Name, Manufacturer, Category)
/// - Compliance Score (96%) with green progress bar
/// - 3 Metric chips: "12 Verified", "0 Issues", "1 Suggestion"
/// - "View Detailed Report →" button (navigates to Screen 6)
/// - "Scan Another Product" button
/// - Automatically saves inspection report to Supabase backend!
class AnalysisResultScreen extends ConsumerStatefulWidget {
  const AnalysisResultScreen({super.key, required this.args});

  final AnalysisResultArgs args;

  @override
  ConsumerState<AnalysisResultScreen> createState() => _AnalysisResultScreenState();
}

class _AnalysisResultScreenState extends ConsumerState<AnalysisResultScreen> {
  bool _saved = false;

  @override
  void initState() {
    super.initState();
    _saveToBackend();
  }

  Future<void> _saveToBackend() async {
    if (_saved) return;
    try {
      await SupabaseService().saveInspectionReport(
        analysis: widget.args.analysis,
        ocrText: widget.args.ocrText,
        primaryImage: widget.args.primaryImage,
        imageUrl: widget.args.imageUrl,
      );
      _saved = true;
    } catch (_) {
      // Backend error handled safely without crashing UI
    }
  }

  @override
  Widget build(BuildContext context) {
    final analysis = widget.args.analysis;
    final isCompliant = analysis.isCompliant;
    final productName = analysis.productName.isNotEmpty ? analysis.productName : 'Scanned Product';
    final manufacturer = analysis.manufacturer.isNotEmpty
        ? analysis.manufacturer
        : 'Unknown Manufacturer';

    final issuesCount = analysis.possibleIssues.length;
    final missingCount = analysis.missingInformation.length;
    // Score derived from real data: start at 100, deduct per issue and missing field
    final rawScore = 100 - (issuesCount * 8) - (missingCount * 6);
    final scorePercent = rawScore.clamp(0, 100);
    // Verified = mandatory fields that ARE present (out of 6 typical fields)
    final totalFields = 6;
    final verifiedCount = (totalFields - missingCount).clamp(0, totalFields);
    final suggestionsCount = missingCount;

    return Scaffold(
      backgroundColor: ProPalette.background,
      appBar: AppBar(
        backgroundColor: ProPalette.background,
        elevation: 0,
        leading: IconButton(
          icon: const Icon(Icons.arrow_back_ios_new_rounded, color: ProPalette.textHeading, size: 20),
          onPressed: () => context.go(AppRoutes.homePath),
        ),
        actions: [
          IconButton(
            icon: const Icon(Icons.share_outlined, color: ProPalette.textHeading, size: 22),
            onPressed: () {
              SharePlus.instance.share(ShareParams(
                text: 'VERIQOO Compliance Report: $productName is ${isCompliant ? "COMPLIANT" : "FLAGGED"}.\nVerified under Legal Metrology Rules.',
              ));
            },
          ),
          IconButton(
            icon: const Icon(Icons.file_download_outlined, color: ProPalette.textHeading, size: 22),
            onPressed: () => context.push('/compliance-report', extra: widget.args),
          ),
          const SizedBox(width: 8),
        ],
      ),
      body: SafeArea(
        child: SingleChildScrollView(
          padding: const EdgeInsets.symmetric(horizontal: 20, vertical: 8),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              // 1. Product Pack Hero Photo
              Center(
                child: Container(
                  height: 190,
                  width: double.infinity,
                  alignment: Alignment.center,
                  child: widget.args.primaryImage != null
                      ? ClipRRect(
                          borderRadius: BorderRadius.circular(16),
                          child: Image.file(
                            File(widget.args.primaryImage!.path),
                            height: 180,
                            fit: BoxFit.contain,
                          ),
                        )
                      : Container(
                          height: 180,
                          width: 140,
                          decoration: BoxDecoration(
                            color: const Color(0xFFF0FDF4),
                            borderRadius: BorderRadius.circular(16),
                            boxShadow: [
                              BoxShadow(
                                color: Colors.black.withValues(alpha: 0.06),
                                blurRadius: 10,
                                offset: const Offset(0, 4),
                              ),
                            ],
                          ),
                          child: Column(
                            mainAxisAlignment: MainAxisAlignment.center,
                            children: const [
                              Icon(Icons.inventory_2_outlined, color: Color(0xFF22C55E), size: 54),
                              SizedBox(height: 8),
                              Text(
                                'Scanned',
                                style: TextStyle(
                                  color: Color(0xFF166534),
                                  fontWeight: FontWeight.w800,
                                  fontSize: 16,
                                ),
                              ),
                              Text(
                                'Product',
                                style: TextStyle(
                                  color: Color(0xFF166534),
                                  fontSize: 11,
                                ),
                              ),
                            ],
                          ),
                        ),
                ),
              ),
              const SizedBox(height: 20),

              // 2. Big Status Banner (Compliant / Flagged)
              Center(
                child: Column(
                  children: [
                    Container(
                      width: 44,
                      height: 44,
                      decoration: BoxDecoration(
                        color: isCompliant ? ProPalette.emeraldText : ProPalette.crimsonViolation,
                        shape: BoxShape.circle,
                      ),
                      child: const Icon(Icons.check, color: Colors.white, size: 26),
                    ),
                    const SizedBox(height: 10),
                    Text(
                      isCompliant ? 'Compliant' : 'Issues Detected',
                      style: TextStyle(
                        fontSize: 22,
                        fontWeight: FontWeight.w800,
                        color: isCompliant ? ProPalette.emeraldText : ProPalette.crimsonViolation,
                      ),
                    ),
                    const SizedBox(height: 4),
                    Text(
                      isCompliant
                          ? 'This product meets applicable Indian regulations.'
                          : 'Specific declarations require attention under Legal Metrology.',
                      textAlign: TextAlign.center,
                      style: const TextStyle(
                        fontSize: 13,
                        color: ProPalette.textMuted,
                      ),
                    ),
                  ],
                ),
              ),
              const SizedBox(height: 24),

              // 3. Product Info Card
              Container(
                padding: const EdgeInsets.all(14),
                decoration: ProPalette.cardDecoration(context, radius: 14),
                child: Row(
                  children: [
                    Container(
                      width: 46,
                      height: 46,
                      decoration: BoxDecoration(
                        color: const Color(0xFFFEF3C7),
                        borderRadius: BorderRadius.circular(10),
                      ),
                      child: const Icon(Icons.fastfood_outlined, color: Color(0xFFD97706), size: 24),
                    ),
                    const SizedBox(width: 14),
                    Expanded(
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Text(
                            productName,
                            style: const TextStyle(
                              fontSize: 15,
                              fontWeight: FontWeight.w700,
                              color: ProPalette.textHeading,
                            ),
                          ),
                          const SizedBox(height: 2),
                          Text(
                            '$manufacturer • Packaged Snacks',
                            style: const TextStyle(
                              fontSize: 12,
                              color: ProPalette.textMuted,
                            ),
                            maxLines: 1,
                            overflow: TextOverflow.ellipsis,
                          ),
                        ],
                      ),
                    ),
                  ],
                ),
              ),
              const SizedBox(height: 20),

              // 4. Compliance Score & Progress Bar
              Row(
                mainAxisAlignment: MainAxisAlignment.spaceBetween,
                children: [
                  const Text(
                    'Compliance Score',
                    style: TextStyle(
                      fontSize: 14,
                      fontWeight: FontWeight.w600,
                      color: ProPalette.textHeading,
                    ),
                  ),
                  Text(
                    '$scorePercent%',
                    style: const TextStyle(
                      fontSize: 14,
                      fontWeight: FontWeight.w800,
                      color: ProPalette.emeraldText,
                    ),
                  ),
                ],
              ),
              const SizedBox(height: 8),
              ClipRRect(
                borderRadius: BorderRadius.circular(10),
                child: LinearProgressIndicator(
                  value: scorePercent / 100.0,
                  backgroundColor: const Color(0xFFE5E7EB),
                  valueColor: const AlwaysStoppedAnimation<Color>(ProPalette.accentEmerald),
                  minHeight: 8,
                ),
              ),
              const SizedBox(height: 18),

              // 5. Metric Chips: Verified | Issues | Suggestion
              Row(
                children: [
                  Expanded(
                    child: _buildMetricChip(
                      icon: Icons.check_circle_outline,
                      count: verifiedCount,
                      label: 'Verified',
                      color: ProPalette.emeraldText,
                      bg: ProPalette.emeraldBg,
                    ),
                  ),
                  const SizedBox(width: 8),
                  Expanded(
                    child: _buildMetricChip(
                      icon: Icons.error_outline,
                      count: issuesCount,
                      label: 'Issues',
                      color: ProPalette.crimsonViolation,
                      bg: ProPalette.crimsonBg,
                    ),
                  ),
                  const SizedBox(width: 8),
                  Expanded(
                    child: _buildMetricChip(
                      icon: Icons.info_outline,
                      count: suggestionsCount,
                      label: 'Suggestion',
                      color: ProPalette.amberWarning,
                      bg: ProPalette.amberBg,
                    ),
                  ),
                ],
              ),
              const SizedBox(height: 28),

              // 6. Action Buttons
              // Primary "View Detailed Report ->" Button
              ElevatedButton(
                onPressed: () {
                  Navigator.of(context).push(
                    MaterialPageRoute(
                      builder: (context) => DetailedReportScreen(args: widget.args),
                    ),
                  );
                },
                style: ElevatedButton.styleFrom(
                  backgroundColor: ProPalette.primaryForest,
                  foregroundColor: Colors.white,
                  padding: const EdgeInsets.symmetric(vertical: 16),
                  shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(14)),
                  elevation: 0,
                ),
                child: const Row(
                  mainAxisAlignment: MainAxisAlignment.center,
                  children: [
                    Text(
                      'View Detailed Report',
                      style: TextStyle(
                        fontSize: 15,
                        fontWeight: FontWeight.w700,
                      ),
                    ),
                    SizedBox(width: 6),
                    Icon(Icons.arrow_forward_rounded, size: 18),
                  ],
                ),
              ),
              const SizedBox(height: 12),

              // Button 2: Official Compliance Dossier (with QR & PDF)
              OutlinedButton.icon(
                onPressed: () => context.push(AppRoutes.complianceReportPath, extra: widget.args),
                icon: const Icon(Icons.picture_as_pdf_outlined, color: ProPalette.primaryForest, size: 18),
                label: const Text(
                  'Compliance Report (PDF & QR Code)',
                  style: TextStyle(
                    fontSize: 14,
                    fontWeight: FontWeight.w700,
                    color: ProPalette.primaryForest,
                  ),
                ),
                style: OutlinedButton.styleFrom(
                  backgroundColor: const Color(0xFFF0FDF4),
                  side: const BorderSide(color: Color(0xFF86EFAC)),
                  padding: const EdgeInsets.symmetric(vertical: 15),
                  shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(14)),
                ),
              ),
              const SizedBox(height: 12),

              // Secondary "Scan Another Product" Button
              OutlinedButton.icon(
                onPressed: () => context.pushReplacement(AppRoutes.scanCapturePath),
                icon: const Icon(Icons.qr_code_scanner_rounded, size: 18),
                label: const Text(
                  'Scan Another Product',
                  style: TextStyle(
                    fontSize: 14,
                    fontWeight: FontWeight.w600,
                  ),
                ),
                style: OutlinedButton.styleFrom(
                  foregroundColor: ProPalette.textHeading,
                  backgroundColor: Colors.white,
                  side: const BorderSide(color: Color(0xFFE5E7EB)),
                  padding: const EdgeInsets.symmetric(vertical: 15),
                  shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(14)),
                ),
              ),
              const SizedBox(height: 24),
            ],
          ),
        ),
      ),
    );
  }

  Widget _buildMetricChip({
    required IconData icon,
    required int count,
    required String label,
    required Color color,
    required Color bg,
  }) {
    return Container(
      padding: const EdgeInsets.symmetric(vertical: 10, horizontal: 8),
      decoration: BoxDecoration(
        color: bg,
        borderRadius: BorderRadius.circular(12),
      ),
      child: Row(
        mainAxisAlignment: MainAxisAlignment.center,
        children: [
          Icon(icon, size: 16, color: color),
          const SizedBox(width: 5),
          Text(
            '$count $label',
            style: TextStyle(
              fontSize: 11,
              fontWeight: FontWeight.w700,
              color: color,
            ),
          ),
        ],
      ),
    );
  }
}
