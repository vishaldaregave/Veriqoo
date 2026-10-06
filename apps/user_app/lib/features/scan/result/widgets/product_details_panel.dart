import 'package:flutter/material.dart';
import 'package:shared_core/design_system/design_system.dart';
import 'package:shared_core/services/compliance_analysis.dart';

import 'package:flutter_application_1/features/scan/result/result_strings.dart';

/// The technical product-details panel: six sharp HAIRLINE rows (no rounded
/// cards, no shadows) separated by [VeriqooDivider]s.
///
/// Each row shows an uppercase meta label and its value; MRP uses the mono
/// (tabular) style. Empty values render [ResultStrings.notDetected] in the
/// tertiary tone so a gap reads as "not detected", not as a blank.
class ProductDetailsPanel extends StatelessWidget {
  const ProductDetailsPanel({super.key, required this.analysis});

  final ComplianceAnalysis analysis;

  @override
  Widget build(BuildContext context) {
    final rows = <_Detail>[
      _Detail(ResultStrings.labelMrp, analysis.mrp, mono: true),
      _Detail(ResultStrings.labelNetQuantity, analysis.netQuantity),
      _Detail(ResultStrings.labelManufacturer, analysis.manufacturer),
      _Detail(ResultStrings.labelAddress, analysis.address),
      _Detail(ResultStrings.labelPackingDate, analysis.packingDate),
      _Detail(ResultStrings.labelCustomerCare, analysis.customerCare),
    ];

    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        for (var i = 0; i < rows.length; i++) ...[
          if (i > 0) const VeriqooDivider(),
          _DetailRow(detail: rows[i]),
        ],
      ],
    );
  }
}

class _Detail {
  const _Detail(this.label, this.value, {this.mono = false});

  final String label;
  final String value;
  final bool mono;
}

class _DetailRow extends StatelessWidget {
  const _DetailRow({required this.detail});

  final _Detail detail;

  @override
  Widget build(BuildContext context) {
    final tokens = Theme.of(context).extension<VeriqooTokens>()!;
    final hasValue = detail.value.trim().isNotEmpty;
    final display = hasValue ? detail.value.trim() : ResultStrings.notDetected;
    final baseStyle = detail.mono ? VeriqooType.mono : VeriqooType.body;

    return Padding(
      padding: const EdgeInsets.symmetric(vertical: VeriqooSpacing.s12),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          SizedBox(
            width: 116,
            child: Text(
              detail.label,
              style: VeriqooType.meta.copyWith(color: tokens.textSecondary),
            ),
          ),
          const SizedBox(width: VeriqooSpacing.s12),
          Expanded(
            child: Text(
              display,
              style: baseStyle.copyWith(
                color: hasValue ? tokens.textPrimary : tokens.textTertiary,
              ),
            ),
          ),
        ],
      ),
    );
  }
}
