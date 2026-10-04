import 'package:flutter/material.dart';
import 'package:flutter_application_1/services/compliance_analysis.dart';
import 'package:flutter_application_1/services/consumer_issue_api_service.dart';

/// Modal dialog allowing consumers to report Legal Metrology violations to the backend.
class ReportViolationDialog extends StatefulWidget {
  final ComplianceAnalysis analysis;
  final String? inspectionId;
  final String ocrText;
  final ConsumerIssueApiService? apiService;

  const ReportViolationDialog({
    super.key,
    required this.analysis,
    this.inspectionId,
    required this.ocrText,
    this.apiService,
  });

  @override
  State<ReportViolationDialog> createState() => _ReportViolationDialogState();
}

class _ReportViolationDialogState extends State<ReportViolationDialog> {
  late final ConsumerIssueApiService _apiService;
  late final TextEditingController _titleController;
  late final TextEditingController _descriptionController;

  String? _activeInspectionId;
  String _selectedIssueType = 'MISLEADING_LABEL';
  bool _isSubmitting = false;
  String? _errorMessage;
  ConsumerIssueReport? _submittedReport;

  static const Map<String, String> _issueTypeLabels = {
    'MISLEADING_LABEL': 'Misleading Label / Deceptive Packaging',
    'PRICE_TAMPERING': 'Price Tampering / Dual MRP',
    'WEIGHT_SHORTAGE': 'Weight Shortage / Net Quantity Mismatch',
    'EXPIRED_PRODUCT': 'Expired Product / Outdated Stock',
    'MISSING_MANDATORY_INFO': 'Missing Mandatory Declarations (Rule 6)',
    'OTHER': 'Other Legal Metrology Violation',
  };

  @override
  void initState() {
    super.initState();
    _apiService = widget.apiService ?? ConsumerIssueApiService();
    _activeInspectionId = widget.inspectionId;

    // Infer preselected issue type from detected issues if available
    if (widget.analysis.possibleIssues.isNotEmpty) {
      final firstIssue = widget.analysis.possibleIssues.first.title.toLowerCase();
      if (firstIssue.contains('mrp') || firstIssue.contains('price')) {
        _selectedIssueType = 'PRICE_TAMPERING';
      } else if (firstIssue.contains('weight') || firstIssue.contains('quantity')) {
        _selectedIssueType = 'WEIGHT_SHORTAGE';
      } else if (firstIssue.contains('date') || firstIssue.contains('expire')) {
        _selectedIssueType = 'EXPIRED_PRODUCT';
      } else {
        _selectedIssueType = 'MISLEADING_LABEL';
      }
    } else if (widget.analysis.missingInformation.isNotEmpty) {
      _selectedIssueType = 'MISSING_MANDATORY_INFO';
    }

    final pName = widget.analysis.productName.isNotEmpty
        ? widget.analysis.productName
        : 'Packaged Commodity';
    _titleController = TextEditingController(text: 'Violation on $pName');

    final descBuffer = StringBuffer();
    if (widget.analysis.possibleIssues.isNotEmpty) {
      descBuffer.writeln('Detected Issues:');
      for (final issue in widget.analysis.possibleIssues) {
        descBuffer.writeln('- ${issue.title}: ${issue.description}');
      }
    }
    if (widget.analysis.missingInformation.isNotEmpty) {
      if (descBuffer.isNotEmpty) descBuffer.writeln();
      descBuffer.writeln('Missing Mandatory Information:');
      for (final item in widget.analysis.missingInformation) {
        descBuffer.writeln('- $item');
      }
    }
    _descriptionController = TextEditingController(
      text: descBuffer.toString().trim(),
    );
  }

  @override
  void dispose() {
    _titleController.dispose();
    _descriptionController.dispose();
    super.dispose();
  }

