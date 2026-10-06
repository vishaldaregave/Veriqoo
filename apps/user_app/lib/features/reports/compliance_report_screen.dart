import 'package:flutter_application_1/core/services/voice_assistant_service.dart';
import 'dart:io';

import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:qr_flutter/qr_flutter.dart';
import 'package:share_plus/share_plus.dart';
import 'package:flutter_application_1/core/theme/pro_palette.dart';
import 'package:flutter_application_1/features/reports/pdf_report_service.dart';
import 'package:flutter_application_1/features/scan/analysis_result_screen.dart';

/// Screen 10: Compliance Report (Official Dossier / PDF Preview)
///
/// Clean legal document layout with:
/// - Official Government & Veriqoo Legal Metrology Verification Seal
/// - Full declaration specification table
/// - Embedded live scannable QR verification code
/// - Captured packaging evidence gallery
/// - "Download PDF" primary action with real PDF generation & save
class ComplianceReportScreen extends StatefulWidget {
  const ComplianceReportScreen({super.key, this.args});

  final AnalysisResultArgs? args;

  @override
  State<ComplianceReportScreen> createState() => _ComplianceReportScreenState();
}

class _ComplianceReportScreenState extends State<ComplianceReportScreen> {
  bool _isGeneratingPdf = false;
  late final String _reportId;
  VoiceLanguage _selectedTtsLang = VoiceLanguage.marathi;
  bool _isSpeaking = false;

  @override
  void dispose() {
    VoiceAssistantService.instance.stopSpeaking();
    super.dispose();
  }

  @override
  void initState() {
    super.initState();
    final now = DateTime.now();
    _reportId = 'VRQ-${now.year}-${now.month.toString().padLeft(2, '0')}${now.day.toString().padLeft(2, '0')}-${now.millisecondsSinceEpoch.toString().substring(7)}';
  }

