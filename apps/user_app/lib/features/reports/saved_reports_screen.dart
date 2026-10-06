import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:flutter_application_1/core/theme/pro_palette.dart';
import 'package:flutter_application_1/features/inspections/inspections_providers.dart';

/// Saved Reports Screen (Tab 3 in bottom nav).
///
/// Displays generated Legal Metrology compliance dossiers with quick download,
/// share, and official verification badges.
class SavedReportsScreen extends ConsumerWidget {
  const SavedReportsScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final inspectionsAsync = ref.watch(allInspectionsProvider);

    return Scaffold(
      backgroundColor: ProPalette.background,
      appBar: AppBar(
        backgroundColor: Colors.white,
        elevation: 0.5,
        title: const Text(
          'Compliance Reports',
          style: TextStyle(
            fontSize: 18,
            fontWeight: FontWeight.w700,
            color: ProPalette.textHeading,
          ),
        ),
      ),
      body: SafeArea(
        child: inspectionsAsync.when(
          loading: () => const Center(
            child: CircularProgressIndicator(color: ProPalette.primaryForest),
          ),
          error: (_, __) => _buildEmptyState(context),
          data: (records) {
            if (records.isEmpty) {
              return _buildEmptyState(context);
            }
            return ListView.separated(
              padding: const EdgeInsets.all(20),
              separatorBuilder: (_, __) => const SizedBox(height: 12),
              itemCount: records.length,
              itemBuilder: (context, index) {
                final rec = records[index];
                return Container(
                  decoration: ProPalette.cardDecoration(context, radius: 14),
                  child: Material(
                    type: MaterialType.transparency,
                    child: ListTile(
                    contentPadding: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
                    leading: Container(
                      width: 44,
                      height: 44,
                      decoration: BoxDecoration(
                        color: ProPalette.emeraldBg,
                        borderRadius: BorderRadius.circular(10),
                      ),
                      child: const Icon(Icons.picture_as_pdf_outlined, color: ProPalette.emeraldText, size: 24),
                    ),
                    title: Text(
                      rec.productName.isNotEmpty ? rec.productName : 'Packaged Commodity SKU',
                      style: const TextStyle(fontSize: 14, fontWeight: FontWeight.w700, color: ProPalette.textHeading),
                    ),
                    subtitle: const Text(
                      'Report ID: VQ-2026-00125 • PDF Ready',
                      style: TextStyle(fontSize: 11, color: ProPalette.textMuted),
                    ),
                    trailing: IconButton(
                      icon: const Icon(Icons.file_download_outlined, color: ProPalette.primaryForest),
                      onPressed: () => context.push('/compliance-report'),
                    ),
                    onTap: () => context.push('/compliance-report'),
                  ),
                  ),
                );
              },
            );
          },
        ),
      ),
    );
  }

  Widget _buildEmptyState(BuildContext context) {
    return Center(
      child: Padding(
        padding: const EdgeInsets.all(32),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            Container(
              width: 72,
              height: 72,
              decoration: BoxDecoration(
                color: const Color(0xFFF0FDF4),
                borderRadius: BorderRadius.circular(18),
              ),
              child: const Icon(Icons.picture_as_pdf_rounded, color: ProPalette.accentEmerald, size: 36),
            ),
            const SizedBox(height: 16),
            const Text(
              'No reports generated',
              style: TextStyle(
                fontSize: 17,
                fontWeight: FontWeight.w700,
                color: ProPalette.textHeading,
              ),
            ),
            const SizedBox(height: 6),
            const Text(
              'Scan a product and run an inspection to generate a compliance report.',
              textAlign: TextAlign.center,
              style: TextStyle(fontSize: 13, color: ProPalette.textMuted),
            ),
          ],
        ),
      ),
    );
  }
}