  Future<void> _handleSubmit() async {
    final title = _titleController.text.trim();
    final description = _descriptionController.text.trim();

    if (title.isEmpty) {
      setState(() => _errorMessage = 'Please provide a short summary title.');
      return;
    }
    if (description.isEmpty) {
      setState(() => _errorMessage = 'Please describe the observed violation.');
      return;
    }

    setState(() {
      _isSubmitting = true;
      _errorMessage = null;
    });

    try {
      // 1. Ensure a server inspection session exists for foreign-key validation.
      // Re-use _activeInspectionId across retry attempts to avoid minting redundant
      // inspection containers and preserve idempotency & duplicate checks.
      String targetInspectionId = _activeInspectionId ?? '';
      if (targetInspectionId.isEmpty) {
        targetInspectionId = await _apiService.ensureInspectionSession(
          productName: widget.analysis.productName.isNotEmpty
              ? widget.analysis.productName
              : 'Unknown Product',
          metadata: {
            'product_name': widget.analysis.productName,
            'mrp': widget.analysis.mrp,
            'net_quantity': widget.analysis.netQuantity,
            'manufacturer': widget.analysis.manufacturer,
            'address': widget.analysis.address,
            'packing_date': widget.analysis.packingDate,
            'customer_care': widget.analysis.customerCare,
            'missing_information': widget.analysis.missingInformation,
            'violations_count': widget.analysis.possibleIssues.length,
            'ocr_snippet': widget.ocrText.length > 300
                ? widget.ocrText.substring(0, 300)
                : widget.ocrText,
          },
        );
        _activeInspectionId = targetInspectionId;
      }

      // 2. Submit the verified issue report to FastAPI backend
      final report = await _apiService.submitIssue(
        inspectionId: targetInspectionId,
        issueType: _selectedIssueType,
        title: title,
        description: description,
      );

      if (!mounted) return;
      setState(() {
        _isSubmitting = false;
        _submittedReport = report;
      });
    } on ConsumerIssueApiException catch (e) {
      if (!mounted) return;
      setState(() {
        _isSubmitting = false;
        if (e.code == 'DUPLICATE_CONSUMER_ISSUE') {
          _errorMessage =
              'Duplicate Complaint: A complaint for this issue type has already been submitted for this product.';
        } else if (e.statusCode == 401) {
          _errorMessage = 'Authentication required. Please sign in to file a complaint.';
        } else if (e.code == 'NETWORK_ERROR') {
          _errorMessage =
              'Network Error: Unable to reach the Veriqoo compliance server. Please check your connection.';
        } else {
          _errorMessage = e.message;
        }
      });
    } catch (e) {
      if (!mounted) return;
      setState(() {
        _isSubmitting = false;
        _errorMessage = 'An unexpected error occurred: $e';
      });
    }
  }

