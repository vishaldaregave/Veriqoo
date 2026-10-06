import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';
import 'package:shared_core/design_system/design_system.dart';

import 'package:flutter_application_1/app/routes.dart';
import 'package:flutter_application_1/features/home/home_strings.dart';

/// The intelligent empty state for the recent section: the editorial message
/// with a SCAN A PRODUCT action, layered over a subtle product-outline +
/// scan-line visual. The background is decorative only (IgnorePointer, low
/// opacity) and pauses under reduced motion.
class HomeRecentEmpty extends StatelessWidget {
  const HomeRecentEmpty({super.key, this.height = 340});

  final double height;

  @override
  Widget build(BuildContext context) {
    return SizedBox(
      height: height,
      child: Stack(
        children: [
          const Positioned.fill(
            child: IgnorePointer(
              child: Opacity(
                opacity: 0.5,
                child: Stack(
                  fit: StackFit.expand,
                  children: [
                    ProductOutline(),
                    ScanningLine(),
                  ],
                ),
              ),
            ),
          ),
          Positioned.fill(
            child: VeriqooEmptyState(
              icon: VeriqooIcons.history,
              title: HomeStrings.emptyTitle,
              message: HomeStrings.emptyMessage,
              action: VeriqooButton(
                label: HomeStrings.scanAProduct,
                icon: VeriqooIcons.scan,
                onPressed: () => context.go(AppRoutes.scanPath),
              ),
            ),
          ),
        ],
      ),
    );
  }
}
