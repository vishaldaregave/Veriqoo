import 'package:flutter/material.dart';
import 'package:shared_core/design_system/design_system.dart';

import 'package:flutter_application_1/features/history/history_strings.dart';
import 'package:flutter_application_1/features/inspections/inspection_query.dart';

/// Shows the combined FILTER & SORT sheet and resolves to the chosen
/// [InspectionQuery] (preserving the incoming free-text), or null if dismissed.
Future<InspectionQuery?> showHistoryFilterSheet(
  BuildContext context,
  InspectionQuery current,
) {
  return VeriqooBottomSheet.show<InspectionQuery>(
    context,
    title: HistoryStrings.filterTitle,
    isScrollControlled: true,
    child: _HistoryFilterSheet(current: current),
  );
}

class _HistoryFilterSheet extends StatefulWidget {
  const _HistoryFilterSheet({required this.current});

  final InspectionQuery current;

  @override
  State<_HistoryFilterSheet> createState() => _HistoryFilterSheetState();
}

class _HistoryFilterSheetState extends State<_HistoryFilterSheet> {
  late InspectionStatusFilter _status;
  late InspectionSortOrder _sort;

  static const Map<InspectionStatusFilter, String> _statusLabels = {
    InspectionStatusFilter.all: HistoryStrings.statusAll,
    InspectionStatusFilter.verified: HistoryStrings.statusVerified,
    InspectionStatusFilter.flag: HistoryStrings.statusFlagged,
    InspectionStatusFilter.missing: HistoryStrings.statusMissing,
    InspectionStatusFilter.violation: HistoryStrings.statusViolation,
  };

  static const Map<InspectionSortOrder, String> _sortLabels = {
    InspectionSortOrder.newest: HistoryStrings.sortNewest,
    InspectionSortOrder.oldest: HistoryStrings.sortOldest,
    InspectionSortOrder.scoreHigh: HistoryStrings.sortScoreHigh,
    InspectionSortOrder.scoreLow: HistoryStrings.sortScoreLow,
  };

  @override
  void initState() {
    super.initState();
    _status = widget.current.status;
    _sort = widget.current.sort;
  }

  @override
  Widget build(BuildContext context) {
    final tokens = Theme.of(context).extension<VeriqooTokens>()!;
    return Column(
      mainAxisSize: MainAxisSize.min,
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        Text(
          HistoryStrings.filterStatus,
          style: VeriqooType.meta.copyWith(color: tokens.textSecondary),
        ),
        const SizedBox(height: VeriqooSpacing.s8),
        for (final entry in _statusLabels.entries)
          _choiceRow(
            tokens: tokens,
            label: entry.value,
            selected: _status == entry.key,
            onTap: () => setState(() => _status = entry.key),
          ),
        const SizedBox(height: VeriqooSpacing.s24),
        Text(
          HistoryStrings.sortOrder,
          style: VeriqooType.meta.copyWith(color: tokens.textSecondary),
        ),
        const SizedBox(height: VeriqooSpacing.s8),
        for (final entry in _sortLabels.entries)
          _choiceRow(
            tokens: tokens,
            label: entry.value,
            selected: _sort == entry.key,
            onTap: () => setState(() => _sort = entry.key),
          ),
        const SizedBox(height: VeriqooSpacing.s24),
        Row(
          children: [
            Expanded(
              child: VeriqooButton(
                label: HistoryStrings.reset,
                variant: VeriqooButtonVariant.ghost,
                expand: true,
                onPressed: () =>
                    Navigator.of(context).pop(const InspectionQuery()),
              ),
            ),
            const SizedBox(width: VeriqooSpacing.s12),
            Expanded(
              child: VeriqooButton(
                label: HistoryStrings.apply,
                expand: true,
                onPressed: () => Navigator.of(context).pop(
                  widget.current.copyWith(status: _status, sort: _sort),
                ),
              ),
            ),
          ],
        ),
      ],
    );
  }

  Widget _choiceRow({
    required VeriqooTokens tokens,
    required String label,
    required bool selected,
    required VoidCallback onTap,
  }) {
    return InkWell(
      onTap: onTap,
      child: Padding(
        padding: const EdgeInsets.symmetric(vertical: VeriqooSpacing.s12),
        child: Row(
          children: [
            Expanded(
              child: Text(
                label,
                style: VeriqooType.body.copyWith(
                  color: selected ? tokens.textPrimary : tokens.textSecondary,
                  fontWeight: selected ? FontWeight.w600 : FontWeight.w400,
                ),
              ),
            ),
            if (selected)
              Icon(VeriqooIcons.check, size: 18, color: tokens.textPrimary),
          ],
        ),
      ),
    );
  }
}
