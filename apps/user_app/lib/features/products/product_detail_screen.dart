import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:shared_core/design_system/design_system.dart';

import 'package:flutter_application_1/app/routes.dart';
import 'package:flutter_application_1/core/widgets/app_background.dart';
import 'package:flutter_application_1/features/history/history_strings.dart';
import 'package:flutter_application_1/features/inspections/inspections_providers.dart';
import 'package:flutter_application_1/features/inspections/product_summary.dart';

/// PRODUCT DETAIL (`/products/:id`). The id is a DERIVED product key
/// (`p-<hex>`): there is no backend product entity, so this view is synthesized
/// by grouping the inspection corpus by normalized product name (D8) and is
/// clearly labelled DERIVED.
class ProductDetailScreen extends ConsumerWidget {
  const ProductDetailScreen({super.key, required this.id});

  final String id;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final tokens = Theme.of(context).extension<VeriqooTokens>()!;
    final async = ref.watch(allInspectionsProvider);

    return Scaffold(
      backgroundColor: tokens.bg,
      appBar: const VeriqooAppBar(title: HistoryStrings.productTitle),
      body: VeriqooBackdrop(
        background: const ProductOutline(),
        child: SafeArea(
          child: async.when(
            loading: () =>
                const Center(child: VeriqooLoading(message: 'Loading')),
            error: (_, __) => VeriqooErrorState(
              title: HistoryStrings.errorTitle,
              message: HistoryStrings.errorMessage,
              onRetry: () => ref.invalidate(allInspectionsProvider),
            ),
            data: (all) {
              final product = findProduct(deriveProducts(all), id);
              if (product == null) {
                return const VeriqooEmptyState(
                  icon: VeriqooIcons.package,
                  title: HistoryStrings.productNotFoundTitle,
                  message: HistoryStrings.productNotFoundMessage,
                );
              }
              return _ProductBody(product: product);
            },
          ),
        ),
      ),
    );
  }
}

class _ProductBody extends StatelessWidget {
  const _ProductBody({required this.product});

  final ProductSummary product;

  @override
  Widget build(BuildContext context) {
    final tokens = Theme.of(context).extension<VeriqooTokens>()!;
    return Center(
      child: ConstrainedBox(
        constraints: const BoxConstraints(maxWidth: 640),
        child: ListView(
          padding: const EdgeInsets.fromLTRB(
            VeriqooSpacing.s24,
            VeriqooSpacing.s8,
            VeriqooSpacing.s24,
            VeriqooSpacing.s32,
          ),
          children: [
            Text(
              product.productName,
              style: VeriqooType.body.copyWith(
                color: tokens.textPrimary,
                fontSize: 24,
                fontWeight: FontWeight.w700,
                height: 1.1,
              ),
            ),
            const SizedBox(height: VeriqooSpacing.s4),
            Text(
              HistoryStrings.inspectionsCount(product.inspectionCount),
              style: VeriqooType.meta.copyWith(color: tokens.textSecondary),
            ),
            const SizedBox(height: VeriqooSpacing.s16),
            Row(
              children: [
                Expanded(
                  child: _metric(
                    context,
                    '${product.latestScore}',
                    HistoryStrings.latestScore,
                  ),
                ),
                Expanded(
                  child: _metric(
                    context,
                    '${product.bestScore}',
                    HistoryStrings.bestScore,
                  ),
                ),
              ],
            ),
            const SizedBox(height: VeriqooSpacing.s16),
            Text(
              HistoryStrings.productDerivedNote,
              style: VeriqooType.caption.copyWith(color: tokens.textSecondary),
            ),
            const SizedBox(height: VeriqooSpacing.s24),
            const VeriqooDivider(),
            const SizedBox(height: VeriqooSpacing.s16),
            const VeriqooSectionHeader(title: HistoryStrings.inspectionHistory),
            const SizedBox(height: VeriqooSpacing.s8),
            for (final record in product.inspections)
              VeriqooInspectionCard(
                inspectionId: record.displayId,
                timestamp: record.timestampLabel,
                product: record.productName,
                score: record.score,
                status: record.status,
                onTap: () => context.go(AppRoutes.historyDetail(record.id)),
              ),
          ],
        ),
      ),
    );
  }

  Widget _metric(BuildContext context, String value, String label) {
    final tokens = Theme.of(context).extension<VeriqooTokens>()!;
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text(
          value,
          style: VeriqooType.mono
              .copyWith(color: tokens.textPrimary, fontSize: 28),
        ),
        const SizedBox(height: VeriqooSpacing.s4),
        Text(
          label,
          style: VeriqooType.meta.copyWith(color: tokens.textSecondary),
        ),
      ],
    );
  }
}
