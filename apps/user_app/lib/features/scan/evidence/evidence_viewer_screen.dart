import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:shared_core/design_system/design_system.dart';

import 'package:flutter_application_1/features/scan/evidence/evidence_viewer_args.dart';
import 'package:flutter_application_1/features/scan/evidence/widgets/evidence_image_view.dart';
import 'package:flutter_application_1/features/scan/model/evidence_image.dart';
import 'package:flutter_application_1/features/scan/result/report_finding.dart';
import 'package:flutter_application_1/features/scan/result/result_strings.dart';
import 'package:flutter_application_1/features/scan/scan_providers.dart';

/// Key for the "WHY THIS MATTERS" trigger (used by widget tests).
const Key kEvidenceWhyButtonKey = Key('evidence-why-button');

/// Key for an evidence selector tile (suffixed with the index).
Key evidenceTileKey(int index) => Key('evidence-tile-$index');

/// The interactive EVIDENCE VIEWER.
///
/// Shows the captured evidence image(s) from `scanState` with the DERIVED
/// live-detection boxes overlaid. Launched from a finding, it zooms toward the
/// best-effort linked region ([linkFinding]), marks the association DERIVED,
/// and offers a plain-language "WHY THIS MATTERS" explanation.
///
/// Evidence linking is best-effort: where the backend does not provide
/// per-issue coordinates, the finding is tied to the primary image/field and
/// the synthesized association is clearly labelled DERIVED — no backend-precise
/// bounding boxes are fabricated.
class EvidenceViewerScreen extends ConsumerStatefulWidget {
  const EvidenceViewerScreen({super.key, this.args = const EvidenceViewerArgs()});

  final EvidenceViewerArgs args;

  @override
  ConsumerState<EvidenceViewerScreen> createState() =>
      _EvidenceViewerScreenState();
}

class _EvidenceViewerScreenState extends ConsumerState<EvidenceViewerScreen> {
  late int _currentIndex = widget.args.initialImageIndex;

  @override
  Widget build(BuildContext context) {
    final tokens = Theme.of(context).extension<VeriqooTokens>()!;
    final scanState = ref.watch(scanStateProvider);
    final evidence = scanState.evidence;

    if (evidence.isEmpty) {
      return Scaffold(
        backgroundColor: tokens.bg,
        appBar: const VeriqooAppBar(title: ResultStrings.evidenceTitle),
        body: const SafeArea(
          child: VeriqooEmptyState(
            icon: VeriqooIcons.scan,
            title: ResultStrings.evidenceEmptyTitle,
            message: ResultStrings.evidenceEmptyMessage,
          ),
        ),
      );
    }

    final index = _currentIndex.clamp(0, evidence.length - 1);
    final current = evidence[index];
    final finding = widget.args.focusFinding;

    final EvidenceLink? link = finding == null
        ? null
        : linkFinding(
            finding,
            detectedFields: scanState.detectedFields,
            evidenceCount: evidence.length,
          );

    // The focus highlight applies only while viewing the linked image.
    final focusRect =
        (link != null && index == link.imageIndex) ? link.field?.rectNormalized : null;
    final showDerivedNote = link != null && index == link.imageIndex;

    return Scaffold(
      backgroundColor: tokens.bg,
      appBar: const VeriqooAppBar(title: ResultStrings.evidenceTitle),
      body: SafeArea(
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            Expanded(
              child: EvidenceImageView(
                key: ValueKey<String>(current.file.path),
                image: current,
                detectedFields: scanState.detectedFields,
                focusRect: focusRect,
              ),
            ),
            if (showDerivedNote)
              Padding(
                padding: const EdgeInsets.fromLTRB(
                  VeriqooSpacing.s24,
                  VeriqooSpacing.s12,
                  VeriqooSpacing.s24,
                  0,
                ),
                child: Row(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Icon(VeriqooIcons.shield, size: 12, color: tokens.textTertiary),
                    const SizedBox(width: VeriqooSpacing.s8),
                    Expanded(
                      child: Text(
                        ResultStrings.derivedNote,
                        style: VeriqooType.meta
                            .copyWith(color: tokens.textTertiary),
                      ),
                    ),
                  ],
                ),
              ),
            if (evidence.length > 1)
              _EvidenceSelector(
                evidence: evidence,
                currentIndex: index,
                onSelect: (i) => setState(() => _currentIndex = i),
              ),
            if (finding != null)
              Padding(
                padding: const EdgeInsets.all(VeriqooSpacing.s24),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.stretch,
                  children: [
                    Text(
                      '${finding.twoDigit} — ${_kindLabel(finding.kind)}',
                      style: VeriqooType.meta
                          .copyWith(color: tokens.textSecondary),
                    ),
                    const SizedBox(height: VeriqooSpacing.s4),
                    Text(
                      finding.title,
                      style: VeriqooType.body
                          .copyWith(color: tokens.textPrimary),
                    ),
                    const SizedBox(height: VeriqooSpacing.s16),
                    VeriqooButton(
                      key: kEvidenceWhyButtonKey,
                      label: ResultStrings.whyThisMattersAction,
                      variant: VeriqooButtonVariant.secondary,
                      icon: VeriqooIcons.shield,
                      expand: true,
                      onPressed: () => _showWhy(context, finding),
                    ),
                  ],
                ),
              ),
          ],
        ),
      ),
    );
  }

  String _kindLabel(ReportFindingKind kind) {
    switch (kind) {
      case ReportFindingKind.missingDeclaration:
        return ResultStrings.findingMissingDeclaration;
      case ReportFindingKind.potentialViolation:
        return ResultStrings.findingPotentialViolation;
    }
  }

  Future<void> _showWhy(BuildContext context, ReportFinding finding) {
    return VeriqooBottomSheet.show<void>(
      context,
      title: ResultStrings.whyThisMatters,
      isScrollControlled: true,
      child: _WhyThisMattersBody(finding: finding),
    );
  }
}

