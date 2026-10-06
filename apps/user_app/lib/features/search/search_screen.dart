import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:shared_core/design_system/design_system.dart';

import 'package:flutter_application_1/app/routes.dart';
import 'package:flutter_application_1/core/widgets/app_background.dart';
import 'package:flutter_application_1/features/history/history_strings.dart';
import 'package:flutter_application_1/features/history/recent_searches_store.dart';
import 'package:flutter_application_1/features/inspections/inspection_query.dart';
import 'package:flutter_application_1/features/inspections/inspection_record.dart';
import 'package:flutter_application_1/features/inspections/inspections_providers.dart';

/// The SEARCH surface. A large editorial field over the bounded inspections
/// corpus (`allInspectionsProvider`), filtered client-side via [InspectionQuery]
/// across product / inspection id / manufacturer / date / issue. Shows recent
/// searches (persisted) when the field is empty, and a no-results state when a
/// query matches nothing.
class SearchScreen extends ConsumerStatefulWidget {
  const SearchScreen({super.key});

  @override
  ConsumerState<SearchScreen> createState() => _SearchScreenState();
}

class _SearchScreenState extends ConsumerState<SearchScreen> {
  final TextEditingController _controller = TextEditingController();
  String _text = '';

  @override
  void dispose() {
    _controller.dispose();
    super.dispose();
  }

  void _submit(String query) {
    final trimmed = query.trim();
    if (trimmed.isEmpty) {
      return;
    }
    ref.read(recentSearchesControllerProvider.notifier).add(trimmed);
  }

  void _useRecent(String query) {
    _controller.text = query;
    _controller.selection = TextSelection.collapsed(offset: query.length);
    setState(() => _text = query);
  }

  void _openResult(String query, InspectionRecord record) {
    _submit(query);
    context.go(AppRoutes.historyDetail(record.id));
  }

  @override
  Widget build(BuildContext context) {
    final tokens = Theme.of(context).extension<VeriqooTokens>()!;
    final all = ref.watch(allInspectionsProvider);
    final trimmed = _text.trim();

    return Scaffold(
      backgroundColor: tokens.bg,
      appBar: const VeriqooAppBar(title: HistoryStrings.searchTitle),
      body: VeriqooBackdrop(
        background: const TechnicalCoordinates(),
        child: SafeArea(
          child: Center(
            child: ConstrainedBox(
              constraints: const BoxConstraints(maxWidth: 640),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.stretch,
                children: [
                  Padding(
                    padding: const EdgeInsets.fromLTRB(
                      VeriqooSpacing.s24,
                      VeriqooSpacing.s16,
                      VeriqooSpacing.s24,
                      VeriqooSpacing.s8,
                    ),
                    child: VeriqooTextField(
                      controller: _controller,
                      label: HistoryStrings.searchLabel,
                      hintText: HistoryStrings.searchHint,
                      prefixIcon: VeriqooIcons.search,
                      textInputAction: TextInputAction.search,
                      onChanged: (value) => setState(() => _text = value),
                      onSubmitted: _submit,
                    ),
                  ),
                  Expanded(
                    child: trimmed.isEmpty
                        ? _recent(tokens)
                        : all.when(
                            loading: () => const Center(
                              child: VeriqooLoading(message: 'Loading'),
                            ),
                            error: (_, __) => VeriqooErrorState(
                              title: HistoryStrings.errorTitle,
                              message: HistoryStrings.errorMessage,
                              onRetry: () =>
                                  ref.invalidate(allInspectionsProvider),
                            ),
                            data: (records) =>
                                _results(context, trimmed, records),
                          ),
                  ),
                ],
              ),
            ),
          ),
        ),
      ),
    );
  }

  Widget _results(
    BuildContext context,
    String text,
    List<InspectionRecord> all,
  ) {
    final results = InspectionQuery(text: text).apply(all);
    if (results.isEmpty) {
      return const VeriqooEmptyState(
        icon: VeriqooIcons.search,
        title: HistoryStrings.noResultsTitle,
        message: HistoryStrings.noResultsMessage,
      );
    }
    return ListView.builder(
      padding: const EdgeInsets.fromLTRB(
        VeriqooSpacing.s24,
        VeriqooSpacing.s8,
        VeriqooSpacing.s24,
        VeriqooSpacing.s32,
      ),
      itemCount: results.length,
      itemBuilder: (context, i) {
        final record = results[i];
        return VeriqooInspectionCard(
          inspectionId: record.displayId,
          timestamp: record.timestampLabel,
          product: record.productName,
          score: record.score,
          status: record.status,
          onTap: () => _openResult(text, record),
        );
      },
    );
  }

  Widget _recent(VeriqooTokens tokens) {
    final recent = ref.watch(recentSearchesControllerProvider);
    return recent.maybeWhen(
      data: (queries) {
        if (queries.isEmpty) {
          return const SizedBox.shrink();
        }
        return ListView(
          padding: const EdgeInsets.fromLTRB(
            VeriqooSpacing.s24,
            VeriqooSpacing.s16,
            VeriqooSpacing.s24,
            VeriqooSpacing.s32,
          ),
          children: [
            Row(
              children: [
                Expanded(
                  child: Text(
                    HistoryStrings.recentSearches,
                    style: VeriqooType.meta
                        .copyWith(color: tokens.textSecondary),
                  ),
                ),
                VeriqooButton(
                  label: HistoryStrings.clear,
                  variant: VeriqooButtonVariant.ghost,
                  size: VeriqooButtonSize.small,
                  onPressed: () => ref
                      .read(recentSearchesControllerProvider.notifier)
                      .clear(),
                ),
              ],
            ),
            const SizedBox(height: VeriqooSpacing.s8),
            for (final query in queries) ...[
              InkWell(
                onTap: () => _useRecent(query),
                child: Padding(
                  padding: const EdgeInsets.symmetric(
                    vertical: VeriqooSpacing.s12,
                  ),
                  child: Row(
                    children: [
                      Icon(
                        VeriqooIcons.history,
                        size: 18,
                        color: tokens.textTertiary,
                      ),
                      const SizedBox(width: VeriqooSpacing.s12),
                      Expanded(
                        child: Text(
                          query,
                          style: VeriqooType.body
                              .copyWith(color: tokens.textPrimary),
                        ),
                      ),
                    ],
                  ),
                ),
              ),
              const VeriqooDivider(),
            ],
          ],
        );
      },
      orElse: () => const SizedBox.shrink(),
    );
  }
}
