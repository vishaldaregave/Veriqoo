import 'package:flutter/material.dart';
import 'package:qr_flutter/qr_flutter.dart';
import 'package:shared_core/design_system/design_system.dart';

import 'package:flutter_application_1/features/scan/result/result_strings.dart';

/// Key for the generated QR widget (used by widget tests).
const Key kReportQrImageKey = Key('report-qr-image');

/// Content for the "Generate QR" [VeriqooModal]: a monochrome QR encoding the
/// report reference/summary payload, plus the reference id in mono.
///
/// The QR is intentionally rendered dark-on-light (black modules on a white
/// quiet zone) regardless of theme — QR scanners expect that polarity, and an
/// inverted (light-on-dark) code is not reliably scannable. This stays within
/// the monochrome system (pure black/white only).
class ReportQrSheet extends StatelessWidget {
  const ReportQrSheet({super.key, required this.payload, required this.id});

  /// The encoded QR payload (see `ReportReference.qrPayload`).
  final String payload;

  /// The human-facing reference id shown beneath the code.
  final String id;

  @override
  Widget build(BuildContext context) {
    final tokens = Theme.of(context).extension<VeriqooTokens>()!;
    return Column(
      mainAxisSize: MainAxisSize.min,
      crossAxisAlignment: CrossAxisAlignment.center,
      children: [
        Container(
          color: Colors.white,
          padding: const EdgeInsets.all(VeriqooSpacing.s16),
          child: QrImageView(
            key: kReportQrImageKey,
            data: payload,
            size: 200,
            backgroundColor: Colors.white,
            eyeStyle: const QrEyeStyle(
              eyeShape: QrEyeShape.square,
              color: Colors.black,
            ),
            dataModuleStyle: const QrDataModuleStyle(
              dataModuleShape: QrDataModuleShape.square,
              color: Colors.black,
            ),
          ),
        ),
        const SizedBox(height: VeriqooSpacing.s16),
        Text(
          id,
          style: VeriqooType.mono.copyWith(
            color: tokens.textPrimary,
            fontSize: 16,
          ),
        ),
        const SizedBox(height: VeriqooSpacing.s8),
        Text(
          ResultStrings.qrHint,
          textAlign: TextAlign.center,
          style: VeriqooType.caption.copyWith(color: tokens.textSecondary),
        ),
      ],
    );
  }
}
