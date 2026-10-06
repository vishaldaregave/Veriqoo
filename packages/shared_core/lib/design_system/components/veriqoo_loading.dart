import 'package:flutter/material.dart';

import '../motif/verification_scan.dart';
import '../theme/veriqoo_spacing.dart';
import '../theme/veriqoo_tokens.dart';
import '../theme/veriqoo_typography.dart';

/// The VERIQOO loading state, built on the signature [VerificationScan] motif.
///
/// A bounded scan panel plays the hairline sweep / corner-lock / staggered OCR
/// box animation with an optional [message] beneath it. Reduced motion resolves
/// the motif to its static locked state.
class VeriqooLoading extends StatelessWidget {
  const VeriqooLoading({
    super.key,
    this.message = 'Verifying',
    this.size = const Size(220, 180),
  });

  /// Status line shown below the scan panel.
  final String message;

  /// Size of the scan panel.
  final Size size;

  @override
  Widget build(BuildContext context) {
    final tokens = Theme.of(context).extension<VeriqooTokens>()!;
    return Semantics(
      liveRegion: true,
      label: message,
      child: Column(
        mainAxisSize: MainAxisSize.min,
        children: [
          SizedBox(
            width: size.width,
            height: size.height,
            child: DecoratedBox(
              decoration: BoxDecoration(
                color: tokens.bgTrue,
                border: Border.all(color: tokens.borderHairline, width: 1),
              ),
              child: const VerificationScan(),
            ),
          ),
          const SizedBox(height: VeriqooSpacing.s16),
          Text(
            message.toUpperCase(),
            style: VeriqooType.meta.copyWith(color: tokens.textSecondary),
          ),
        ],
      ),
    );
  }
}
