import 'package:flutter/material.dart';
import 'package:shared_core/design_system/design_system.dart';

import 'package:flutter_application_1/core/widgets/app_background.dart';

/// Report detail placeholder (`/reports/:id`). Reads the report [id]; later
/// phases load the real compliance report.
class ReportDetailScreen extends StatelessWidget {
  const ReportDetailScreen({super.key, required this.id});

  final String id;

  @override
  Widget build(BuildContext context) {
    final tokens = Theme.of(context).extension<VeriqooTokens>()!;
    return Scaffold(
      backgroundColor: tokens.bg,
      appBar: const VeriqooAppBar(title: 'Report'),
      body: VeriqooBackdrop(
        background: const ComplianceMarkers(),
        child: SafeArea(
          child: SingleChildScrollView(
            padding: const EdgeInsets.all(VeriqooSpacing.s24),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                VeriqooSectionHeader(title: 'Report', subtitle: id),
                const SizedBox(height: VeriqooSpacing.s24),
                const Center(
                  child: VeriqooScore(value: 0, caption: 'SCORE'),
                ),
                const SizedBox(height: VeriqooSpacing.s24),
                const VeriqooStatus(kind: VeriqooStatusKind.missing),
                const SizedBox(height: VeriqooSpacing.s24),
                const VeriqooEmptyState(
                  icon: VeriqooIcons.verified,
                  title: 'Report coming soon',
                  message: 'The full compliance report lands in a later phase.',
                ),
              ],
            ),
          ),
        ),
      ),
    );
  }
}
