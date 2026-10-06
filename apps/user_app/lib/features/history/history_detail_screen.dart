import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:shared_core/design_system/design_system.dart';

import 'package:flutter_application_1/core/widgets/app_background.dart';
import 'package:flutter_application_1/features/history/history_strings.dart';
import 'package:flutter_application_1/features/inspections/inspection_detail.dart';
import 'package:flutter_application_1/features/inspections/inspections_providers.dart';
import 'package:flutter_application_1/features/scan/result/compliance_score.dart';
import 'package:flutter_application_1/features/scan/result/report_finding.dart';
import 'package:flutter_application_1/features/scan/result/widgets/product_details_panel.dart';
import 'package:flutter_application_1/features/scan/result/widgets/report_finding_tile.dart';

/// Read-only INSPECTION DETAIL (`/history/:id`). Fetches the saved inspection,
/// reconstructs the [InspectionDetail] (analysis from `ai_report`), and renders
/// the Phase 6 report widgets — score dial, product-details panel, numbered
/// findings — WITHOUT a Save action (viewing never re-persists).
class HistoryDetailScreen extends ConsumerWidget {
  const HistoryDetailScreen({super.key, required this.id});

  final String id;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final tokens = Theme.of(context).extension<VeriqooTokens>()!;
    final async = ref.watch(inspectionDetailProvider(id));

    return Scaffold(
      backgroundColor: tokens.bg,
      appBar: const VeriqooAppBar(title: HistoryStrings.inspectionTitle),
      body: VeriqooBackdrop(
        background: const ProductOutline(),
        child: SafeArea(
          child: async.when(
            loading: () =>
                const Center(child: VeriqooLoading(message: 'Loading')),
            error: (_, __) => VeriqooErrorState(
              title: HistoryStrings.detailErrorTitle,
              message: HistoryStrings.detailErrorMessage,
              onRetry: () => ref.invalidate(inspectionDetailProvider(id)),
            ),
            data: (detail) {
              if (detail == null) {
                return const VeriqooEmptyState(
                  icon: VeriqooIcons.history,
                  title: HistoryStrings.notFoundTitle,
                  message: HistoryStrings.notFoundMessage,
                );
              }
              return _DetailBody(detail: detail);
            },
          ),
        ),
      ),
    );
  }
}

class _DetailBody extends StatelessWidget {
  const _DetailBody({required this.detail});

  final InspectionDetail detail;