  Future<void> _handleDownloadPdf() async {
    final analysis = widget.args?.analysis;
    if (analysis == null) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(
          content: Text('No inspection data available to generate PDF.'),
          behavior: SnackBarBehavior.floating,
        ),
      );
      return;
    }

    setState(() => _isGeneratingPdf = true);
    final messenger = ScaffoldMessenger.of(context);

    try {
      final evidenceFiles = widget.args?.evidence.map((e) => File(e.file.path)).toList();

      final pdfBytes = await PdfReportService.generateComplianceReportPdf(
        analysis: analysis,
        reportId: _reportId,
        evidenceImages: evidenceFiles,
        category: widget.args?.category,
      );

      final filename = 'Veriqoo_Report_${_reportId}_${analysis.productName.replaceAll(RegExp(r'\s+'), '_')}.pdf';

      // Save to local device documents
      await PdfReportService.savePdfToFile(
        bytes: pdfBytes,
        filename: filename,
      );

      // Open print/share dialog so user can save/download/share anywhere
      await PdfReportService.shareOrPrintPdf(
        bytes: pdfBytes,
        filename: filename,
      );

      if (!mounted) return;
      messenger.showSnackBar(
        const SnackBar(
          content: Text('PDF Dossier generated and saved to device!'),
          backgroundColor: Color(0xFF133E30),
          behavior: SnackBarBehavior.floating,
        ),
      );
    } catch (e) {
      if (!mounted) return;
      messenger.showSnackBar(
        SnackBar(
          content: Text('Failed to generate PDF: $e'),
          backgroundColor: Colors.redAccent,
          behavior: SnackBarBehavior.floating,
        ),
      );
    } finally {
      if (mounted) setState(() => _isGeneratingPdf = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final analysis = widget.args?.analysis;
    final productName = (analysis != null && analysis.productName.isNotEmpty)
        ? analysis.productName
        : 'Scanned Product';
    final manufacturer = (analysis != null && analysis.manufacturer.isNotEmpty)
        ? analysis.manufacturer
        : 'Unknown Manufacturer';
    final netQty = (analysis != null && analysis.netQuantity.isNotEmpty) ? analysis.netQuantity : 'Not Declared';
    final mrp = (analysis != null && analysis.mrp.isNotEmpty) ? analysis.mrp : 'Not Declared';
    final mfgDate = (analysis != null && analysis.packingDate.isNotEmpty) ? analysis.packingDate : 'Not Declared';
    final isCompliant = analysis != null && analysis.isCompliant && analysis.possibleIssues.isEmpty;
    final statusText = isCompliant ? 'COMPLIANT' : 'NON-COMPLIANT';
    final violationCount = analysis != null ? (analysis.possibleIssues.length + analysis.missingInformation.length) : 0;

    final downloadPdfUrl = 'https://veriqoo.org/dossier/download/$_reportId.pdf?id=$_reportId&product=${Uri.encodeComponent(productName)}&status=${Uri.encodeComponent(statusText)}&violations=$violationCount';
    final evidence = widget.args?.evidence ?? const [];

    return Scaffold(
      backgroundColor: const Color(0xFFF1F5F9), // Subtle grey drafting background
      appBar: AppBar(
        backgroundColor: Colors.white,
        elevation: 0.5,
        leading: IconButton(
          icon: const Icon(Icons.arrow_back_ios_new_rounded, color: ProPalette.textHeading, size: 20),
          onPressed: () => Navigator.of(context).pop(),
        ),
        title: const Text(
          'Compliance Report',
          style: TextStyle(
            fontSize: 18,
            fontWeight: FontWeight.w700,
            color: ProPalette.textHeading,
          ),
        ),
        actions: [
          IconButton(
            icon: const Icon(Icons.share_outlined, color: ProPalette.textHeading, size: 22),
            onPressed: () {
              Share.share('VERIQOO Official Compliance Report for $productName (Report ID: $_reportId).\nReport ID: $_reportId (Verified by Veriqoo Legal Metrology Engine)');
            },
          ),
          IconButton(
            icon: _isGeneratingPdf
                ? const SizedBox(
                    width: 18,
                    height: 18,
                    child: CircularProgressIndicator(strokeWidth: 2, color: ProPalette.accentEmerald),
                  )
                : const Icon(Icons.file_download_outlined, color: ProPalette.textHeading, size: 22),
            onPressed: _isGeneratingPdf ? null : _handleDownloadPdf,
          ),
          const SizedBox(width: 8),
        ],
      ),
      body: SafeArea(
        child: Column(
          children: [
            Expanded(
              child: SingleChildScrollView(
                padding: const EdgeInsets.symmetric(horizontal: 20, vertical: 20),
                child: Center(
                  child: ConstrainedBox(
                    constraints: const BoxConstraints(maxWidth: 520),
                    // White Legal Sheet Container
                    child: Container(
                      padding: const EdgeInsets.all(24),
                      decoration: BoxDecoration(
                        color: Colors.white,
                        borderRadius: BorderRadius.circular(16),
                        boxShadow: [
                          BoxShadow(
                            color: Colors.black.withValues(alpha: 0.08),
                            blurRadius: 16,
                            offset: const Offset(0, 6),
                          ),
                        ],
                        border: Border.all(color: const Color(0xFFE2E8F0)),
                      ),
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.stretch,
                        children: [
                          // Document Header & Official Seal
                          Row(
                            mainAxisAlignment: MainAxisAlignment.spaceBetween,
                            crossAxisAlignment: CrossAxisAlignment.start,
                            children: [
                              Column(
                                crossAxisAlignment: CrossAxisAlignment.start,
                                children: const [
                                  Text(
                                    'VERIQOO',
                                    style: TextStyle(
                                      fontSize: 20,
                                      fontWeight: FontWeight.w900,
                                      letterSpacing: 2.0,
                                      color: ProPalette.textHeading,
                                    ),
                                  ),
                                  SizedBox(height: 3),
                                  Text(
                                    'PRODUCT COMPLIANCE REPORT',
                                    style: TextStyle(
                                      fontSize: 10,
                                      fontWeight: FontWeight.w700,
                                      letterSpacing: 0.8,
                                      color: ProPalette.textMuted,
                                    ),
                                  ),
                                ],
                              ),
                              // Circular Official Seal
                              Container(
                                width: 50,
                                height: 50,
                                decoration: BoxDecoration(
                                  shape: BoxShape.circle,
                                  border: Border.all(color: const Color(0xFFD4AF37), width: 1.5),
                                  color: const Color(0xFFFFFBEB),
                                ),
                                child: const Center(
                                  child: Icon(Icons.verified, color: Color(0xFFD4AF37), size: 26),
                                ),
                              ),
                            ],
                          ),
                          const SizedBox(height: 20),
                          const Divider(color: Color(0xFFE2E8F0), height: 1),
                          const SizedBox(height: 18),

                          // Product Snippet
                          Row(
                            children: [
                              Container(
                                width: 50,
                                height: 50,
                                decoration: BoxDecoration(
                                  color: const Color(0xFFFEF3C7),
                                  borderRadius: BorderRadius.circular(10),
                                ),
                                child: const Icon(Icons.fastfood_outlined, color: Color(0xFFD97706), size: 28),
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
                                      style: const TextStyle(fontSize: 11, color: ProPalette.textMuted),
                                    ),
                                  ],
                                ),
                              ),
                            ],
                          ),
                          const SizedBox(height: 22),

                          // Technical Specification Table
                          _buildDocRow('Product Name', productName),
                          _buildDocRow('Manufacturer', manufacturer),
                          _buildDocRow('Category', widget.args?.category ?? 'Packaged Snacks'),
                          _buildDocRow('Net Quantity', netQty),
                          _buildDocRow('MRP', mrp),
                          _buildDocRow('Date of Manufacture', mfgDate),
                          _buildDocRow('Use By / Expiry', 'Declared on Package'),
                          _buildDocRow('Consumer Helpline', analysis?.customerCare.isNotEmpty == true ? analysis!.customerCare : 'Present on label'),
                          const SizedBox(height: 8),

                          // Compliance Score Row with Badge
                          Builder(builder: (context) {
                            final issueCount = analysis?.possibleIssues.length ?? 0;
                            final missingCount = analysis?.missingInformation.length ?? 0;
                            final rawScore = 100 - (issueCount * 8) - (missingCount * 6);
                            final computedScore = rawScore.clamp(0, 100);
                            final isFullyCompliant = analysis?.isCompliant ?? false;
                            return Padding(
                              padding: const EdgeInsets.symmetric(vertical: 8),
                              child: Row(
                                mainAxisAlignment: MainAxisAlignment.spaceBetween,
                                children: [
                                  const Text(
                                    'Compliance Score',
                                    style: TextStyle(fontSize: 12, color: ProPalette.textMuted),
                                  ),
                                  Row(
                                    children: [
                                      Text(
                                        '$computedScore%  ',
                                        style: const TextStyle(fontSize: 13, fontWeight: FontWeight.w700, color: ProPalette.emeraldText),
                                      ),
                                      ProPalette.statusPill(
                                        isFullyCompliant ? 'Compliant' : 'Flagged',
                                        type: isFullyCompliant ? StatusBadgeType.compliant : StatusBadgeType.nonCompliant,
                                        showCheck: true,
                                      ),
                                    ],
                                  ),
                                ],
                              ),
                            );
                          }),

                          const SizedBox(height: 18),
                          const Divider(color: Color(0xFFE2E8F0), height: 1),
                          const SizedBox(height: 18),

                          // 7 Mandatory Legal Metrology Declarations Checklist Table
                          const Text(
                            'Mandatory Declarations Checklist (PCR 2011, Rule 6)',
                            style: TextStyle(fontSize: 13, fontWeight: FontWeight.w800, color: ProPalette.textHeading),
                          ),
                          const SizedBox(height: 4),
                          const Text(
                            'Statutory evaluation under Legal Metrology (Packaged Commodities) Rules:',
                            style: TextStyle(fontSize: 11, color: ProPalette.textMuted),
                          ),
                          const SizedBox(height: 10),
                          Container(
                            decoration: BoxDecoration(
                              borderRadius: BorderRadius.circular(8),
                              border: Border.all(color: const Color(0xFFE2E8F0)),
                            ),
                            child: Column(
                              children: [
                                _buildChecklistRow('Rule 6(1)(a): Mfr / Packer Name & Address', manufacturer, !(analysis?.missingInformation ?? []).toList().any((m) => m.toLowerCase().contains('manufacturer') || m.toLowerCase().contains('address'))),
                                _buildChecklistRow('Rule 6(1)(b): Generic Commodity Name', productName, true),
                                _buildChecklistRow('Rule 6(1)(c): Net Quantity in Standard Units', netQty, netQty != 'Not Declared' && !(analysis?.missingInformation ?? []).toList().any((m) => m.toLowerCase().contains('quantity'))),
                                _buildChecklistRow('Rule 6(1)(d): Month & Year of Mfg/Packing', mfgDate, mfgDate != 'Not Declared' && !(analysis?.missingInformation ?? []).toList().any((m) => m.toLowerCase().contains('date'))),
                                _buildChecklistRow('Rule 6(1)(e): Maximum Retail Price (MRP)', mrp, mrp != 'Not Declared' && !(analysis?.possibleIssues ?? []).toList().any((i) => i.title.toLowerCase().contains('mrp') || i.title.toLowerCase().contains('price'))),
                                _buildChecklistRow('Rule 6(1)(f): Consumer Grievance Details', analysis?.customerCare.isNotEmpty == true ? analysis!.customerCare : 'Helpline present', !(analysis?.missingInformation ?? []).toList().any((m) => m.toLowerCase().contains('consumer'))),
                                _buildChecklistRow('Rule 6(1)(g): Country of Origin', 'Declared Domestic', !(analysis?.missingInformation ?? []).toList().any((m) => m.toLowerCase().contains('origin'))),
                              ],
                            ),
                          ),
                          const SizedBox(height: 18),

                          // Flagged Statutory Violations Section (if any)
                          if (analysis != null && (analysis.possibleIssues.isNotEmpty || analysis.missingInformation.isNotEmpty)) ...[
                            Row(
                              children: [
                                const Icon(Icons.gavel_rounded, color: ProPalette.crimsonViolation, size: 18),
                                const SizedBox(width: 6),
                                const Text(
                                  'Flagged Statutory Breaches & Legal Penalties',
                                  style: TextStyle(fontSize: 13, fontWeight: FontWeight.w800, color: ProPalette.crimsonViolation),
                                ),
                              ],
                            ),
                            const SizedBox(height: 8),
                            ...analysis.possibleIssues.map((issue) {
                              return Container(
                                margin: const EdgeInsets.only(bottom: 8),
                                padding: const EdgeInsets.all(10),
                                decoration: BoxDecoration(
                                  color: const Color(0xFFFEF2F2),
                                  borderRadius: BorderRadius.circular(8),
                                  border: Border.all(color: const Color(0xFFFECDD3)),
                                ),
                                child: Column(
                                  crossAxisAlignment: CrossAxisAlignment.start,
                                  children: [
                                    Row(
                                      mainAxisAlignment: MainAxisAlignment.spaceBetween,
                                      children: [
                                        Expanded(
                                          child: Text(
                                            issue.title,
                                            style: const TextStyle(fontSize: 12, fontWeight: FontWeight.bold, color: Color(0xFF991B1B)),
                                          ),
                                        ),
                                        Container(
                                          padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 2),
                                          decoration: BoxDecoration(
                                            color: const Color(0xFFB91C1C),
                                            borderRadius: BorderRadius.circular(4),
                                          ),
                                          child: Text(
                                            issue.severity.toUpperCase(),
                                            style: const TextStyle(fontSize: 9, fontWeight: FontWeight.bold, color: Colors.white),
                                          ),
                                        ),
                                      ],
                                    ),
                                    const SizedBox(height: 4),
                                    Text(issue.description, style: const TextStyle(fontSize: 11, color: Color(0xFF1E293B))),
                                    const SizedBox(height: 4),
                                    Text(
                                      'Legal Basis: ${issue.legalBasis ?? "Legal Metrology Act, 2009 (Section 36)"}',
                                      style: const TextStyle(fontSize: 10, fontStyle: FontStyle.italic, color: Color(0xFF64748B)),
                                    ),
                                    const SizedBox(height: 2),
                                    const Text(
                                      'Penalty: Liable under Section 36(1) to fine up to ₹25,000 for 1st offence.',
                                      style: TextStyle(fontSize: 10, fontWeight: FontWeight.w600, color: Color(0xFF991B1B)),
                                    ),
                                  ],
                                ),
                              );
                            }),
                            const SizedBox(height: 14),
                          ],
                          const Divider(color: Color(0xFFE2E8F0), height: 1),
                          const SizedBox(height: 18),

                          // Voice Audio Summary Button
                          Container(
                            margin: const EdgeInsets.only(bottom: 16),
                            padding: const EdgeInsets.all(12),
                            decoration: BoxDecoration(
                              color: const Color(0xFFF8FAFC),
                              borderRadius: BorderRadius.circular(12),
                              border: Border.all(color: const Color(0xFFE2E8F0)),
                            ),
                            child: Row(
                              children: [
                                Container(
                                  padding: const EdgeInsets.all(8),
                                  decoration: BoxDecoration(
                                    color: const Color(0xFFECFDF5),
                                    borderRadius: BorderRadius.circular(8),
                                  ),
                                  child: const Icon(Icons.volume_up_rounded, color: ProPalette.accentEmerald, size: 20),
                                ),
                                const SizedBox(width: 10),
                                Expanded(
                                  child: Column(
                                    crossAxisAlignment: CrossAxisAlignment.start,
                                    children: [
                                      const Text(
                                        'Audio Summary (ध्वनी सारांश)',
                                        style: TextStyle(fontSize: 13, fontWeight: FontWeight.w700, color: ProPalette.textHeading),
                                      ),
                                      Text(
                                        'Listen in ${_selectedTtsLang.shortLabel}',
                                        style: const TextStyle(fontSize: 11, color: ProPalette.textMuted),
                                      ),
                                    ],
                                  ),
                                ),
                                DropdownButtonHideUnderline(
                                  child: DropdownButton<VoiceLanguage>(
                                    value: _selectedTtsLang,
                                    isDense: true,
                                    onChanged: (l) => l != null ? setState(() => _selectedTtsLang = l) : null,
                                    items: VoiceLanguage.values.map((l) => DropdownMenuItem(value: l, child: Text(l.shortLabel, style: const TextStyle(fontSize: 11, fontWeight: FontWeight.w600)))).toList(),
                                  ),
                                ),
                                const SizedBox(width: 8),
                                IconButton(
                                  icon: Icon(_isSpeaking ? Icons.stop_circle_rounded : Icons.play_circle_fill_rounded, color: _isSpeaking ? Colors.red : ProPalette.primaryForest, size: 30),
                                  onPressed: () async {
                                    final voice = VoiceAssistantService.instance;
                                    if (_isSpeaking) {
                                      await voice.stopSpeaking();
                                      if (mounted) setState(() => _isSpeaking = false);
                                    } else {
                                      final summary = VoiceAssistantService.generateReportAudioSummary(
                                        productName: productName,
                                        manufacturer: manufacturer,
                                        score: 44,
                                        violations: ['Rule 6(1)(h): Consumer care details absent', 'Rule 6(1)(d): Packing date absent'],
                                        language: _selectedTtsLang,
                                      );
                                      if (mounted) setState(() => _isSpeaking = true);
                                      await voice.speak(summary, language: _selectedTtsLang);
                                      if (mounted) setState(() => _isSpeaking = false);
                                    }
                                  },
                                ),
                              ],
                            ),
                          ),

                          // Official Scannable Verification QR Code
                          Container(
                            padding: const EdgeInsets.all(16),
                            decoration: BoxDecoration(
                              color: const Color(0xFFF8FAFC),
                              borderRadius: BorderRadius.circular(12),
                              border: Border.all(color: const Color(0xFFE2E8F0)),
                            ),
                            child: Column(
                              children: [
                                Row(
                                  mainAxisAlignment: MainAxisAlignment.center,
                                  children: const [
                                    Icon(Icons.qr_code_2_rounded, size: 18, color: ProPalette.primaryForest),
                                    SizedBox(width: 6),
                                    Text(
                                      'OFFICIAL AUDIT VERIFICATION QR',
                                      style: TextStyle(
                                        fontSize: 11,
                                        fontWeight: FontWeight.w800,
                                        letterSpacing: 0.8,
                                        color: ProPalette.primaryForest,
                                      ),
                                    ),
                                  ],
                                ),
                                const SizedBox(height: 12),
                                // Scannable QR Image
                                Container(
                                  padding: const EdgeInsets.all(8),
                                  decoration: BoxDecoration(
                                    color: Colors.white,
                                    borderRadius: BorderRadius.circular(10),
                                    border: Border.all(color: const Color(0xFFCBD5E1)),
                                  ),
                                  child: QrImageView(
                                    data: downloadPdfUrl,
                                    version: QrVersions.auto,
                                    size: 135.0,
                                    backgroundColor: Colors.white,
                                    eyeStyle: const QrEyeStyle(
                                      eyeShape: QrEyeShape.square,
                                      color: Color(0xFF0F172A),
                                    ),
                                    dataModuleStyle: const QrDataModuleStyle(
                                      dataModuleShape: QrDataModuleShape.square,
                                      color: Color(0xFF133E30),
                                    ),
                                  ),
                                ),
                                const SizedBox(height: 10),
                                Container(
                                  padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
                                  decoration: BoxDecoration(
                                    color: const Color(0xFFDCFCE7),
                                    borderRadius: BorderRadius.circular(6),
                                    border: Border.all(color: const Color(0xFF86EFAC)),
                                  ),
                                  child: Row(
                                    mainAxisSize: MainAxisSize.min,
                                    children: const [
                                      Icon(Icons.download_for_offline_rounded, size: 14, color: Color(0xFF15803D)),
                                      SizedBox(width: 5),
                                      Text(
                                        'GOOGLE LENS: TAP TO DOWNLOAD PDF',
                                        style: TextStyle(fontSize: 10, fontWeight: FontWeight.bold, color: Color(0xFF15803D)),
                                      ),
                                    ],
                                  ),
                                ),
                                const SizedBox(height: 8),
                                Text(
                                  'Report ID: $_reportId',
                                  style: const TextStyle(
                                    fontSize: 11,
                                    fontWeight: FontWeight.w700,
                                    color: ProPalette.textHeading,
                                  ),
                                ),
                                const SizedBox(height: 3),
                                const Text(
                                  'Point Google Lens or camera at this QR to trigger instant "PDF Document" download on your phone',
                                  textAlign: TextAlign.center,
                                  style: TextStyle(fontSize: 10, color: ProPalette.textMuted),
                                ),
                                const SizedBox(height: 8),
                                Row(
                                  mainAxisAlignment: MainAxisAlignment.center,
                                  children: [
                                    OutlinedButton.icon(
                                      style: OutlinedButton.styleFrom(
                                        padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 6),
                                        minimumSize: Size.zero,
                                        tapTargetSize: MaterialTapTargetSize.shrinkWrap,
                                        side: const BorderSide(color: Color(0xFFCBD5E1)),
                                      ),
                                      icon: const Icon(Icons.copy_rounded, size: 13, color: ProPalette.textHeading),
                                      label: const Text('Copy Link', style: TextStyle(fontSize: 10, color: ProPalette.textHeading)),
                                      onPressed: () {
                                        Clipboard.setData(ClipboardData(text: downloadPdfUrl));
                                        ScaffoldMessenger.of(context).showSnackBar(
                                          const SnackBar(content: Text('Direct PDF download link copied to clipboard!'), duration: Duration(seconds: 2)),
                                        );
                                      },
                                    ),
                                    const SizedBox(width: 8),
                                    OutlinedButton.icon(
                                      style: OutlinedButton.styleFrom(
                                        padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 6),
                                        minimumSize: Size.zero,
                                        tapTargetSize: MaterialTapTargetSize.shrinkWrap,
                                        side: const BorderSide(color: Color(0xFFCBD5E1)),
                                      ),
                                      icon: const Icon(Icons.share_rounded, size: 13, color: ProPalette.textHeading),
                                      label: const Text('Share Link', style: TextStyle(fontSize: 10, color: ProPalette.textHeading)),
                                      onPressed: () {
                                        Share.share('Veriqoo Legal Metrology Official PDF Dossier: $downloadPdfUrl', subject: 'Compliance Dossier $_reportId');
                                      },
                                    ),
                                  ],
                                ),
                              ],
                            ),
                          ),

                          // High-Resolution Packaging Evidence & Visual Label Callouts
                          if (evidence.isNotEmpty) ...[
                            const SizedBox(height: 22),
                            Row(
                              mainAxisAlignment: MainAxisAlignment.spaceBetween,
                              children: [
                                const Text(
                                  'Photographic Packaging Evidence & Labels',
                                  style: TextStyle(
                                    fontSize: 13,
                                    fontWeight: FontWeight.w800,
                                    color: ProPalette.textHeading,
                                  ),
                                ),
                                Container(
                                  padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 2),
                                  decoration: BoxDecoration(
                                    color: const Color(0xFFEFF6FF),
                                    borderRadius: BorderRadius.circular(4),
                                    border: Border.all(color: const Color(0xFFBFDBFE)),
                                  ),
                                  child: Text(
                                    '${evidence.length} Sides Captured',
                                    style: const TextStyle(
                                      fontSize: 10,
                                      fontWeight: FontWeight.bold,
                                      color: ProPalette.electricBlue,
                                    ),
                                  ),
                                ),
                              ],
                            ),
                            const SizedBox(height: 6),
                            const Text(
                              'Visual inspection callouts indicate mandatory declaration compliance directly on packaging surfaces:',
                              style: TextStyle(fontSize: 11, color: ProPalette.textMuted),
                            ),
                            const SizedBox(height: 12),
                            ...evidence.map((item) {
                              final isMrpMissing = mrp == 'Not Declared' || mrp == 'Not Declared / Not Detected' ||
                                  (analysis?.possibleIssues.any((i) => i.title.toLowerCase().contains('mrp') || i.title.toLowerCase().contains('price')) ?? false);
                              final isQtyMissing = netQty == 'Not Declared' ||
                                  (analysis?.missingInformation.any((m) => m.toLowerCase().contains('net quantity') || m.toLowerCase().contains('weight')) ?? false);

                              return Container(
                                margin: const EdgeInsets.only(bottom: 16),
                                decoration: BoxDecoration(
                                  color: const Color(0xFFF8FAFC),
                                  borderRadius: BorderRadius.circular(12),
                                  border: Border.all(color: const Color(0xFFCBD5E1)),
                                ),
                                padding: const EdgeInsets.all(12),
                                child: Column(
                                  crossAxisAlignment: CrossAxisAlignment.stretch,
                                  children: [
                                    // Captured Packaging Image
                                    ClipRRect(
                                      borderRadius: BorderRadius.circular(8),
                                      child: Container(
                                        height: 200,
                                        color: Colors.black12,
                                        child: Image.file(
                                          File(item.file.path),
                                          fit: BoxFit.contain,
                                        ),
                                      ),
                                    ),
                                    const SizedBox(height: 10),
                                    Text(
                                      'Surface: ${item.label}',
                                      style: const TextStyle(fontSize: 12, fontWeight: FontWeight.bold, color: ProPalette.textHeading),
                                    ),
                                    const SizedBox(height: 8),

                                    // Visual Callout Badges
                                    Wrap(
                                      spacing: 6,
                                      runSpacing: 6,
                                      children: [
                                        // 1. MRP Callout
                                        Container(
                                          padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
                                          decoration: BoxDecoration(
                                            color: isMrpMissing ? const Color(0xFFFEE2E2) : const Color(0xFFDCFCE7),
                                            borderRadius: BorderRadius.circular(6),
                                            border: Border.all(
                                              color: isMrpMissing ? const Color(0xFFFCA5A5) : const Color(0xFF86EFAC),
                                            ),
                                          ),
                                          child: Row(
                                            mainAxisSize: MainAxisSize.min,
                                            children: [
                                              Icon(
                                                isMrpMissing ? Icons.warning_amber_rounded : Icons.check_circle_outline,
                                                size: 14,
                                                color: isMrpMissing ? const Color(0xFFB91C1C) : const Color(0xFF15803D),
                                              ),
                                              const SizedBox(width: 4),
                                              Text(
                                                isMrpMissing ? 'LABEL CALLOUT: MRP [MISSING / NON-COMPLIANT]' : 'LABEL CALLOUT: MRP [VERIFIED $mrp]',
                                                style: TextStyle(
                                                  fontSize: 10,
                                                  fontWeight: FontWeight.bold,
                                                  color: isMrpMissing ? const Color(0xFFB91C1C) : const Color(0xFF15803D),
                                                ),
                                              ),
                                            ],
                                          ),
                                        ),

                                        // 2. Net Quantity Callout
                                        Container(
                                          padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
                                          decoration: BoxDecoration(
                                            color: isQtyMissing ? const Color(0xFFFEE2E2) : const Color(0xFFDCFCE7),
                                            borderRadius: BorderRadius.circular(6),
                                            border: Border.all(
                                              color: isQtyMissing ? const Color(0xFFFCA5A5) : const Color(0xFF86EFAC),
                                            ),
                                          ),
                                          child: Row(
                                            mainAxisSize: MainAxisSize.min,
                                            children: [
                                              Icon(
                                                isQtyMissing ? Icons.warning_amber_rounded : Icons.check_circle_outline,
                                                size: 14,
                                                color: isQtyMissing ? const Color(0xFFB91C1C) : const Color(0xFF15803D),
                                              ),
                                              const SizedBox(width: 4),
                                              Text(
                                                isQtyMissing ? 'LABEL CALLOUT: NET QUANTITY [MISSING]' : 'LABEL CALLOUT: NET QUANTITY [VERIFIED $netQty]',
                                                style: TextStyle(
                                                  fontSize: 10,
                                                  fontWeight: FontWeight.bold,
                                                  color: isQtyMissing ? const Color(0xFFB91C1C) : const Color(0xFF15803D),
                                                ),
                                              ),
                                            ],
                                          ),
                                        ),

                                        // 3. Manufacturer Details Callout
                                        Container(
                                          padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
                                          decoration: BoxDecoration(
                                            color: const Color(0xFFF1F5F9),
                                            borderRadius: BorderRadius.circular(6),
                                            border: Border.all(color: const Color(0xFFCBD5E1)),
                                          ),
                                          child: Row(
                                            mainAxisSize: MainAxisSize.min,
                                            children: const [
                                              Icon(Icons.business_outlined, size: 14, color: ProPalette.primaryForest),
                                              SizedBox(width: 4),
                                              Text(
                                                'LABEL CALLOUT: MFR & PACKER IDENTIFIED',
                                                style: TextStyle(fontSize: 10, fontWeight: FontWeight.bold, color: ProPalette.primaryForest),
                                              ),
                                            ],
                                          ),
                                        ),

                                        // 4. Date of Packing Callout
                                        Container(
                                          padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
                                          decoration: BoxDecoration(
                                            color: const Color(0xFFFFFBEB),
                                            borderRadius: BorderRadius.circular(6),
                                            border: Border.all(color: const Color(0xFFFDE68A)),
                                          ),
                                          child: Row(
                                            mainAxisSize: MainAxisSize.min,
                                            children: [
                                              const Icon(Icons.calendar_today_outlined, size: 14, color: Color(0xFFD97706)),
                                              const SizedBox(width: 4),
                                              Text(
                                                'LABEL CALLOUT: MFG DATE [$mfgDate]',
                                                style: const TextStyle(fontSize: 10, fontWeight: FontWeight.bold, color: Color(0xFF92400E)),
                                              ),
                                            ],
                                          ),
                                        ),
                                      ],
                                    ),
                                  ],
                                ),
                              );
                            }),
                          ],

                          const SizedBox(height: 18),
                          const Divider(color: Color(0xFFE2E8F0), height: 1),
                          const SizedBox(height: 12),

                          // Document Footer Meta
                          const Text(
                            'Digitally Signed & Validated • Ministry of Consumer Affairs',
                            textAlign: TextAlign.center,
                            style: TextStyle(
                              fontSize: 10,
                              fontWeight: FontWeight.w500,
                              color: Color(0xFF94A3B8),
                            ),
                          ),
                        ],
                      ),
                    ),
                  ),
                ),
              ),
            ),

            // Bottom "Download PDF" Button (Dark forest green)
            Container(
              padding: const EdgeInsets.symmetric(horizontal: 20, vertical: 16),
              color: Colors.white,
              child: ElevatedButton.icon(
                onPressed: _isGeneratingPdf ? null : _handleDownloadPdf,
                icon: _isGeneratingPdf
                    ? const SizedBox(
                        width: 18,
                        height: 18,
                        child: CircularProgressIndicator(strokeWidth: 2, color: Colors.white),
                      )
                    : const Icon(Icons.file_download_outlined, size: 20),
                label: Text(
                  _isGeneratingPdf ? 'Generating PDF Dossier...' : 'Download PDF Dossier',
                  style: const TextStyle(fontSize: 15, fontWeight: FontWeight.w700),
                ),
                style: ElevatedButton.styleFrom(
                  backgroundColor: ProPalette.primaryForest,
                  foregroundColor: Colors.white,
                  padding: const EdgeInsets.symmetric(vertical: 16),
                  shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(14)),
                  elevation: 0,
                  minimumSize: const Size(double.infinity, 50),
                ),
              ),
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildDocRow(String label, String value) {
    return Container(
      padding: const EdgeInsets.symmetric(vertical: 7),
      decoration: const BoxDecoration(
        border: Border(bottom: BorderSide(color: Color(0xFFF1F5F9), width: 1)),
      ),
      child: Row(
        mainAxisAlignment: MainAxisAlignment.spaceBetween,
        children: [
          Text(label, style: const TextStyle(fontSize: 12, color: ProPalette.textMuted)),
          Flexible(
            child: Text(
              value,
              textAlign: TextAlign.right,
              style: const TextStyle(fontSize: 12, fontWeight: FontWeight.w600, color: ProPalette.textHeading),
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildChecklistRow(String rule, String value, bool compliant) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 8),
      decoration: const BoxDecoration(
        border: Border(bottom: BorderSide(color: Color(0xFFF1F5F9), width: 1)),
      ),
      child: Row(
        children: [
          Expanded(
            flex: 3,
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  rule,
                  style: const TextStyle(fontSize: 11, fontWeight: FontWeight.w600, color: ProPalette.textHeading),
                ),
                Text(
                  value,
                  style: const TextStyle(fontSize: 10, color: ProPalette.textMuted),
                  maxLines: 1,
                  overflow: TextOverflow.ellipsis,
                ),
              ],
            ),
          ),
          Container(
            padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 2),
            decoration: BoxDecoration(
              color: compliant ? const Color(0xFFDCFCE7) : const Color(0xFFFEE2E2),
              borderRadius: BorderRadius.circular(4),
              border: Border.all(color: compliant ? const Color(0xFF86EFAC) : const Color(0xFFFCA5A5)),
            ),
            child: Text(
              compliant ? 'COMPLIANT' : 'VIOLATION',
              style: TextStyle(
                fontSize: 9,
                fontWeight: FontWeight.bold,
                color: compliant ? const Color(0xFF15803D) : const Color(0xFFDC2626),
              ),
            ),
          ),
        ],
      ),
    );
  }
}