/// Plain-language explanation for a finding, built from the available data.
class _WhyThisMattersBody extends StatelessWidget {
  const _WhyThisMattersBody({required this.finding});

  final ReportFinding finding;

  @override
  Widget build(BuildContext context) {
    final tokens = Theme.of(context).extension<VeriqooTokens>()!;
    final issue = finding.issue;
    final ruleTitles =
        issue?.ruleTitles.where((r) => r.trim().isNotEmpty).toList() ??
            const <String>[];
    final ruleNumbers =
        issue?.ruleNumbers.where((r) => r.trim().isNotEmpty).toList() ??
            const <String>[];

    return SingleChildScrollView(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        mainAxisSize: MainAxisSize.min,
        children: [
          VeriqooStatus(kind: finding.status),
          const SizedBox(height: VeriqooSpacing.s16),
          Text(
            _explanation(finding),
            style: VeriqooType.body.copyWith(color: tokens.textPrimary),
          ),
          if (ruleNumbers.isNotEmpty || ruleTitles.isNotEmpty) ...[
            const SizedBox(height: VeriqooSpacing.s16),
            Text(
              'LEGAL REFERENCE',
              style: VeriqooType.meta.copyWith(color: tokens.textSecondary),
            ),
            const SizedBox(height: VeriqooSpacing.s4),
            if (ruleNumbers.isNotEmpty)
              Text(
                ruleNumbers.join(', '),
                style: VeriqooType.mono.copyWith(color: tokens.textPrimary),
              ),
            if (ruleTitles.isNotEmpty) ...[
              const SizedBox(height: VeriqooSpacing.s4),
              Text(
                ruleTitles.join('\n'),
                style:
                    VeriqooType.caption.copyWith(color: tokens.textSecondary),
              ),
            ],
          ],
          const SizedBox(height: VeriqooSpacing.s16),
          Row(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Icon(VeriqooIcons.shield, size: 12, color: tokens.textTertiary),
              const SizedBox(width: VeriqooSpacing.s8),
              Expanded(
                child: Text(
                  ResultStrings.derivedNote,
                  style: VeriqooType.meta.copyWith(color: tokens.textTertiary),
                ),
              ),
            ],
          ),
        ],
      ),
    );
  }

  String _explanation(ReportFinding finding) {
    if (finding.kind == ReportFindingKind.missingDeclaration) {
      return ResultStrings.whyMissingDeclaration(
        finding.missingField ?? finding.title,
      );
    }
    final issue = finding.issue;
    if (issue != null) {
      final parts = <String>[];
      if (issue.description.trim().isNotEmpty) {
        parts.add(issue.description.trim());
      }
      final legalBasis = issue.legalBasis?.trim() ?? '';
      if (legalBasis.isNotEmpty) {
        parts.add(legalBasis);
      }
      if (parts.isNotEmpty) {
        return parts.join('\n\n');
      }
    }
    return ResultStrings.whyGenericViolation;
  }
}

/// A thin horizontal strip of numbered evidence tiles for multi-image sets.
class _EvidenceSelector extends StatelessWidget {
  const _EvidenceSelector({
    required this.evidence,
    required this.currentIndex,
    required this.onSelect,
  });

  final List<EvidenceImage> evidence;
  final int currentIndex;
  final ValueChanged<int> onSelect;

  @override
  Widget build(BuildContext context) {
    final tokens = Theme.of(context).extension<VeriqooTokens>()!;
    return SizedBox(
      height: 56,
      child: ListView.separated(
        scrollDirection: Axis.horizontal,
        padding: const EdgeInsets.symmetric(horizontal: VeriqooSpacing.s24),
        itemCount: evidence.length,
        separatorBuilder: (_, __) => const SizedBox(width: VeriqooSpacing.s8),
        itemBuilder: (context, i) {
          final selected = i == currentIndex;
          final image = evidence[i];
          return Semantics(
            button: true,
            selected: selected,
            label: 'Evidence ${image.twoDigit} ${image.label}',
            child: GestureDetector(
              key: evidenceTileKey(i),
              behavior: HitTestBehavior.opaque,
              onTap: () => onSelect(i),
              child: Container(
                alignment: Alignment.center,
                padding: const EdgeInsets.symmetric(
                  horizontal: VeriqooSpacing.s16,
                ),
                decoration: BoxDecoration(
                  color: selected ? tokens.inverseBg : Colors.transparent,
                  border: Border.all(
                    color: selected ? tokens.borderStrong : tokens.borderHairline,
                    width: 1,
                  ),
                ),
                child: Column(
                  mainAxisAlignment: MainAxisAlignment.center,
                  children: [
                    Text(
                      image.twoDigit,
                      style: VeriqooType.mono.copyWith(
                        color: selected ? tokens.inverseText : tokens.textPrimary,
                      ),
                    ),
                    Text(
                      image.label.toUpperCase(),
                      style: VeriqooType.meta.copyWith(
                        color: selected
                            ? tokens.inverseText
                            : tokens.textSecondary,
                        fontSize: 9,
                      ),
                    ),
                  ],
                ),
              ),
            ),
          );
        },
      ),
    );
  }
}