  @override
  Widget build(BuildContext context) {
    final tokens = Theme.of(context).extension<VeriqooTokens>()!;
    final analysis = detail.analysis;
    final record = detail.record;
    final score = ComplianceScore.fromAnalysis(analysis);
    final findings = ReportFinding.fromAnalysis(analysis);
    final productName = analysis.productName.isNotEmpty
        ? analysis.productName
        : record.productName;

    return Center(
      child: ConstrainedBox(
        constraints: const BoxConstraints(maxWidth: 640),
        child: SingleChildScrollView(
          padding: const EdgeInsets.fromLTRB(
            VeriqooSpacing.s24,
            VeriqooSpacing.s8,
            VeriqooSpacing.s24,
            VeriqooSpacing.s32,
          ),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              Text(
                record.displayId,
                style: VeriqooType.mono.copyWith(color: tokens.textSecondary),
              ),
              const SizedBox(height: VeriqooSpacing.s4),
              Text(
                productName,
                style: VeriqooType.body.copyWith(
                  color: tokens.textPrimary,
                  fontSize: 24,
                  fontWeight: FontWeight.w700,
                  height: 1.1,
                ),
              ),
              const SizedBox(height: VeriqooSpacing.s4),
              Text(
                record.timestampLabel,
                style: VeriqooType.meta.copyWith(color: tokens.textTertiary),
              ),
              const SizedBox(height: VeriqooSpacing.s24),
              Center(
                child: VeriqooScore(value: score.score, caption: 'COMPLIANCE'),
              ),
              const SizedBox(height: VeriqooSpacing.s24),
              _Summary(score: score),
              const SizedBox(height: VeriqooSpacing.s24),
              const VeriqooDivider(),
              const SizedBox(height: VeriqooSpacing.s16),
              ProductDetailsPanel(analysis: analysis),
              if (findings.isNotEmpty) ...[
                const SizedBox(height: VeriqooSpacing.s24),
                const VeriqooSectionHeader(title: 'FINDINGS'),
                for (final finding in findings)
                  ReportFindingTile(
                    finding: finding,
                    onInspect: () => _showWhy(context, finding),
                  ),
              ],
              if (detail.imageUrl != null) ...[
                const SizedBox(height: VeriqooSpacing.s24),
                const VeriqooSectionHeader(title: HistoryStrings.capturedImage),
                const SizedBox(height: VeriqooSpacing.s12),
                _Evidence(url: detail.imageUrl!),
              ],
            ],
          ),
        ),
      ),
    );
  }

  void _showWhy(BuildContext context, ReportFinding finding) {
    final tokens = Theme.of(context).extension<VeriqooTokens>()!;
    VeriqooBottomSheet.show<void>(
      context,
      title: finding.title,
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        mainAxisSize: MainAxisSize.min,
        children: [
          VeriqooStatus(kind: finding.status),
          const SizedBox(height: VeriqooSpacing.s16),
          Text(
            finding.detail ?? finding.title,
            style: VeriqooType.body.copyWith(color: tokens.textSecondary),
          ),
          if (finding.issue != null &&
              finding.issue!.ruleTitles.isNotEmpty) ...[
            const SizedBox(height: VeriqooSpacing.s16),
            for (final rule in finding.issue!.ruleTitles)
              Padding(
                padding: const EdgeInsets.only(bottom: VeriqooSpacing.s8),
                child: Text(
                  '• $rule',
                  style: VeriqooType.caption
                      .copyWith(color: tokens.textTertiary),
                ),
              ),
          ],
        ],
      ),
    );
  }
}

class _Summary extends StatelessWidget {
  const _Summary({required this.score});

  final ComplianceScore score;

  @override
  Widget build(BuildContext context) {
    return Row(
      children: [
        Expanded(
          child: _metric(
            context,
            '${score.verified}/${score.mandatoryTotal}',
            'VERIFIED',
          ),
        ),
        Expanded(child: _metric(context, '${score.flagged}', 'FLAGGED')),
        Expanded(child: _metric(context, '${score.missing}', 'MISSING')),
      ],
    );
  }

  Widget _metric(BuildContext context, String value, String label) {
    final tokens = Theme.of(context).extension<VeriqooTokens>()!;
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text(
          value,
          style: VeriqooType.mono
              .copyWith(color: tokens.textPrimary, fontSize: 20),
        ),
        const SizedBox(height: VeriqooSpacing.s4),
        Text(
          label,
          style: VeriqooType.meta.copyWith(color: tokens.textSecondary),
        ),
      ],
    );
  }
}

class _Evidence extends StatelessWidget {
  const _Evidence({required this.url});

  final String url;

  @override
  Widget build(BuildContext context) {
    final tokens = Theme.of(context).extension<VeriqooTokens>()!;
    return ClipRRect(
      borderRadius: BorderRadius.circular(6),
      child: ConstrainedBox(
        constraints: const BoxConstraints(maxHeight: 320),
        child: Image.network(
          url,
          fit: BoxFit.cover,
          width: double.infinity,
          loadingBuilder: (context, child, progress) {
            if (progress == null) {
              return child;
            }
            return const SizedBox(
              height: 180,
              child: Center(
                child: VeriqooLoading(
                  message: 'Loading',
                  size: Size(160, 120),
                ),
              ),
            );
          },
          errorBuilder: (context, _, __) => Container(
            height: 180,
            alignment: Alignment.center,
            color: tokens.surface,
            child: Text(
              HistoryStrings.imageUnavailable,
              style: VeriqooType.caption.copyWith(color: tokens.textTertiary),
            ),
          ),
        ),
      ),
    );
  }
}
