import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';
import 'package:shared_core/design_system/design_system.dart';

import 'package:flutter_application_1/app/routes.dart';
import 'package:flutter_application_1/features/home/home_strings.dart';
import 'package:flutter_application_1/features/inspections/inspection_record.dart';

/// The RECENT INSPECTIONS section: a [VeriqooSectionHeader] with a ghost
/// "View all" action over up to five [VeriqooInspectionCard] ledger rows, each
/// tappable through to its detail record.
///
/// When [entrance] is supplied the rows fade + rise in with a subtle per-row
/// stagger. A controller pinned at `1` (reduced motion) resolves to the static
/// shown state with no motion.
class HomeRecentList extends StatelessWidget {
  const HomeRecentList({super.key, required this.records, this.entrance});

  final List<InspectionRecord> records;
  final Animation<double>? entrance;

  @override
  Widget build(BuildContext context) {
    final visible = records.take(5).toList(growable: false);

    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      mainAxisSize: MainAxisSize.min,
      children: [
        VeriqooSectionHeader(
          title: HomeStrings.recentInspections,
          action: VeriqooButton(
            label: HomeStrings.viewAll,
            variant: VeriqooButtonVariant.ghost,
            size: VeriqooButtonSize.small,
            onPressed: () => context.go(AppRoutes.historyPath),
          ),
        ),
        for (var i = 0; i < visible.length; i++)
          _StaggeredRow(
            animation: entrance,
            index: i,
            count: visible.length,
            child: VeriqooInspectionCard(
              inspectionId: visible[i].displayId,
              timestamp: visible[i].timestampLabel,
              product: visible[i].productName,
              score: visible[i].score,
              status: visible[i].status,
              onTap: () => context.go(AppRoutes.historyDetail(visible[i].id)),
            ),
          ),
      ],
    );
  }
}

/// Fades + rises [child] in across a per-row slice of [animation]. With a null
/// animation (or one already at its end) the child renders fully shown.
class _StaggeredRow extends StatelessWidget {
  const _StaggeredRow({
    required this.animation,
    required this.index,
    required this.count,
    required this.child,
  });

  final Animation<double>? animation;
  final int index;
  final int count;
  final Widget child;

  @override
  Widget build(BuildContext context) {
    final anim = animation;
    if (anim == null) {
      return child;
    }

    // Rows occupy the back half of the entrance; each starts a little later.
    final step = count <= 1 ? 0.0 : 0.4 / (count - 1);
    final start = 0.5 + index * step;
    const window = 0.2;

    return AnimatedBuilder(
      animation: anim,
      child: child,
      builder: (context, child) {
        final t = _slice(anim.value, start, start + window);
        return Opacity(
          opacity: t,
          child: Transform.translate(
            offset: Offset(0, (1 - t) * 12),
            child: child,
          ),
        );
      },
    );
  }

  double _slice(double value, double start, double end) {
    if (value <= start) {
      return 0;
    }
    if (value >= end) {
      return 1;
    }
    return VeriqooMotion.enter.transform((value - start) / (end - start));
  }
}
