import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:flutter_application_1/app/routes.dart';
import 'package:flutter_application_1/core/theme/pro_palette.dart';
import 'package:flutter_application_1/features/inspections/inspections_providers.dart';
import 'package:flutter_application_1/features/inspections/inspection_record.dart';

/// Screen 2: VERIQOO Home Screen.
///
/// Faithfully reproduces the clean, high-contrast, modern UI from the design board:
/// - Top bar with VERIQOO branding, notification bell, and user avatar
/// - "Scan Any Product" display heading & subtitle
/// - Signature Dark Forest Green "Tap to Scan" hero card
/// - 2x2 Quick Action grid (Scan History, Saved Reports, Regulatory Library, Learn & Explore)
/// - Recent Scans list connected to live Supabase backend data with status pills
class HomeScreen extends ConsumerWidget {
  const HomeScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final recentAsync = ref.watch(recentInspectionsProvider);

    return Scaffold(
      backgroundColor: ProPalette.background,
      body: SafeArea(
        child: RefreshIndicator(
          color: ProPalette.primaryForest,
          onRefresh: () async {
            ref.invalidate(recentInspectionsProvider);
            ref.invalidate(inspectionSummaryProvider);
          },
          child: SingleChildScrollView(
            physics: const AlwaysScrollableScrollPhysics(),
            padding: const EdgeInsets.symmetric(horizontal: 20, vertical: 16),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.stretch,
              children: [
                // 1. Top Bar
                _buildTopBar(context),
                const SizedBox(height: 24),

                // 2. Heading
                const Text(
                  'Scan Any Product',
                  style: TextStyle(
                    fontSize: 26,
                    fontWeight: FontWeight.w800,
                    letterSpacing: -0.5,
                    color: ProPalette.textHeading,
                  ),
                ),
                const SizedBox(height: 6),
                const Text(
                  'Get an evidence-backed compliance report in seconds.',
                  style: TextStyle(
                    fontSize: 14,
                    color: ProPalette.textMuted,
                  ),
                ),
                const SizedBox(height: 20),

                // 3. Hero "Tap to Scan" Card
                _buildHeroScanCard(context),
                const SizedBox(height: 20),

                // 4. 2x2 Quick Action Grid
                _buildQuickActionsGrid(context),
                const SizedBox(height: 28),

                // 5. Recent Scans Header
                Row(
                  mainAxisAlignment: MainAxisAlignment.spaceBetween,
                  children: [
                    const Text(
                      'Recent Scans',
                      style: TextStyle(
                        fontSize: 18,
                        fontWeight: FontWeight.w700,
                        color: ProPalette.textHeading,
                      ),
                    ),
                    InkWell(
                      onTap: () => context.go(AppRoutes.historyPath),
                      borderRadius: BorderRadius.circular(4),
                      child: const Padding(
                        padding: EdgeInsets.symmetric(horizontal: 4, vertical: 2),
                        child: Text(
                          'View all →',
                          style: TextStyle(
                            fontSize: 14,
                            fontWeight: FontWeight.w500,
                            color: ProPalette.textMuted,
                          ),
                        ),
                      ),
                    ),
                  ],
                ),
                const SizedBox(height: 12),

                // 6. Recent Scans List (Connected to Supabase)
                recentAsync.when(
                  loading: () => const Center(
                    child: Padding(
                      padding: EdgeInsets.all(24.0),
                      child: CircularProgressIndicator(color: ProPalette.primaryForest),
                    ),
                  ),
                  error: (_, __) => _buildFallbackRecentItem(context),
                  data: (items) {
                    if (items.isEmpty) {
                      return _buildFallbackRecentItem(context);
                    
  /// Consumer Protection Banner (Shortcut added at bottom)
  Widget _buildConsumerProtectionBanner(BuildContext context) {
    return InkWell(
      onTap: () => context.push(AppRoutes.consumerProtectionPath),
      borderRadius: BorderRadius.circular(16),
      child: Container(
        padding: const EdgeInsets.all(16),
        decoration: BoxDecoration(
          gradient: const LinearGradient(
            colors: [Color(0xFF3B82F6), Color(0xFF1D4ED8)], // Blue gradient
            begin: Alignment.topLeft,
            end: Alignment.bottomRight,
          ),
          borderRadius: BorderRadius.circular(16),
          boxShadow: [
            BoxShadow(
              color: const Color(0xFF3B82F6).withOpacity(0.3),
              blurRadius: 10,
              offset: const Offset(0, 4),
            ),
          ],
        ),
        child: Row(
          children: [
            Container(
              padding: const EdgeInsets.all(10),
              decoration: BoxDecoration(
                color: Colors.white.withOpacity(0.2),
                shape: BoxShape.circle,
              ),
              child: const Icon(Icons.security, color: Colors.white, size: 24),
            ),
            const SizedBox(width: 16),
            const Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    'Consumer Protection',
                    style: TextStyle(
                      color: Colors.white,
                      fontSize: 16,
                      fontWeight: FontWeight.bold,
                    ),
                  ),
                  SizedBox(height: 4),
                  Text(
                    'Ad Clickbait Detector & More',
                    style: TextStyle(
                      color: Colors.white70,
                      fontSize: 12,
                    ),
                  ),
                ],
              ),
            ),
            const Icon(Icons.arrow_forward_ios, color: Colors.white, size: 16),
          ],
        ),
      ),
    );
  }
}
                    return Column(
                      children: items.map((rec) => _buildRecentRecordCard(context, rec)).toList(),
                    );
                  },
                ),

                const SizedBox(height: 20),
                _buildConsumerProtectionBanner(context),
                const SizedBox(height: 32),
              ],
            ),
          ),
        ),
      ),
    );
  }

  /// Top Bar with VERIQOO logo, Notification Bell, and Avatar
  Widget _buildTopBar(BuildContext context) {
    return Row(
      mainAxisAlignment: MainAxisAlignment.spaceBetween,
      children: [
        const Text(
          'VERIQOO',
          style: TextStyle(
            fontSize: 20,
            fontWeight: FontWeight.w900,
            letterSpacing: 2.0,
            color: ProPalette.textHeading,
          ),
        ),
        Row(
          children: [
            IconButton(
              icon: Stack(
                children: [
                  const Icon(Icons.notifications_outlined, size: 24, color: ProPalette.textHeading),
                  Positioned(
                    right: 2,
                    top: 2,
                    child: Container(
                      width: 8,
                      height: 8,
                      decoration: const BoxDecoration(
                        color: ProPalette.crimsonViolation,
                        shape: BoxShape.circle,
                      ),
                    ),
                  ),
                ],
              ),
              onPressed: () => context.push(AppRoutes.notificationsPath),
            ),
            const SizedBox(width: 4),
            GestureDetector(
              onTap: () => context.go(AppRoutes.profilePath),
              child: const CircleAvatar(
                radius: 17,
                backgroundColor: Color(0xFF6366F1),
                child: Text(
                  'A',
                  style: TextStyle(
                    color: Colors.white,
                    fontWeight: FontWeight.w700,
                    fontSize: 15,
                  ),
                ),
              ),
            ),
          ],
        ),
      ],
    );
  }

  /// Hero "Tap to Scan" Card with rich forest green background
  Widget _buildHeroScanCard(BuildContext context) {
    return Material(
      color: Colors.transparent,
      child: InkWell(
        onTap: () => context.push(AppRoutes.scanCapturePath),
        borderRadius: BorderRadius.circular(20),
        child: Container(
          padding: const EdgeInsets.symmetric(horizontal: 20, vertical: 22),
          decoration: BoxDecoration(
            gradient: const LinearGradient(
              colors: [Color(0xFF0E3326), Color(0xFF164836)],
              begin: Alignment.topLeft,
              end: Alignment.bottomRight,
            ),
            borderRadius: BorderRadius.circular(20),
            boxShadow: [
              BoxShadow(
                color: const Color(0xFF0E3326).withValues(alpha: 0.25),
                blurRadius: 16,
                offset: const Offset(0, 6),
              ),
            ],
          ),
          child: Row(
            children: [
              // Camera Icon in circular container
              Container(
                width: 48,
                height: 48,
                decoration: BoxDecoration(
                  color: Colors.white.withValues(alpha: 0.15),
                  shape: BoxShape.circle,
                ),
                child: const Icon(
                  Icons.camera_alt_outlined,
                  color: Colors.white,
                  size: 24,
                ),
              ),
              const SizedBox(width: 16),

              // Title & Subtitle
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: const [
                    Text(
                      'Tap to Scan',
                      style: TextStyle(
                        color: Colors.white,
                        fontSize: 18,
                        fontWeight: FontWeight.w700,
                      ),
                    ),
                    SizedBox(height: 4),
                    Text(
                      'Product • Barcode • Label',
                      style: TextStyle(
                        color: Color(0xFFA7F3D0), // Soft Mint
                        fontSize: 12,
                        fontWeight: FontWeight.w500,
                      ),
                    ),
                  ],
                ),
              ),

              // Right Arrow Circle
              Container(
                width: 36,
                height: 36,
                decoration: BoxDecoration(
                  color: Colors.white.withValues(alpha: 0.15),
                  shape: BoxShape.circle,
                ),
                child: const Icon(
                  Icons.arrow_forward,
                  color: Colors.white,
                  size: 18,
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }

  /// 2x2 Quick Actions Grid
  Widget _buildQuickActionsGrid(BuildContext context) {
    return GridView.count(
      crossAxisCount: 2,
      crossAxisSpacing: 14,
      mainAxisSpacing: 14,
      childAspectRatio: 1.5,
      shrinkWrap: true,
      physics: const NeverScrollableScrollPhysics(),
      children: [
        // 1. Scan History
        _buildActionTile(
          context,
          icon: Icons.qr_code_scanner_rounded,
          iconColor: const Color(0xFF10B981),
          iconBg: const Color(0xFFECFDF5),
          label: 'Scan History',
          onTap: () => context.go(AppRoutes.historyPath),
        ),

        // 2. Saved Reports
        _buildActionTile(
          context,
          icon: Icons.description_outlined,
          iconColor: const Color(0xFFEF4444),
          iconBg: const Color(0xFFFEF2F2),
          label: 'Saved Reports',
          onTap: () => context.push('/reports'),
        ),

        // 3. Regulatory Library
        _buildActionTile(
          context,
          icon: Icons.menu_book_rounded,
          iconColor: const Color(0xFF8B5CF6),
          iconBg: const Color(0xFFF5F3FF),
          label: 'Regulatory Library',
          onTap: () => context.push('/regulatory-library'),
        ),

        // 4. Learn & Explore
        _buildActionTile(
          context,
          icon: Icons.explore_outlined,
          iconColor: const Color(0xFFF59E0B),
          iconBg: const Color(0xFFFFFBEB),
          label: 'Learn & Explore',
          onTap: () => context.push(AppRoutes.consumerProtectionPath),
        ),
      ],
    );
  }

  Widget _buildActionTile(
    BuildContext context, {
    required IconData icon,
    required Color iconColor,
    required Color iconBg,
    required String label,
    required VoidCallback onTap,
  }) {
    return Material(
      color: Colors.transparent,
      child: InkWell(
        onTap: onTap,
        borderRadius: BorderRadius.circular(16),
        child: Container(
          padding: const EdgeInsets.all(14),
          decoration: ProPalette.cardDecoration(context, radius: 16),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            mainAxisAlignment: MainAxisAlignment.center,
            children: [
              Container(
                width: 38,
                height: 38,
                decoration: BoxDecoration(
                  color: iconBg,
                  borderRadius: BorderRadius.circular(10),
                ),
                child: Icon(icon, color: iconColor, size: 20),
              ),
              const SizedBox(height: 10),
              Text(
                label,
                style: const TextStyle(
                  fontSize: 13,
                  fontWeight: FontWeight.w600,
                  color: ProPalette.textHeading,
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }

  /// Recent Scans Card built from real Supabase inspection
  Widget _buildRecentRecordCard(BuildContext context, InspectionRecord rec) {
    final isCompliant = rec.isCompliant == true;
    final statusType = isCompliant
        ? StatusBadgeType.compliant
        : (rec.issueCount > 2 ? StatusBadgeType.nonCompliant : StatusBadgeType.minorIssue);

    final statusLabel = isCompliant ? 'Compliant' : (rec.issueCount > 2 ? 'Non-Compliant' : 'Minor Issue');

    return Container(
      margin: const EdgeInsets.only(bottom: 10),
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
          child: const Center(
            child: Icon(Icons.fastfood_outlined, color: Color(0xFFD97706), size: 24),
          ),
        ),
        title: Text(
          rec.productName.isNotEmpty ? rec.productName : 'Packaged Commodity SKU',
          style: const TextStyle(
            fontSize: 14,
            fontWeight: FontWeight.w600,
            color: ProPalette.textHeading,
          ),
          maxLines: 1,
          overflow: TextOverflow.ellipsis,
        ),
        subtitle: Text(
          rec.timestampLabel.isNotEmpty
              ? rec.timestampLabel
              : (rec.inspectedAt != null ? _formatRelativeTime(rec.inspectedAt!) : 'Recently'),
          style: const TextStyle(
            fontSize: 12,
            color: ProPalette.textMuted,
          ),
        ),
        trailing: ProPalette.statusPill(
          statusLabel,
          type: statusType,
          showCheck: isCompliant,
        ),
        onTap: () => context.push(AppRoutes.historyDetail(rec.id)),
      ),
      ),
    );
  }


  /// Empty state shown when no inspections have been performed yet
  Widget _buildFallbackRecentItem(BuildContext context) {
    return Container(
      padding: const EdgeInsets.symmetric(vertical: 28, horizontal: 20),
      decoration: ProPalette.cardDecoration(context, radius: 14),
      child: Column(
        children: [
          Container(
            width: 56,
            height: 56,
            decoration: BoxDecoration(
              color: const Color(0xFFF0FDF4),
              borderRadius: BorderRadius.circular(14),
            ),
            child: const Icon(Icons.qr_code_scanner_rounded, color: ProPalette.accentEmerald, size: 30),
          ),
          const SizedBox(height: 14),
          const Text(
            'No scans yet',
            style: TextStyle(
              fontSize: 15,
              fontWeight: FontWeight.w700,
              color: ProPalette.textHeading,
            ),
          ),
          const SizedBox(height: 4),
          const Text(
            'Scan a product label to see your compliance history here.',
            textAlign: TextAlign.center,
            style: TextStyle(
              fontSize: 12,
              color: ProPalette.textMuted,
            ),
          ),
          const SizedBox(height: 14),
          OutlinedButton.icon(
            onPressed: () => context.push(AppRoutes.scanCapturePath),
            icon: const Icon(Icons.add_a_photo_outlined, size: 16),
            label: const Text('Scan Your First Product', style: TextStyle(fontSize: 13, fontWeight: FontWeight.w600)),
            style: OutlinedButton.styleFrom(
              foregroundColor: ProPalette.primaryForest,
              side: const BorderSide(color: Color(0xFF86EFAC)),
              backgroundColor: const Color(0xFFF0FDF4),
              padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 10),
              shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(10)),
            ),
          ),
        ],
      ),
    );
  }

  String _formatRelativeTime(DateTime time) {
    final diff = DateTime.now().difference(time);
    if (diff.inMinutes < 60) {
      return '${diff.inMinutes.clamp(1, 60)} min ago';
    } else if (diff.inHours < 24) {
      return '${diff.inHours} hours ago';
    } else {
      return '${diff.inDays} days ago';
    }
  }

  /// Consumer Protection Banner (Shortcut added at bottom)
  Widget _buildConsumerProtectionBanner(BuildContext context) {
    return InkWell(
      onTap: () => context.push(AppRoutes.consumerProtectionPath),
      borderRadius: BorderRadius.circular(16),
      child: Container(
        padding: const EdgeInsets.all(16),
        decoration: BoxDecoration(
          gradient: const LinearGradient(
            colors: [Color(0xFF3B82F6), Color(0xFF1D4ED8)], // Blue gradient
            begin: Alignment.topLeft,
            end: Alignment.bottomRight,
          ),
          borderRadius: BorderRadius.circular(16),
          boxShadow: [
            BoxShadow(
              color: const Color(0xFF3B82F6).withOpacity(0.3),
              blurRadius: 10,
              offset: const Offset(0, 4),
            ),
          ],
        ),
        child: Row(
          children: [
            Container(
              padding: const EdgeInsets.all(10),
              decoration: BoxDecoration(
                color: Colors.white.withOpacity(0.2),
                shape: BoxShape.circle,
              ),
              child: const Icon(Icons.security, color: Colors.white, size: 24),
            ),
            const SizedBox(width: 16),
            const Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    'Consumer Protection',
                    style: TextStyle(
                      color: Colors.white,
                      fontSize: 16,
                      fontWeight: FontWeight.bold,
                    ),
                  ),
                  SizedBox(height: 4),
                  Text(
                    'Ad Clickbait Detector & More',
                    style: TextStyle(
                      color: Colors.white70,
                      fontSize: 12,
                    ),
                  ),
                ],
              ),
            ),
            const Icon(Icons.arrow_forward_ios, color: Colors.white, size: 16),
          ],
        ),
      ),
    );
  }
}
