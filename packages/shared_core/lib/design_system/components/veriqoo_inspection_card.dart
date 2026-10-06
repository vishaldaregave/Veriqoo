import 'package:flutter/material.dart';

import '../foundations/veriqoo_icons.dart';
import '../theme/veriqoo_spacing.dart';
import '../theme/veriqoo_tokens.dart';
import '../theme/veriqoo_typography.dart';
import 'veriqoo_status.dart';

/// An editorial LEDGER ROW for an inspection record — deliberately NOT a
/// floating rounded card.
///
/// Lays out the inspection ID and timestamp in mono tabular figures, the
/// product name in body text, the numeric score in mono, and a [VeriqooStatus]
/// chip. Rows separate with hairlines and use radius [none] so a list reads as
/// a technical register. Tapping (when [onTap] is set) is a 44px-min target
/// with a Semantics summary.
class VeriqooInspectionCard extends StatefulWidget {
  const VeriqooInspectionCard({
    super.key,
    required this.inspectionId,
    required this.timestamp,
    required this.product,
    required this.score,
    required this.status,
    this.maxScore = 100,
    this.onTap,
  });

  /// Inspection identifier, e.g. `VRQ-20261004-0182` (rendered in mono).
  final String inspectionId;

  /// Human-readable timestamp (rendered in mono).
  final String timestamp;

  /// Product name.
  final String product;

  /// Numeric compliance score.
  final int score;

  /// Score denominator.
  final int maxScore;

  /// Verification outcome chip.
  final VeriqooStatusKind status;

  /// Optional tap handler for opening the full record.
  final VoidCallback? onTap;

  @override
  State<VeriqooInspectionCard> createState() => _VeriqooInspectionCardState();
}

class _VeriqooInspectionCardState extends State<VeriqooInspectionCard> {
  bool _focused = false;

  @override
  Widget build(BuildContext context) {
    final tokens = Theme.of(context).extension<VeriqooTokens>()!;

    final row = Container(
      constraints: const BoxConstraints(minHeight: 44),
      padding: const EdgeInsets.symmetric(
        vertical: VeriqooSpacing.s16,
        horizontal: VeriqooSpacing.s4,
      ),
      decoration: BoxDecoration(
        border: Border(
          bottom: BorderSide(color: tokens.borderHairline, width: 1),
        ),
      ),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              mainAxisSize: MainAxisSize.min,
              children: [
                Row(
                  children: [
                    Flexible(
                      child: Text(
                        widget.inspectionId,
                        overflow: TextOverflow.ellipsis,
                        style: VeriqooType.mono
                            .copyWith(color: tokens.textSecondary),
                      ),
                    ),
                    const SizedBox(width: VeriqooSpacing.s8),
                    Text(
                      widget.timestamp,
                      style: VeriqooType.mono.copyWith(
                        color: tokens.textTertiary,
                        fontSize: 11,
                      ),
                    ),
                  ],
                ),
                const SizedBox(height: VeriqooSpacing.s4),
                Text(
                  widget.product,
                  maxLines: 1,
                  overflow: TextOverflow.ellipsis,
                  style: VeriqooType.bodyL.copyWith(
                    color: tokens.textPrimary,
                    fontWeight: FontWeight.w600,
                  ),
                ),
                const SizedBox(height: VeriqooSpacing.s8),
                VeriqooStatus(kind: widget.status),
              ],
            ),
          ),
          const SizedBox(width: VeriqooSpacing.s16),
          // Score column (mono, tabular).
          Column(
            crossAxisAlignment: CrossAxisAlignment.end,
            mainAxisSize: MainAxisSize.min,
            children: [
              Text(
                '${widget.score}/${widget.maxScore}',
                style: VeriqooType.mono.copyWith(
                  color: tokens.textPrimary,
                  fontSize: 16,
                  fontWeight: FontWeight.w500,
                ),
              ),
              if (widget.onTap != null) ...[
                const SizedBox(height: VeriqooSpacing.s8),
                Icon(
                  VeriqooIcons.chevronRight,
                  size: 18,
                  color: tokens.textSecondary,
                ),
              ],
            ],
          ),
        ],
      ),
    );

    final semanticsLabel =
        '${widget.product}, inspection ${widget.inspectionId}, '
        'score ${widget.score} of ${widget.maxScore}, ${widget.status.label}';

    if (widget.onTap == null) {
      return Semantics(
        label: semanticsLabel,
        child: ExcludeSemantics(child: row),
      );
    }

    return Semantics(
      button: true,
      label: semanticsLabel,
      child: ExcludeSemantics(
        child: GestureDetector(
          behavior: HitTestBehavior.opaque,
          onTap: widget.onTap,
          child: FocusableActionDetector(
            onShowFocusHighlight: (v) => setState(() => _focused = v),
            actions: <Type, Action<Intent>>{
              ActivateIntent: CallbackAction<ActivateIntent>(
                onInvoke: (_) {
                  widget.onTap?.call();
                  return null;
                },
              ),
            },
            child: DecoratedBox(
              decoration: BoxDecoration(
                border: Border.all(
                  color: _focused ? tokens.textPrimary : Colors.transparent,
                  width: 2,
                ),
              ),
              child: row,
            ),
          ),
        ),
      ),
    );
  }
}
