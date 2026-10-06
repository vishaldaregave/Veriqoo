import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:flutter_application_1/app/routes.dart';
import 'package:flutter_application_1/core/theme/pro_palette.dart';
import 'package:flutter_application_1/features/inspections/inspections_providers.dart';
import 'package:flutter_application_1/features/inspections/inspection_record.dart';

/// Screen 9: Scan History Screen matching the design board.
///
/// Features:
/// - Top bar with Back, Title, Search and Filter actions
/// - Filter chips: "All", "Compliant", "Issues", "Favourites"
/// - Month group header ("October 2026")
/// - Scan item tiles with food/product thumbnails, timestamps, status badges, and 3-dots popup menus
/// - Backed by live Supabase backend data via [allInspectionsProvider]
class HistoryScreen extends ConsumerStatefulWidget {
  const HistoryScreen({super.key});

  @override
  ConsumerState<HistoryScreen> createState() => _HistoryScreenState();
}

class _HistoryScreenState extends ConsumerState<HistoryScreen> {
  String _selectedFilter = 'All';

  final List<String> _filters = ['All', 'Compliant', 'Issues', 'Favourites'];


  @override
  Widget build(BuildContext context) {
    final inspectionsAsync = ref.watch(allInspectionsProvider);

    return Scaffold(
      backgroundColor: ProPalette.background,
      appBar: AppBar(
        backgroundColor: Colors.white,
        elevation: 0.5,
        leading: IconButton(
          icon: const Icon(Icons.arrow_back_ios_new_rounded, color: ProPalette.textHeading, size: 20),
          onPressed: () {
            if (context.canPop()) {
              context.pop();
            } else {
              context.go(AppRoutes.homePath);
            }
          },
        ),
        title: const Text(
          'Scan History',
          style: TextStyle(
            fontSize: 18,
            fontWeight: FontWeight.w700,
            color: ProPalette.textHeading,
          ),
        ),
        actions: [
          IconButton(
            icon: const Icon(Icons.search, color: ProPalette.textHeading, size: 22),
            onPressed: () => context.push(AppRoutes.searchPath),
          ),
          IconButton(
            icon: const Icon(Icons.tune_rounded, color: ProPalette.textHeading, size: 22),
            onPressed: () {
              ScaffoldMessenger.of(context).showSnackBar(
                const SnackBar(content: Text('Filter presets applied.')),
              );
            },
          ),
          const SizedBox(width: 8),
        ],
      ),
      body: SafeArea(
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            const SizedBox(height: 12),

            // 1. Filter Chips Row
            SizedBox(
              height: 38,
              child: ListView.separated(
                scrollDirection: Axis.horizontal,
                padding: const EdgeInsets.symmetric(horizontal: 20),
                separatorBuilder: (_, __) => const SizedBox(width: 8),
                itemCount: _filters.length,
                itemBuilder: (context, index) {
                  final filter = _filters[index];
                  final isSelected = filter == _selectedFilter;
                  return GestureDetector(
                    onTap: () => setState(() => _selectedFilter = filter),
                    child: AnimatedContainer(
                      duration: const Duration(milliseconds: 150),
                      padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
                      decoration: BoxDecoration(
                        color: isSelected ? const Color(0xFF0E3326) : Colors.white,
                        borderRadius: BorderRadius.circular(20),
                        border: Border.all(
                          color: isSelected ? const Color(0xFF0E3326) : const Color(0xFFE2E8F0),
                        ),
                      ),
                      child: Text(
                        filter,
                        style: TextStyle(
                          fontSize: 12,
                          fontWeight: isSelected ? FontWeight.w700 : FontWeight.w500,
                          color: isSelected ? Colors.white : ProPalette.textHeading,
                        ),
                      ),
                    ),
                  );
                },
              ),
            ),
            const SizedBox(height: 16),

            // 2. Month Grouping Header
            const Padding(
              padding: EdgeInsets.symmetric(horizontal: 20, vertical: 4),
              child: Text(
                'October 2026',
                style: TextStyle(
                  fontSize: 13,
                  fontWeight: FontWeight.w600,
                  color: ProPalette.textMuted,
                ),
              ),
            ),
            const SizedBox(height: 6),

            // 3. Scan Items List
            Expanded(
              child: RefreshIndicator(
                color: ProPalette.primaryForest,
                onRefresh: () async {
                  ref.invalidate(allInspectionsProvider);
                },
                child: inspectionsAsync.when(
                  loading: () => const Center(
                    child: CircularProgressIndicator(color: ProPalette.primaryForest),
                  ),
                  error: (_, __) => _buildEmptyState(context),
                  data: (liveRecords) {
                    if (liveRecords.isEmpty) {
                      return _buildEmptyState(context);
                    }
                    return ListView.separated(
                      padding: const EdgeInsets.symmetric(horizontal: 20, vertical: 8),
                      separatorBuilder: (_, __) => const SizedBox(height: 10),
                      itemCount: liveRecords.length,
                      itemBuilder: (context, index) {
                        final rec = liveRecords[index];
                        return _buildLiveRecordTile(context, rec);
                      },
                    );
                  },
                ),
              ),
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildLiveRecordTile(BuildContext context, InspectionRecord rec) {
    final isCompliant = rec.isCompliant == true;
    final statusType = isCompliant
        ? StatusBadgeType.compliant
        : (rec.issueCount > 2 ? StatusBadgeType.nonCompliant : StatusBadgeType.minorIssue);
    final statusLabel = isCompliant ? 'Compliant' : (rec.issueCount > 2 ? 'Non-Compliant' : 'Minor Issue');

    return Container(
      decoration: ProPalette.cardDecoration(context, radius: 14),
      child: Material(
        type: MaterialType.transparency,
        child: ListTile(
        contentPadding: const EdgeInsets.symmetric(horizontal: 14, vertical: 4),
        leading: Container(
          width: 44,
          height: 44,
          decoration: BoxDecoration(
            color: const Color(0xFFFEF3C7),
            borderRadius: BorderRadius.circular(10),
          ),
          child: const Icon(Icons.fastfood_outlined, color: Color(0xFFD97706), size: 24),
        ),
        title: Text(
          rec.productName.isNotEmpty ? rec.productName : 'Packaged Commodity SKU',
          style: const TextStyle(fontSize: 14, fontWeight: FontWeight.w700, color: ProPalette.textHeading),
          maxLines: 1,
          overflow: TextOverflow.ellipsis,
        ),
        subtitle: Text(
          rec.timestampLabel.isNotEmpty
              ? rec.timestampLabel
              : (rec.inspectedAt != null ? _formatTime(rec.inspectedAt!) : 'Recently'),
          style: const TextStyle(fontSize: 12, color: ProPalette.textMuted),
        ),

        trailing: Row(
          mainAxisSize: MainAxisSize.min,
          children: [
            ProPalette.statusPill(statusLabel, type: statusType),
            const SizedBox(width: 4),
            IconButton(
              icon: const Icon(Icons.more_vert, size: 20, color: ProPalette.textMuted),
              onPressed: () => _showItemActions(context, rec.productName),
            ),
          ],
        ),
        onTap: () => context.push(AppRoutes.historyDetail(rec.id)),
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
              child: const Icon(Icons.history_toggle_off_rounded, color: ProPalette.accentEmerald, size: 36),
            ),
            const SizedBox(height: 16),
            const Text(
              'No inspections yet',
              style: TextStyle(
                fontSize: 17,
                fontWeight: FontWeight.w700,
                color: ProPalette.textHeading,
              ),
            ),
            const SizedBox(height: 6),
            const Text(
              'Your compliance scan history will appear here once you scan a product.',
              textAlign: TextAlign.center,
              style: TextStyle(fontSize: 13, color: ProPalette.textMuted),
            ),
            const SizedBox(height: 20),
            ElevatedButton.icon(
              onPressed: () => context.go(AppRoutes.scanCapturePath),
              icon: const Icon(Icons.qr_code_scanner_rounded, size: 18),
              label: const Text('Scan a Product', style: TextStyle(fontSize: 14, fontWeight: FontWeight.w700)),
              style: ElevatedButton.styleFrom(
                backgroundColor: ProPalette.primaryForest,
                foregroundColor: Colors.white,
                padding: const EdgeInsets.symmetric(horizontal: 24, vertical: 12),
                shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
                elevation: 0,
              ),
            ),
          ],
        ),
      ),
    );
  }

  void _showItemActions(BuildContext context, String productName) {
    showModalBottomSheet(
      context: context,
      shape: const RoundedRectangleBorder(
        borderRadius: BorderRadius.vertical(top: Radius.circular(20)),
      ),
      builder: (context) {
        return SafeArea(
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              ListTile(
                leading: const Icon(Icons.visibility_outlined),
                title: const Text('View Full Dossier'),
                onTap: () {
                  Navigator.pop(context);
                  context.push('/compliance-report');
                },
              ),
              ListTile(
                leading: const Icon(Icons.share_outlined),
                title: const Text('Share Verification'),
                onTap: () {
                  Navigator.pop(context);
                },
              ),
              ListTile(
                leading: const Icon(Icons.delete_outline, color: ProPalette.crimsonViolation),
                title: const Text('Delete from History', style: TextStyle(color: ProPalette.crimsonViolation)),
                onTap: () => Navigator.pop(context),
              ),
            ],
          ),
        );
      },
    );
  }

  String _formatTime(DateTime time) {
    final diff = DateTime.now().difference(time);
    if (diff.inMinutes < 60) return '${diff.inMinutes.clamp(1, 60)} min ago';
    if (diff.inHours < 24) return '${diff.inHours} hours ago';
    return '${diff.inDays} days ago';
  }
}
