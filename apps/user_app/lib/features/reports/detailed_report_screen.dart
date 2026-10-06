import 'dart:io';

import 'package:flutter/material.dart';
import 'package:share_plus/share_plus.dart';
import 'package:flutter_application_1/core/theme/pro_palette.dart';
import 'package:flutter_application_1/core/services/voice_assistant_service.dart';
import 'package:flutter_application_1/features/reports/compliance_report_screen.dart';
import 'package:flutter_application_1/features/scan/analysis_result_screen.dart';

/// Screen 6, 7, 8: Detailed Report Screen.
///
/// Features a 4-tab bar:
/// - Overview (Screen 6): Mini product card, Compliance Summary %, 7 Rule checklist tiles, Overall Conclusion card
/// - Evidence (Screen 7): Segmented control, package photo with interactive bounding boxes & callout badges, Extracted Information table
/// - Regulations (Screen 8): Act cards (Legal Metrology, FSSAI) and Relevant Clauses (Clause 6, 7, 10, 11)
/// - Details: Complete technical label specifications table
class DetailedReportScreen extends StatefulWidget {
  const DetailedReportScreen({super.key, required this.args});

  final AnalysisResultArgs args;

  @override
  State<DetailedReportScreen> createState() => _DetailedReportScreenState();
}

class _DetailedReportScreenState extends State<DetailedReportScreen>
    with SingleTickerProviderStateMixin {
  late final TabController _tabController;
  String _evidenceMode = 'Detected Text';
  VoiceLanguage _selectedTtsLang = VoiceLanguage.marathi;
  bool _isSpeaking = false;

  Future<void> _toggleTtsSummary({
    required String productName,
    required String manufacturer,
    required int score,
    required List<String> violations,
  }) async {
    final voiceService = VoiceAssistantService.instance;
    if (_isSpeaking) {
      await voiceService.stopSpeaking();
      if (mounted) setState(() => _isSpeaking = false);
    } else {
      final summary = VoiceAssistantService.generateReportAudioSummary(
        productName: productName,
        manufacturer: manufacturer,
        score: score,
        violations: violations,
        language: _selectedTtsLang,
      );
      if (mounted) setState(() => _isSpeaking = true);
      await voiceService.speak(summary, language: _selectedTtsLang);
      if (mounted) setState(() => _isSpeaking = false);
    }
  }

  @override
  void initState() {
    super.initState();
    _tabController = TabController(length: 4, vsync: this);
  }

  @override
  void dispose() {
    _tabController.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final analysis = widget.args.analysis;
    final productName = analysis.productName.isNotEmpty ? analysis.productName : "Unknown Product";

    return Scaffold(
      backgroundColor: ProPalette.background,
      appBar: AppBar(
        backgroundColor: Colors.white,
        elevation: 0.5,
        leading: IconButton(
          icon: const Icon(Icons.arrow_back_ios_new_rounded, color: ProPalette.textHeading, size: 20),
          onPressed: () => Navigator.of(context).pop(),
        ),
        title: const Text(
          'Detailed Report',
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
              SharePlus.instance.share(ShareParams(
                text: 'VERIQOO Detailed Report for $productName (Legal Metrology Compliance).',
              ));
            },
          ),
          IconButton(
            icon: const Icon(Icons.file_download_outlined, color: ProPalette.textHeading, size: 22),
            tooltip: 'Download Official PDF Report',
            onPressed: () {
              Navigator.of(context).push(
                MaterialPageRoute(
                  builder: (context) => ComplianceReportScreen(args: widget.args),
                ),
              );
            },
          ),
          const SizedBox(width: 8),
        ],
        bottom: TabBar(
          controller: _tabController,
          labelColor: ProPalette.primaryForest,
          unselectedLabelColor: ProPalette.textMuted,
          indicatorColor: ProPalette.primaryForest,
          indicatorWeight: 2.5,
          labelStyle: const TextStyle(fontWeight: FontWeight.w700, fontSize: 13),
          unselectedLabelStyle: const TextStyle(fontWeight: FontWeight.w500, fontSize: 13),
          tabs: const [
            Tab(text: 'Overview'),
            Tab(text: 'Details'),
            Tab(text: 'Regulations'),
            Tab(text: 'Evidence'),
          ],
        ),
      ),
      body: TabBarView(
        controller: _tabController,
        children: [
          _buildOverviewTab(context),
          _buildDetailsTab(context),
          _buildRegulationsTab(context),
          _buildEvidenceTab(context),
        ],
      ),
    );
  }

  // =========================================================================
  // SCREEN 6: OVERVIEW TAB
  // =========================================================================
  Widget _buildOverviewTab(BuildContext context) {
    final analysis = widget.args.analysis;
    final productName = analysis.productName.isNotEmpty ? analysis.productName : "Unknown Product";
    final manufacturer = analysis.manufacturer.isNotEmpty ? analysis.manufacturer : "Unknown Manufacturer";

    // Build the consolidated list of violated / non-compliant rules
    final List<Map<String, String>> violations = [];
    final seenRules = <String>{};

    // 1. From possibleIssues:
    for (final issue in analysis.possibleIssues) {
      final ruleNumber = issue.ruleNumbers.isNotEmpty
          ? issue.ruleNumbers.join(', ')
          : _inferRuleNumber(issue.title);
      final ruleTitle = issue.ruleTitles.isNotEmpty ? issue.ruleTitles.first : issue.title;
      seenRules.add(ruleNumber.toLowerCase());
      seenRules.add(ruleTitle.toLowerCase());
      violations.add({
        'rule': ruleNumber,
        'title': ruleTitle,
        'reason': issue.description.isNotEmpty ? issue.description : 'Mandatory rule requirement not met on packaging.',
        'severity': issue.severity.toUpperCase(),
        'legalBasis': issue.legalBasis ?? 'Legal Metrology (Packaged Commodities) Rules, 2011',
      });
    }

    // 2. From missingInformation:
    for (final missingItem in analysis.missingInformation) {
      final trimmed = missingItem.trim();
      final inferredRule = _inferRuleNumber(trimmed);
      final inferredTitle = _inferRuleTitle(trimmed);
      if (!seenRules.contains(inferredRule.toLowerCase()) && !seenRules.contains(inferredTitle.toLowerCase())) {
        seenRules.add(inferredRule.toLowerCase());
        seenRules.add(inferredTitle.toLowerCase());
        violations.add({
          'rule': inferredRule,
          'title': inferredTitle,
          'reason': 'Mandatory declaration "$trimmed" is missing or unreadable on package.',
          'severity': 'HIGH',
          'legalBasis': 'Mandatory under Legal Metrology (Packaged Commodities) Rules, 2011',
        });
      }
    }

    final violationCount = violations.length;
    // Deduce compliance score on basis of violations detected
    final int computedScore = (100 - (violationCount * 14)).clamp(0, 100);
    final scoreRatio = computedScore / 100.0;
    final isCompliant = violationCount == 0 && computedScore >= 90;

    final Color scoreColor = computedScore >= 80
        ? const Color(0xFF059669) // Emerald
        : (computedScore >= 50 ? const Color(0xFFD97706) : const Color(0xFFDC2626)); // Amber / Crimson

    final conclusionBg = isCompliant ? const Color(0xFFF0FDF4) : const Color(0xFFFEF2F2);
    final conclusionBorder = isCompliant ? const Color(0xFFBBF7D0) : const Color(0xFFFECACA);
    final conclusionTextCol = isCompliant ? const Color(0xFF166534) : const Color(0xFF991B1B);
    final conclusionTitleCol = isCompliant ? const Color(0xFF14532D) : const Color(0xFF7F1D1D);

    return SingleChildScrollView(
      padding: const EdgeInsets.all(20),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          // 1. Mini Product Card
          Container(
            padding: const EdgeInsets.all(12),
            decoration: ProPalette.cardDecoration(context, radius: 14),
            child: Row(
              children: [
                Container(
                  width: 44,
                  height: 44,
                  decoration: BoxDecoration(
                    color: const Color(0xFFFEF3C7),
                    borderRadius: BorderRadius.circular(10),
                  ),
                  child: const Icon(Icons.inventory_2_outlined, color: Color(0xFFD97706), size: 24),
                ),
                const SizedBox(width: 12),
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(
                        productName,
                        style: const TextStyle(fontSize: 14, fontWeight: FontWeight.w700, color: ProPalette.textHeading),
                      ),
                      const SizedBox(height: 2),
                      Text(
                        manufacturer,
                        style: const TextStyle(fontSize: 11, color: ProPalette.textMuted),
                      ),
                    ],
                  ),
                ),
              ],
            ),
          ),
          const SizedBox(height: 16),

          // 2. Compliance Score Card (Dynamically deduced with color feedback)
          Container(
            padding: const EdgeInsets.all(16),
            decoration: ProPalette.cardDecoration(context, radius: 14),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.stretch,
              children: [
                Row(
                  mainAxisAlignment: MainAxisAlignment.spaceBetween,
                  children: [
                    const Text(
                      'Compliance Score',
                      style: TextStyle(
                        fontSize: 14,
                        fontWeight: FontWeight.w700,
                        color: ProPalette.textHeading,
                      ),
                    ),
                    Container(
                      padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
                      decoration: BoxDecoration(
                        color: scoreColor.withValues(alpha: 0.12),
                        borderRadius: BorderRadius.circular(8),
                      ),
                      child: Text(
                        '$computedScore%',
                        style: TextStyle(
                          fontSize: 16,
                          fontWeight: FontWeight.w800,
                          color: scoreColor,
                        ),
                      ),
                    ),
                  ],
                ),
                const SizedBox(height: 10),
                ClipRRect(
                  borderRadius: BorderRadius.circular(8),
                  child: LinearProgressIndicator(
                    value: scoreRatio,
                    minHeight: 9,
                    backgroundColor: const Color(0xFFE5E7EB),
                    valueColor: AlwaysStoppedAnimation<Color>(scoreColor),
                  ),
                ),
                const SizedBox(height: 8),
                Text(
                  isCompliant
                      ? 'Fully Compliant • 0 Violations'
                      : '$violationCount Non-Compliant Issue(s) Detected',
                  style: TextStyle(
                    fontSize: 12,
                    fontWeight: FontWeight.w600,
                    color: scoreColor,
                  ),
                ),
              ],
            ),
          ),
          const SizedBox(height: 16),

          // 3. Overall Conclusion Card (Dynamically deduced based on violated rules)
          Container(
            padding: const EdgeInsets.all(16),
            decoration: BoxDecoration(
              color: conclusionBg,
              borderRadius: BorderRadius.circular(14),
              border: Border.all(color: conclusionBorder, width: 1.2),
            ),
            child: Row(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Icon(
                  isCompliant ? Icons.check_circle_rounded : Icons.cancel_rounded,
                  color: scoreColor,
                  size: 24,
                ),
                const SizedBox(width: 12),
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(
                        isCompliant
                            ? 'Overall Conclusion: Fully Compliant'
                            : 'Overall Conclusion: Non-Compliant',
                        style: TextStyle(
                          fontSize: 14,
                          fontWeight: FontWeight.w700,
                          color: conclusionTitleCol,
                        ),
                      ),
                      const SizedBox(height: 4),
                      Text(
                        isCompliant
                            ? 'This product satisfies all mandatory declarations required under the Legal Metrology (Packaged Commodities) Rules, 2011.'
                            : 'This product fails Legal Metrology (Packaged Commodities) Rules, 2011. $violationCount mandatory declaration rule(s) were NOT followed or are absent on this package.',
                        style: TextStyle(
                          fontSize: 12,
                          height: 1.4,
                          color: conclusionTextCol,
                        ),
                      ),
                    ],
                  ),
                ),
              ],
            ),
          ),
          const SizedBox(height: 16),

          // Voice Audio Summary Card (TTS in Marathi, Hindi, English)
          Container(
            padding: const EdgeInsets.all(14),
            decoration: BoxDecoration(
              color: Colors.white,
              borderRadius: BorderRadius.circular(14),
              border: Border.all(color: const Color(0xFFE2E8F0)),
              boxShadow: [
                BoxShadow(
                  color: Colors.black.withValues(alpha: 0.03),
                  blurRadius: 6,
                  offset: const Offset(0, 2),
                ),
              ],
            ),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.stretch,
              children: [
                Row(
                  mainAxisAlignment: MainAxisAlignment.spaceBetween,
                  children: [
                    Row(
                      children: [
                        Container(
                          padding: const EdgeInsets.all(7),
                          decoration: BoxDecoration(
                            color: const Color(0xFFECFDF5),
                            borderRadius: BorderRadius.circular(8),
                          ),
                          child: const Icon(Icons.volume_up_rounded, color: ProPalette.accentEmerald, size: 20),
                        ),
                        const SizedBox(width: 8),
                        const Text(
                          'Voice Summary (अहवाल ध्वनी)',
                          style: TextStyle(
                            fontSize: 14,
                            fontWeight: FontWeight.w700,
                            color: ProPalette.textHeading,
                          ),
                        ),
                      ],
                    ),
                    // Language Selector Dropdown (Marathi, Hindi, English)
                    Container(
                      padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 2),
                      decoration: BoxDecoration(
                        color: const Color(0xFFF1F5F9),
                        borderRadius: BorderRadius.circular(8),
                      ),
                      child: DropdownButtonHideUnderline(
                        child: DropdownButton<VoiceLanguage>(
                          value: _selectedTtsLang,
                          isDense: true,
                          icon: const Icon(Icons.arrow_drop_down, size: 18),
                          onChanged: (lang) {
                            if (lang != null) setState(() => _selectedTtsLang = lang);
                          },
                          items: VoiceLanguage.values.map((lang) {
                            return DropdownMenuItem(
                              value: lang,
                              child: Text(
                                lang.shortLabel,
                                style: const TextStyle(fontSize: 12, fontWeight: FontWeight.w600),
                              ),
                            );
                          }).toList(),
                        ),
                      ),
                    ),
                  ],
                ),
                const SizedBox(height: 8),
                Text(
                  _isSpeaking
                      ? 'वाचन सुरू आहे (${_selectedTtsLang.shortLabel})...'
                      : 'या अहवालाचा संपूर्ण कायदेशीर ध्वनी सारांश ${_selectedTtsLang.shortLabel} मध्ये ऐका.',
                  style: const TextStyle(fontSize: 12, color: ProPalette.textMuted),
                ),
                const SizedBox(height: 10),
                ElevatedButton.icon(
                  onPressed: () => _toggleTtsSummary(
                    productName: productName,
                    manufacturer: manufacturer,
                    score: computedScore,
                    violations: violations.map((v) => '${v['rule']}: ${v['title']}').toList(),
                  ),
                  icon: Icon(_isSpeaking ? Icons.stop_rounded : Icons.play_arrow_rounded, color: Colors.white, size: 20),
                  label: Text(
                    _isSpeaking ? 'Stop Audio' : 'Play Voice Summary (${_selectedTtsLang.shortLabel})',
                    style: const TextStyle(fontSize: 13, fontWeight: FontWeight.w700, color: Colors.white),
                  ),
                  style: ElevatedButton.styleFrom(
                    backgroundColor: _isSpeaking ? const Color(0xFFDC2626) : ProPalette.primaryForest,
                    padding: const EdgeInsets.symmetric(vertical: 10),
                    shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(10)),
                  ),
                ),
              ],
            ),
          ),
          const SizedBox(height: 18),

          // 4. Violated Rules & Reasons Section
          // User requirement: "Only show that which rules are not followed and deduce the compliance on the basis of that."
          if (violations.isNotEmpty) ...[
            Row(
              children: [
                Container(
                  padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
                  decoration: BoxDecoration(
                    color: const Color(0xFFFEF2F2),
                    borderRadius: BorderRadius.circular(6),
                    border: Border.all(color: const Color(0xFFFCA5A5)),
                  ),
                  child: Text(
                    '$violationCount VIOLATIONS',
                    style: const TextStyle(
                      fontSize: 11,
                      fontWeight: FontWeight.w800,
                      color: Color(0xFF991B1B),
                    ),
                  ),
                ),
                const SizedBox(width: 8),
                const Text(
                  'Rules Not Followed & Reasons',
                  style: TextStyle(
                    fontSize: 15,
                    fontWeight: FontWeight.w800,
                    color: ProPalette.textHeading,
                  ),
                ),
              ],
            ),
            const SizedBox(height: 12),
            ...violations.map((v) => _buildViolatedRuleCard(context, v)),
          ] else ...[
            Container(
              padding: const EdgeInsets.all(16),
              decoration: BoxDecoration(
                color: const Color(0xFFF0FDF4),
                borderRadius: BorderRadius.circular(12),
                border: Border.all(color: const Color(0xFFBBF7D0)),
              ),
              child: Row(
                children: const [
                  Icon(Icons.verified_rounded, color: Color(0xFF059669), size: 24),
                  SizedBox(width: 12),
                  Expanded(
                    child: Text(
                      'No violations detected. All mandatory Legal Metrology declarations are followed.',
                      style: TextStyle(
                        fontSize: 13,
                        fontWeight: FontWeight.w600,
                        color: Color(0xFF166534),
                      ),
                    ),
                  ),
                ],
              ),
            ),
          ],
          const SizedBox(height: 24),
        ],
      ),
    );
  }

  Widget _buildViolatedRuleCard(BuildContext context, Map<String, String> violation) {
    final rule = violation['rule'] ?? 'Legal Metrology Rule';
    final title = violation['title'] ?? 'Mandatory Declaration';
    final reason = violation['reason'] ?? 'Declaration missing or non-compliant.';
    final severity = violation['severity'] ?? 'HIGH';
    final basis = violation['legalBasis'] ?? 'Legal Metrology (Packaged Commodities) Rules, 2011';

    return Container(
      margin: const EdgeInsets.only(bottom: 12),
      padding: const EdgeInsets.all(14),
      decoration: BoxDecoration(
        color: Colors.white,
        borderRadius: BorderRadius.circular(12),
        border: Border.all(color: const Color(0xFFFECACA), width: 1.2),
        boxShadow: [
          BoxShadow(
            color: Colors.black.withValues(alpha: 0.03),
            blurRadius: 6,
            offset: const Offset(0, 2),
          ),
        ],
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            mainAxisAlignment: MainAxisAlignment.spaceBetween,
            children: [
              Container(
                padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
                decoration: BoxDecoration(
                  color: const Color(0xFFFEF2F2),
                  borderRadius: BorderRadius.circular(6),
                  border: Border.all(color: const Color(0xFFFCA5A5)),
                ),
                child: Row(
                  mainAxisSize: MainAxisSize.min,
                  children: [
                    const Icon(Icons.gavel_rounded, size: 12, color: Color(0xFFDC2626)),
                    const SizedBox(width: 4),
                    Text(
                      rule,
                      style: const TextStyle(
                        fontSize: 11,
                        fontWeight: FontWeight.w800,
                        color: Color(0xFF991B1B),
                      ),
                    ),
                  ],
                ),
              ),
              Container(
                padding: const EdgeInsets.symmetric(horizontal: 7, vertical: 2),
                decoration: BoxDecoration(
                  color: severity == 'CRITICAL' ? const Color(0xFF7F1D1D) : const Color(0xFFDC2626),
                  borderRadius: BorderRadius.circular(4),
                ),
                child: Text(
                  severity,
                  style: const TextStyle(
                    fontSize: 10,
                    fontWeight: FontWeight.w800,
                    color: Colors.white,
                    letterSpacing: 0.4,
                  ),
                ),
              ),
            ],
          ),
          const SizedBox(height: 8),
          Text(
            title,
            style: const TextStyle(
              fontSize: 14,
              fontWeight: FontWeight.w700,
              color: ProPalette.textHeading,
            ),
          ),
          const SizedBox(height: 4),
          Row(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              const Padding(
                padding: EdgeInsets.only(top: 2, right: 6),
                child: Icon(Icons.error_outline_rounded, size: 14, color: Color(0xFFDC2626)),
              ),
              Expanded(
                child: Text(
                  reason,
                  style: const TextStyle(
                    fontSize: 12.5,
                    height: 1.35,
                    color: Color(0xFF374151),
                  ),
                ),
              ),
            ],
          ),
          const SizedBox(height: 8),
          Container(
            padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
            decoration: BoxDecoration(
              color: const Color(0xFFF9FAFB),
              borderRadius: BorderRadius.circular(6),
            ),
            child: Row(
              children: [
                const Icon(Icons.menu_book_outlined, size: 12, color: Color(0xFF6B7280)),
                const SizedBox(width: 6),
                Expanded(
                  child: Text(
                    basis,
                    style: const TextStyle(
                      fontSize: 10.5,
                      color: Color(0xFF6B7280),
                      fontStyle: FontStyle.italic,
                    ),
                  ),
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }

  String _inferRuleNumber(String text) {
    final lower = text.toLowerCase();
    if (lower.contains('mrp') || lower.contains('retail price')) return 'Rule 6(1)(c)';
    if (lower.contains('net qty') || lower.contains('net quantity') || lower.contains('weight') || lower.contains('volume')) return 'Rule 6(1)(e)';
    if (lower.contains('mfg') || lower.contains('date') || lower.contains('pack') || lower.contains('expiry')) return 'Rule 6(1)(d)';
    if (lower.contains('customer') || lower.contains('care') || lower.contains('helpline') || lower.contains('email')) return 'Rule 6(1)(h)';
    if (lower.contains('manufacturer') || lower.contains('address') || lower.contains('packer') || lower.contains('importer')) return 'Rule 6(1)(a)';
    if (lower.contains('unit sale') || lower.contains('usp')) return 'Rule 6(1)(k)';
    return 'Rule 6(1)';
  }

  String _inferRuleTitle(String text) {
    final lower = text.toLowerCase();
    if (lower.contains('mrp') || lower.contains('retail price')) return 'Maximum Retail Price (MRP)';
    if (lower.contains('net qty') || lower.contains('net quantity') || lower.contains('weight')) return 'Net Quantity Declaration';
    if (lower.contains('mfg') || lower.contains('date') || lower.contains('pack') || lower.contains('expiry')) return 'Date of Manufacture / Packing';
    if (lower.contains('customer') || lower.contains('care') || lower.contains('helpline')) return 'Consumer Care Helpline & Redressal';
    if (lower.contains('manufacturer') || lower.contains('address') || lower.contains('packer')) return 'Manufacturer Name & Address';
    if (lower.contains('unit sale') || lower.contains('usp')) return 'Unit Sale Price (USP)';
    return text;
  }

  // =========================================================================
  // SCREEN 7: EVIDENCE TAB
  // =========================================================================
  Widget _buildEvidenceTab(BuildContext context) {
    final analysis = widget.args.analysis;
    final netQty = analysis.netQuantity.isNotEmpty ? analysis.netQuantity : 'Not Found';
    final mrp = analysis.mrp.isNotEmpty ? analysis.mrp : 'Not Found';

    return SingleChildScrollView(
      padding: const EdgeInsets.all(20),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          // Segmented Control: Detected Text | Label Image | Analysis
          Container(
            padding: const EdgeInsets.all(4),
            decoration: BoxDecoration(
              color: const Color(0xFFF1F5F9),
              borderRadius: BorderRadius.circular(12),
            ),
            child: Row(
              children: ['Detected Text', 'Label Image', 'Analysis'].map((tab) {
                final isSelected = tab == _evidenceMode;
                return Expanded(
                  child: GestureDetector(
                    onTap: () => setState(() => _evidenceMode = tab),
                    child: Container(
                      padding: const EdgeInsets.symmetric(vertical: 8),
                      decoration: BoxDecoration(
                        color: isSelected ? Colors.white : Colors.transparent,
                        borderRadius: BorderRadius.circular(10),
                        boxShadow: isSelected
                            ? [
                                BoxShadow(
                                  color: Colors.black.withValues(alpha: 0.05),
                                  blurRadius: 4,
                                  offset: const Offset(0, 2),
                                ),
                              ]
                            : null,
                      ),
                      alignment: Alignment.center,
                      child: Text(
                        tab,
                        style: TextStyle(
                          fontSize: 12,
                          fontWeight: isSelected ? FontWeight.w700 : FontWeight.w500,
                          color: isSelected ? ProPalette.textHeading : ProPalette.textMuted,
                        ),
                      ),
                    ),
                  ),
                );
              }).toList(),
            ),
          ),
          const SizedBox(height: 20),

          // Photo Preview with Interactive Bounding Box Callouts
          Container(
            height: 260,
            decoration: BoxDecoration(
              color: const Color(0xFF1E293B),
              borderRadius: BorderRadius.circular(16),
            ),
            child: Stack(
              children: [
                // Product Label Image or Graphic
                Center(
                  child: widget.args.primaryImage != null
                      ? ClipRRect(
                          borderRadius: BorderRadius.circular(16),
                          child: Image.file(
                            File(widget.args.primaryImage!.path),
                            fit: BoxFit.cover,
                            width: double.infinity,
                            height: double.infinity,
                          ),
                        )
                      : Container(
                          color: const Color(0xFF334155),
                          child: const Center(
                            child: Icon(Icons.qr_code_scanner, color: Colors.white38, size: 64),
                          ),
                        ),
                ),

                // Bounding Box 1: Net Quantity Callout
                Positioned(
                  top: 50,
                  left: 30,
                  child: Container(
                    padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 6),
                    decoration: BoxDecoration(
                      color: Colors.white,
                      borderRadius: BorderRadius.circular(8),
                      border: Border.all(color: ProPalette.accentEmerald, width: 1.5),
                      boxShadow: [
                        BoxShadow(
                          color: Colors.black.withValues(alpha: 0.2),
                          blurRadius: 6,
                          offset: const Offset(0, 2),
                        ),
                      ],
                    ),
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        const Text(
                          'Net Quantity',
                          style: TextStyle(fontSize: 10, color: ProPalette.textMuted),
                        ),
                        Text(
                          netQty,
                          style: const TextStyle(fontSize: 13, fontWeight: FontWeight.w700, color: ProPalette.textHeading),
                        ),
                      ],
                    ),
                  ),
                ),

                // Bounding Box 2: MRP Callout
                Positioned(
                  bottom: 40,
                  left: 30,
                  child: Container(
                    padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 6),
                    decoration: BoxDecoration(
                      color: Colors.white,
                      borderRadius: BorderRadius.circular(8),
                      border: Border.all(color: ProPalette.accentEmerald, width: 1.5),
                      boxShadow: [
                        BoxShadow(
                          color: Colors.black.withValues(alpha: 0.2),
                          blurRadius: 6,
                          offset: const Offset(0, 2),
                        ),
                      ],
                    ),
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        const Text(
                          'MRP',
                          style: TextStyle(fontSize: 10, color: ProPalette.textMuted),
                        ),
                        Text(
                          mrp,
                          style: const TextStyle(fontSize: 13, fontWeight: FontWeight.w700, color: ProPalette.textHeading),
                        ),
                      ],
                    ),
                  ),
                ),
              ],
            ),
          ),
          const SizedBox(height: 20),

          // Extracted Information Card with [Edit] Pencil Button
          Container(
            padding: const EdgeInsets.all(16),
            decoration: ProPalette.cardDecoration(context, radius: 14),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.stretch,
              children: [
                Row(
                  mainAxisAlignment: MainAxisAlignment.spaceBetween,
                  children: [
                    const Text(
                      'Extracted Information',
                      style: TextStyle(
                        fontSize: 14,
                        fontWeight: FontWeight.w700,
                        color: ProPalette.textHeading,
                      ),
                    ),
                    Row(
                      children: const [
                        Icon(Icons.edit_outlined, size: 14, color: ProPalette.primaryForest),
                        SizedBox(width: 4),
                        Text(
                          'Edit',
                          style: TextStyle(
                            fontSize: 13,
                            fontWeight: FontWeight.w600,
                            color: ProPalette.primaryForest,
                          ),
                        ),
                      ],
                    ),
                  ],
                ),
                const SizedBox(height: 12),
                const Divider(height: 1, color: Color(0xFFF1F5F9)),
                const SizedBox(height: 12),
                _buildInfoRow('Net Quantity', netQty),
                _buildInfoRow('MRP', mrp),
                _buildInfoRow('Manufacturer', analysis.manufacturer.isNotEmpty ? analysis.manufacturer : 'Not Found'),
              ],
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildInfoRow(String label, String value) {
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 6),
      child: Row(
        mainAxisAlignment: MainAxisAlignment.spaceBetween,
        children: [
          Text(label, style: const TextStyle(fontSize: 13, color: ProPalette.textMuted)),
          Text(value, style: const TextStyle(fontSize: 13, fontWeight: FontWeight.w600, color: ProPalette.textHeading)),
        ],
      ),
    );
  }

  // =========================================================================
  // SCREEN 8: REGULATIONS TAB
  // =========================================================================
  Widget _buildRegulationsTab(BuildContext context) {
    final analysis = widget.args.analysis;

    // Check which mandatory rules passed vs violated
    final issues = analysis.possibleIssues;
    final missing = analysis.missingInformation;
    final isViolation = (String keyword) {
      final k = keyword.toLowerCase();
      return issues.any((i) => i.title.toLowerCase().contains(k) || i.description.toLowerCase().contains(k)) ||
          missing.any((m) => m.toLowerCase().contains(k));
    };

    final mrpViolated = isViolation('mrp') || isViolation('price');
    final qtyViolated = isViolation('net qty') || isViolation('quantity') || isViolation('weight');
    final dateViolated = isViolation('mfg') || isViolation('date') || isViolation('pack');
    final mfrViolated = isViolation('manufacturer') || isViolation('packer') || isViolation('address');
    final careViolated = isViolation('customer') || isViolation('care') || isViolation('helpline');

    return SingleChildScrollView(
      padding: const EdgeInsets.all(20),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          // 1. Legal Metrology Act Card
          _buildActCard(
            context,
            icon: Icons.gavel_rounded,
            iconColor: ProPalette.purpleAct,
            iconBg: ProPalette.purpleBg,
            title: 'Legal Metrology Act, 2009',
            subtitle: 'Packaged Commodities Rules, 2011',
          ),
          const SizedBox(height: 16),

          // 2. Dynamic Clause Compliance Status
          const Text(
            'Applicable Mandatory Declarations',
            style: TextStyle(
              fontSize: 15,
              fontWeight: FontWeight.w700,
              color: ProPalette.textHeading,
            ),
          ),
          const SizedBox(height: 12),

          _buildDynamicClauseTile('Rule 6(1)(a)', 'Name and address of manufacturer / packer', !mfrViolated),
          _buildDynamicClauseTile('Rule 6(1)(c)', 'Maximum Retail Price (MRP inclusive of all taxes)', !mrpViolated),
          _buildDynamicClauseTile('Rule 6(1)(d)', 'Month and year of manufacture or pre-packing', !dateViolated),
          _buildDynamicClauseTile('Rule 6(1)(e)', 'Net quantity in standard units of weight or measure', !qtyViolated),
          _buildDynamicClauseTile('Rule 6(1)(h)', 'Consumer care helpline, email & grievance address', !careViolated),
        ],
      ),
    );
  }

  Widget _buildDynamicClauseTile(String clause, String title, bool passed) {
    return Container(
      margin: const EdgeInsets.only(bottom: 10),
      padding: const EdgeInsets.all(12),
      decoration: BoxDecoration(
        color: Colors.white,
        borderRadius: BorderRadius.circular(10),
        border: Border.all(
          color: passed ? const Color(0xFFBBF7D0) : const Color(0xFFFECACA),
          width: 1,
        ),
      ),
      child: Row(
        children: [
          Icon(
            passed ? Icons.check_circle : Icons.cancel,
            color: passed ? const Color(0xFF059669) : const Color(0xFFDC2626),
            size: 20,
          ),
          const SizedBox(width: 10),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  clause,
                  style: TextStyle(
                    fontSize: 11,
                    fontWeight: FontWeight.w800,
                    color: passed ? const Color(0xFF166534) : const Color(0xFF991B1B),
                  ),
                ),
                Text(
                  title,
                  style: const TextStyle(fontSize: 12.5, fontWeight: FontWeight.w600, color: ProPalette.textHeading),
                ),
              ],
            ),
          ),
          Container(
            padding: const EdgeInsets.symmetric(horizontal: 7, vertical: 2),
            decoration: BoxDecoration(
              color: passed ? const Color(0xFFDCFCE7) : const Color(0xFFFEE2E2),
              borderRadius: BorderRadius.circular(4),
            ),
            child: Text(
              passed ? 'COMPLIANT' : 'VIOLATION',
              style: TextStyle(
                fontSize: 10,
                fontWeight: FontWeight.w800,
                color: passed ? const Color(0xFF166534) : const Color(0xFF991B1B),
              ),
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildActCard(
    BuildContext context, {
    required IconData icon,
    required Color iconColor,
    required Color iconBg,
    required String title,
    required String subtitle,
  }) {
    return Container(
      padding: const EdgeInsets.all(16),
      decoration: ProPalette.cardDecoration(context, radius: 14),
      child: Row(
        children: [
          Container(
            width: 44,
            height: 44,
            decoration: BoxDecoration(
              color: iconBg,
              borderRadius: BorderRadius.circular(10),
            ),
            child: Icon(icon, color: iconColor, size: 24),
          ),
          const SizedBox(width: 14),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  title,
                  style: const TextStyle(fontSize: 14, fontWeight: FontWeight.w700, color: ProPalette.textHeading),
                ),
                const SizedBox(height: 2),
                Text(
                  subtitle,
                  style: const TextStyle(fontSize: 12, color: ProPalette.textMuted),
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildClauseTile(String clause, String desc) {
    return Container(
      margin: const EdgeInsets.only(bottom: 10),
      padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 14),
      decoration: ProPalette.cardDecoration(context, radius: 12),
      child: Row(
        children: [
          Container(
            padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
            decoration: BoxDecoration(
              color: const Color(0xFFFEF3C7),
              borderRadius: BorderRadius.circular(6),
            ),
            child: Text(
              clause,
              style: const TextStyle(fontSize: 11, fontWeight: FontWeight.w700, color: Color(0xFFB45309)),
            ),
          ),
          const SizedBox(width: 14),
          Expanded(
            child: Text(
              desc,
              style: const TextStyle(fontSize: 13, fontWeight: FontWeight.w600, color: ProPalette.textHeading),
            ),
          ),
          const Icon(Icons.arrow_forward_ios_rounded, size: 14, color: Color(0xFF94A3B8)),
        ],
      ),
    );
  }

  // =========================================================================
  // DETAILS TAB
  // =========================================================================
  Widget _buildDetailsTab(BuildContext context) {
    final analysis = widget.args.analysis;
    return SingleChildScrollView(
      padding: const EdgeInsets.all(20),
      child: Container(
        padding: const EdgeInsets.all(16),
        decoration: ProPalette.cardDecoration(context, radius: 14),
        child: Column(
          children: [
            _buildInfoRow('Product Name', analysis.productName.isNotEmpty ? analysis.productName : "Unknown Product"),
            _buildInfoRow('Category', 'Packaged Product'),
            _buildInfoRow('MRP', analysis.mrp.isNotEmpty ? analysis.mrp : 'Not Found'),
            _buildInfoRow('Net Quantity', analysis.netQuantity.isNotEmpty ? analysis.netQuantity : 'Not Found'),
            _buildInfoRow('Manufacturer', analysis.manufacturer.isNotEmpty ? analysis.manufacturer : 'Unknown Manufacturer'),
            _buildInfoRow('Packing Date', analysis.packingDate.isNotEmpty ? analysis.packingDate : 'Not Found'),
            _buildInfoRow('Consumer Care', analysis.customerCare.isNotEmpty ? analysis.customerCare : 'Not Found'),
            _buildInfoRow('Standard', 'Legal Metrology (Packaged Commodities) Rules, 2011'),
          ],
        ),
      ),
    );
  }
}
