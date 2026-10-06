import 'package:flutter/material.dart';
import 'package:shared_core/design_system/design_system.dart';

/// The signature visual band: the [VerificationScan] motif sweeping over a
/// stylized monochrome package silhouette ([ProductOutline]).
///
/// It is purely decorative — wrapped in [IgnorePointer] and held at low
/// [Opacity] so it sits BELOW the foreground content hierarchy. Both layers are
/// design-system [BackgroundEffect]/motif widgets, so motion pauses
/// automatically under reduced motion and when offscreen.
class HomeSignatureScan extends StatelessWidget {
  const HomeSignatureScan({super.key, this.height = 180});

  /// Band height in logical pixels (~160–200 per the brief).
  final double height;

  @override
  Widget build(BuildContext context) {
    return IgnorePointer(
      child: SizedBox(
        height: height,
        width: double.infinity,
        child: const Opacity(
          opacity: 0.5,
          child: Stack(
            fit: StackFit.expand,
            children: [
              ProductOutline(),
              VerificationScan(),
            ],
          ),
        ),
      ),
    );
  }
}
