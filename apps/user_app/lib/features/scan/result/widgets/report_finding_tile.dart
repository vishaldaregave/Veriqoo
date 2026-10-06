import 'package:flutter/material.dart';
import 'package:shared_core/design_system/design_system.dart';

import 'package:flutter_application_1/features/scan/result/report_finding.dart';
import 'package:flutter_application_1/features/scan/result/result_strings.dart';

/// Key for a finding tile's inspect/view-evidence action (suffixed with the
/// finding number).
Key reportFindingActionKey(int number) => Key('report-finding-action-$number');

/// One numbered inspection finding, rendered as strong editorial typography on
/// hairline dividers — deliberately NOT a generic red "error card".
///
/// Shows a large mono ordinal, the category label
/// (MISSING DECLARATION / POTENTIAL VIOLATION), the [VeriqooStatus] marker, the
/// finding title/detail, and a ghost action (View evidence / Inspect) that
/// invokes [onInspect].
class ReportFindingTile extends StatelessWidget {
  const ReportFindingTile({
    super.key,
    required this.finding,
    required this.onInspect,
  });

  final ReportFinding finding;
  final VoidCallback onInspect;

  @override
  Widget build(BuildContext context) {
    final tokens = Theme.of(context).extension<VeriqooTokens>()!;
    final isMissing = finding.kind == ReportFindingKind.missingDeclaration;
    final kindLabel = isMissing
        ? ResultStrings.findingMissingDeclaration
        : ResultStrings.findingPotentialViolation;
    final actionLabel =
        isMissing ? ResultStrings.viewEvidence : ResultStrings.inspect;
    final actionIcon = isMissing ? VeriqooIcons.eye : VeriqooIcons.zoomIn;

    return Padding(
      padding: const EdgeInsets.symmetric(vertical: VeriqooSpacing.s16),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          SizedBox(
            width: 40,
            child: Text(
              finding.twoDigit,
              style: VeriqooType.mono.copyWith(
                color: tokens.textTertiary,
                fontSize: 22,
              ),
            ),
          ),
          const SizedBox(width: VeriqooSpacing.s12),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Row(
                  children: [
                    Expanded(
                      child: Text(
                        kindLabel,
                        style: VeriqooType.meta
                            .copyWith(color: tokens.textSecondary),
                      ),
                    ),
                    const SizedBox(width: VeriqooSpacing.s8),
                    VeriqooStatus(kind: finding.status, markerSize: 14),
                  ],
                ),
                const SizedBox(height: VeriqooSpacing.s8),
                Text(
                  finding.title,
                  style: VeriqooType.body.copyWith(
                    color: tokens.textPrimary,
                    fontWeight: FontWeight.w600,
                  ),
                ),
                if (finding.detail != null) ...[
                  const SizedBox(height: VeriqooSpacing.s4),
                  Text(
                    finding.detail!,
                    style: VeriqooType.caption
                        .copyWith(color: tokens.textSecondary),
                  ),
                ],
                const SizedBox(height: VeriqooSpacing.s8),
                Align(
                  alignment: Alignment.centerLeft,
                  child: VeriqooButton(
                    key: reportFindingActionKey(finding.number),
                    label: actionLabel,
                    variant: VeriqooButtonVariant.ghost,
                    size: VeriqooButtonSize.small,
                    icon: actionIcon,
                    onPressed: onInspect,
                  ),
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }
}
