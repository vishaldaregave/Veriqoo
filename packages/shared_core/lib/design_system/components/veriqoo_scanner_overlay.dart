import 'package:flutter/material.dart';

import '../motif/verification_scan.dart';
import '../theme/veriqoo_spacing.dart';
import '../theme/veriqoo_tokens.dart';
import '../theme/veriqoo_typography.dart';

/// A full-bleed scanner overlay built on the [VerificationScan] motif.
///
/// Lays a scan treatment — four corner markers, a thin sweeping line, and
/// sample OCR detection boxes with tiny field labels — over an optional camera
/// preview [child]. An optional [hint] line is pinned near the bottom. Reduced
/// motion resolves the motif to its static locked state.
class VeriqooScannerOverlay extends StatelessWidget {
  const VeriqooScannerOverlay({
    super.key,
    this.child,
    this.hint = 'Align the label within the frame',
    this.enabled = true,
    this.fields = VerificationScan.defaultFields,
  });

  /// Optional live camera preview rendered beneath the overlay.
  final Widget? child;

  /// Guidance line shown near the bottom of the frame.
  final String? hint;

  /// When false the scan holds its static locked state (no sweep).
  final bool enabled;

  /// OCR field targets rendered as detection boxes.
  final List<ScanField> fields;

  @override
  Widget build(BuildContext context) {
    final tokens = Theme.of(context).extension<VeriqooTokens>()!;
    return Semantics(
      label: 'Scanner. ${hint ?? ''}'.trim(),
      child: ExcludeSemantics(
        child: Stack(
          fit: StackFit.expand,
          children: [
            ColoredBox(color: tokens.bgTrue),
            if (child != null) Positioned.fill(child: child!),
            Positioned.fill(
              child: VerificationScan(
                enabled: enabled,
                fields: fields,
                cornerLength: 28,
                sweepThickness: 2,
              ),
            ),
            if (hint != null)
              Positioned(
                left: VeriqooSpacing.s24,
                right: VeriqooSpacing.s24,
                bottom: VeriqooSpacing.s32,
                child: Center(
                  child: Container(
                    padding: const EdgeInsets.symmetric(
                      horizontal: VeriqooSpacing.s16,
                      vertical: VeriqooSpacing.s8,
                    ),
                    decoration: BoxDecoration(
                      color: tokens.surfaceRaised.withValues(alpha: 0.85),
                      border:
                          Border.all(color: tokens.borderHairline, width: 1),
                    ),
                    child: Text(
                      hint!.toUpperCase(),
                      textAlign: TextAlign.center,
                      style: VeriqooType.meta
                          .copyWith(color: tokens.textPrimary),
                    ),
                  ),
                ),
              ),
          ],
        ),
      ),
    );
  }
}
