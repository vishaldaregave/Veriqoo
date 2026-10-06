import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';
import 'package:shared_core/design_system/design_system.dart';

import 'package:flutter_application_1/app/routes.dart';
import 'package:flutter_application_1/features/home/home_strings.dart';

/// The primary/secondary action pair: SCAN PRODUCT (inverse fill) to `/scan`
/// and VIEW HISTORY (hairline outline) to `/history`.
class HomeActions extends StatelessWidget {
  const HomeActions({super.key});

  @override
  Widget build(BuildContext context) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      mainAxisSize: MainAxisSize.min,
      children: [
        VeriqooButton(
          label: HomeStrings.scanProduct,
          icon: VeriqooIcons.scan,
          size: VeriqooButtonSize.large,
          expand: true,
          onPressed: () => context.go(AppRoutes.scanPath),
        ),
        const SizedBox(height: VeriqooSpacing.s12),
        VeriqooButton(
          label: HomeStrings.viewHistory,
          variant: VeriqooButtonVariant.secondary,
          size: VeriqooButtonSize.large,
          expand: true,
          onPressed: () => context.go(AppRoutes.historyPath),
        ),
      ],
    );
  }
}
