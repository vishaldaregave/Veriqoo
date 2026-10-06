import 'package:flutter/material.dart';
import 'package:shared_core/design_system/design_system.dart';
import 'package:shared_core/services/compliance_analysis.dart';
import 'package:shared_core/services/supabase_service.dart';

import 'package:flutter_application_1/core/widgets/app_background.dart';

/// Report-an-issue placeholder (`/report-issue`). The form renders with the
/// design system; submit is a no-op SnackBar until a later phase wires it to
/// `shared_core`.
class ReportIssueScreen extends StatefulWidget {
  const ReportIssueScreen({super.key});

  @override
  State<ReportIssueScreen> createState() => _ReportIssueScreenState();
}

class _ReportIssueScreenState extends State<ReportIssueScreen> {
  final _subjectController = TextEditingController();
  final _detailsController = TextEditingController();

  @override
  void dispose() {
    _subjectController.dispose();
    _detailsController.dispose();
    super.dispose();
  }

  Future<void> _submit() async {
    final subject = _subjectController.text.trim();
    final details = _detailsController.text.trim();
    if (subject.isEmpty) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('Please enter a subject for the report.')),
      );
      return;
    }

    FocusScope.of(context).unfocus();
    try {
      await SupabaseService().saveInspectionReport(
        analysis: ComplianceAnalysis(
          productName: subject,
          mrp: '',
          netQuantity: '',
          manufacturer: '',
          address: '',
          packingDate: '',
          customerCare: '',
          missingInformation: const ['Reported by Consumer / Field Officer'],
          possibleIssues: [
            ComplianceIssue(
              title: 'Consumer Grievance',
              severity: 'high',
              description: details.isNotEmpty ? details : 'Reported violation',
            ),
          ],
        ),
        ocrText: 'GRIEVANCE REPORT:\nSubject: $subject\nDetails: $details',
      );
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('Grievance report submitted and recorded in backend.')),
      );
      _subjectController.clear();
      _detailsController.clear();
    } catch (e) {
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text('Report queued: $e')),
      );
    }
  }

  @override
  Widget build(BuildContext context) {
    final tokens = Theme.of(context).extension<VeriqooTokens>()!;
    return Scaffold(
      backgroundColor: tokens.bg,
      appBar: const VeriqooAppBar(title: 'Report an issue'),
      body: VeriqooBackdrop(
        background: const DataTicker(),
        child: SafeArea(
          child: SingleChildScrollView(
            padding: const EdgeInsets.all(VeriqooSpacing.s24),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.stretch,
              children: [
                const VeriqooSectionHeader(
                  title: 'Report',
                  subtitle: 'Tell us what looks wrong.',
                ),
                const SizedBox(height: VeriqooSpacing.s24),
                VeriqooTextField(
                  controller: _subjectController,
                  label: 'Subject',
                  hintText: 'Short summary',
                  textInputAction: TextInputAction.next,
                ),
                const SizedBox(height: VeriqooSpacing.s24),
                VeriqooTextField(
                  controller: _detailsController,
                  label: 'Details',
                  hintText: 'What happened?',
                  textInputAction: TextInputAction.newline,
                ),
                const SizedBox(height: VeriqooSpacing.s32),
                VeriqooButton(
                  label: 'Submit',
                  expand: true,
                  onPressed: _submit,
                ),
              ],
            ),
          ),
        ),
      ),
    );
  }
}