  @override
  Widget build(BuildContext context) {
    return Dialog(
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(20)),
      backgroundColor: Colors.white,
      insetPadding: const EdgeInsets.symmetric(horizontal: 20, vertical: 24),
      child: ConstrainedBox(
        constraints: const BoxConstraints(maxWidth: 540),
        child: Padding(
          padding: const EdgeInsets.all(24),
          child: _submittedReport != null
              ? _buildSuccessView(_submittedReport!)
              : _buildFormView(),
        ),
      ),
    );
  }

  Widget _buildFormView() {
    return SingleChildScrollView(
      child: Column(
        mainAxisSize: MainAxisSize.min,
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Container(
                padding: const EdgeInsets.all(10),
                decoration: BoxDecoration(
                  color: const Color(0xFFFDECEA),
                  borderRadius: BorderRadius.circular(12),
                ),
                child: const Icon(Icons.gavel_rounded, color: Color(0xFFC53030), size: 24),
              ),
              const SizedBox(width: 14),
              const Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      'Report Violation',
                      style: TextStyle(
                        fontSize: 20,
                        fontWeight: FontWeight.w800,
                        color: Color(0xFF183B32),
                      ),
                    ),
                    SizedBox(height: 2),
                    Text(
                      'Legal Metrology Department Complaint',
                      style: TextStyle(fontSize: 12, color: Color(0xFF6B7280)),
                    ),
                  ],
                ),
              ),
              IconButton(
                icon: const Icon(Icons.close, color: Colors.grey),
                onPressed: _isSubmitting ? null : () => Navigator.of(context).pop(),
              ),
            ],
          ),
          const SizedBox(height: 18),

          // Error Banner
          if (_errorMessage != null) ...[
            Container(
              key: const Key('report_error_banner'),
              width: double.infinity,
              padding: const EdgeInsets.all(12),
              decoration: BoxDecoration(
                color: const Color(0xFFFDECEA),
                borderRadius: BorderRadius.circular(10),
                border: Border.all(color: const Color(0xFFF5C6CB)),
              ),
              child: Row(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  const Icon(Icons.error_outline_rounded, color: Color(0xFFC53030), size: 20),
                  const SizedBox(width: 10),
                  Expanded(
                    child: Text(
                      _errorMessage!,
                      style: const TextStyle(fontSize: 13, color: Color(0xFF721C24)),
                    ),
                  ),
                ],
              ),
            ),
            const SizedBox(height: 14),
          ],

          // Inspection Reference
          Text(
            'Target Product: ${widget.analysis.productName.isNotEmpty ? widget.analysis.productName : "Packaged Commodity"}',
            style: const TextStyle(fontSize: 13, fontWeight: FontWeight.w600, color: Color(0xFF4B5563)),
          ),
          const SizedBox(height: 14),

          // Issue Type Dropdown
          const Text(
            'Violation Category',
            style: TextStyle(fontSize: 14, fontWeight: FontWeight.w700, color: Color(0xFF1F2937)),
          ),
          const SizedBox(height: 6),
          DropdownButtonFormField<String>(
            key: const Key('issue_type_dropdown'),
            isExpanded: true,
            initialValue: _selectedIssueType,
            decoration: InputDecoration(
              contentPadding: const EdgeInsets.symmetric(horizontal: 14, vertical: 12),
              border: OutlineInputBorder(borderRadius: BorderRadius.circular(10)),
            ),
            items: _issueTypeLabels.entries
                .map((e) => DropdownMenuItem(
                      value: e.key,
                      child: Text(
                        e.value,
                        overflow: TextOverflow.ellipsis,
                        style: const TextStyle(fontSize: 13),
                      ),
                    ))
                .toList(),
            onChanged: _isSubmitting ? null : (v) => setState(() => _selectedIssueType = v ?? 'MISLEADING_LABEL'),
          ),
          const SizedBox(height: 14),

          // Title Input
          const Text(
            'Summary Title',
            style: TextStyle(fontSize: 14, fontWeight: FontWeight.w700, color: Color(0xFF1F2937)),
          ),
          const SizedBox(height: 6),
          TextField(
            key: const Key('issue_title_input'),
            controller: _titleController,
            enabled: !_isSubmitting,
            decoration: InputDecoration(
              hintText: 'e.g. Missing MRP on packaged snack',
              contentPadding: const EdgeInsets.symmetric(horizontal: 14, vertical: 12),
              border: OutlineInputBorder(borderRadius: BorderRadius.circular(10)),
            ),
          ),
          const SizedBox(height: 14),

          // Description Input
          const Text(
            'Detailed Description',
            style: TextStyle(fontSize: 14, fontWeight: FontWeight.w700, color: Color(0xFF1F2937)),
          ),
          const SizedBox(height: 6),
          TextField(
            key: const Key('issue_description_input'),
            controller: _descriptionController,
            enabled: !_isSubmitting,
            maxLines: 4,
            decoration: InputDecoration(
              hintText: 'Explain the non-compliance observed on the packaging...',
              contentPadding: const EdgeInsets.all(12),
              border: OutlineInputBorder(borderRadius: BorderRadius.circular(10)),
            ),
          ),
          const SizedBox(height: 22),

          // Actions
          Wrap(
            alignment: WrapAlignment.end,
            crossAxisAlignment: WrapCrossAlignment.center,
            spacing: 10,
            runSpacing: 10,
            children: [
              TextButton(
                onPressed: _isSubmitting ? null : () => Navigator.of(context).pop(),
                child: const Text('Cancel'),
              ),
              ElevatedButton.icon(
                key: const Key('submit_complaint_button'),
                style: ElevatedButton.styleFrom(
                  backgroundColor: const Color(0xFFC53030),
                  foregroundColor: Colors.white,
                  padding: const EdgeInsets.symmetric(horizontal: 18, vertical: 12),
                  shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
                ),
                onPressed: _isSubmitting ? null : _handleSubmit,
                icon: _isSubmitting
                    ? const SizedBox(
                        width: 18,
                        height: 18,
                        child: CircularProgressIndicator(strokeWidth: 2, color: Colors.white),
                      )
                    : const Icon(Icons.send_rounded, size: 18),
                label: Text(
                  _isSubmitting ? 'Submitting...' : 'Submit Complaint',
                  style: const TextStyle(fontWeight: FontWeight.w700),
                ),
              ),
            ],
          ),
        ],
      ),
    );
  }

  Widget _buildSuccessView(ConsumerIssueReport report) {
    final isVerified = report.jurisdictionVerified;

    return Column(
      mainAxisSize: MainAxisSize.min,
      crossAxisAlignment: CrossAxisAlignment.center,
      children: [
        Container(
          padding: const EdgeInsets.all(16),
          decoration: const BoxDecoration(
            color: Color(0xFFEAF4EF),
            shape: BoxShape.circle,
          ),
          child: const Icon(Icons.check_circle_rounded, color: Color(0xFF183B32), size: 48),
        ),
        const SizedBox(height: 16),
        const Text(
          'Complaint Filed Successfully',
          style: TextStyle(
            fontSize: 22,
            fontWeight: FontWeight.w800,
            color: Color(0xFF183B32),
          ),
        ),
        const SizedBox(height: 8),
        Text(
          'Reference ID: ${report.id}',
          key: const Key('complaint_reference_id'),
          style: const TextStyle(
            fontSize: 13,
            fontWeight: FontWeight.w600,
            color: Color(0xFF4B5563),
          ),
        ),
        const SizedBox(height: 6),
        Container(
          padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
          decoration: BoxDecoration(
            color: const Color(0xFFFFF1D9),
            borderRadius: BorderRadius.circular(8),
          ),
          child: Text(
            'Status: ${report.status}',
            style: const TextStyle(
              fontSize: 12,
              fontWeight: FontWeight.w700,
              color: Color(0xFFB86512),
            ),
          ),
        ),
        const SizedBox(height: 18),

        // Jurisdiction Status Card
        Container(
          width: double.infinity,
          padding: const EdgeInsets.all(14),
          decoration: BoxDecoration(
            color: isVerified ? const Color(0xFFEAF4EF) : const Color(0xFFF3F4F6),
            borderRadius: BorderRadius.circular(12),
            border: Border.all(
              color: isVerified ? const Color(0xFFA7D5C0) : const Color(0xFFE5E7EB),
            ),
          ),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Row(
                children: [
                  Icon(
                    isVerified ? Icons.verified_user_rounded : Icons.info_outline_rounded,
                    color: isVerified ? const Color(0xFF183B32) : const Color(0xFF6B7280),
                    size: 18,
                  ),
                  const SizedBox(width: 8),
                  Expanded(
                    child: Text(
                      isVerified ? 'Jurisdiction Verified' : 'Jurisdiction Pending Verification',
                      style: TextStyle(
                        fontSize: 13,
                        fontWeight: FontWeight.w700,
                        color: isVerified ? const Color(0xFF183B32) : const Color(0xFF374151),
                      ),
                    ),
                  ),
                ],
              ),
              const SizedBox(height: 6),
              Text(
                isVerified
                    ? 'Routed to ${report.department} Department (${report.stateCode ?? ""} / ${report.districtCode ?? ""}).'
                    : 'Your complaint has been securely submitted. It will be routed to the appropriate Legal Metrology enforcement queue once retail premises jurisdiction is verified.',
                key: const Key('jurisdiction_status_text'),
                style: const TextStyle(fontSize: 12, color: Color(0xFF4B5563)),
              ),
            ],
          ),
        ),
        const SizedBox(height: 24),

        SizedBox(
          width: double.infinity,
          height: 48,
          child: ElevatedButton(
            key: const Key('dismiss_success_button'),
            style: ElevatedButton.styleFrom(
              backgroundColor: const Color(0xFF183B32),
              foregroundColor: Colors.white,
              shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
            ),
            onPressed: () => Navigator.of(context).pop(report),
            child: const Text('Done', style: TextStyle(fontWeight: FontWeight.w700)),
          ),
        ),
      ],
    );
  }
}
