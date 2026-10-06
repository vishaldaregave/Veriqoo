import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';
import '../../../app/routes.dart';
import '../../../core/theme/pro_palette.dart';
import '../../consumer_protection/voice_copilot_sheet.dart';

/// Quick testing launcher for all Consumer Protection features directly from Home.
class HomeConsumerProtectionHub extends StatelessWidget {
  const HomeConsumerProtectionHub({super.key});

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final isDark = theme.brightness == Brightness.dark;

    return Container(
      decoration: ProPalette.cardDecoration(context, elevated: true),
      padding: const EdgeInsets.all(16),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Container(
                padding: const EdgeInsets.all(8),
                decoration: BoxDecoration(
                  color: ProPalette.electricBlue.withValues(alpha: 0.12),
                  borderRadius: BorderRadius.circular(8),
                ),
                child: const Icon(Icons.shield, color: ProPalette.electricBlue, size: 20),
              ),
              const SizedBox(width: 10),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    const Text(
                      'Consumer Protection Section',
                      style: TextStyle(fontWeight: FontWeight.bold, fontSize: 15),
                    ),
                    Text(
                      'Integrated testing suite for citizen defense & legal metrology',
                      style: TextStyle(
                        fontSize: 11,
                        color: isDark ? Colors.white60 : Colors.black54,
                      ),
                    ),
                  ],
                ),
              ),
              InkWell(
                onTap: () => context.go(AppRoutes.consumerProtectionPath),
                borderRadius: BorderRadius.circular(6),
                child: Padding(
                  padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 4),
                  child: Row(
                    mainAxisSize: MainAxisSize.min,
                    children: const [
                      Text(
                        'View All',
                        style: TextStyle(
                          fontSize: 12,
                          fontWeight: FontWeight.bold,
                          color: ProPalette.electricBlue,
                        ),
                      ),
                      Icon(Icons.arrow_forward_ios, size: 12, color: ProPalette.electricBlue),
                    ],
                  ),
                ),
              ),
            ],
          ),
          const SizedBox(height: 14),

          // 2-Column quick-action grid
          Row(
            children: [
              Expanded(
                child: _buildActionTile(
                  context,
                  icon: Icons.mic_none,
                  iconColor: ProPalette.electricBlue,
                  title: 'STT Copilot',
                  subtitle: '10 Regional langs',
                  onTap: () => showVoiceCopilot(context),
                ),
              ),
              const SizedBox(width: 8),
              Expanded(
                child: _buildActionTile(
                  context,
                  icon: Icons.campaign_outlined,
                  iconColor: ProPalette.crimsonViolation,
                  title: 'Instagram Ads',
                  subtitle: 'Clickbait detector',
                  onTap: () => context.push(AppRoutes.adDetectorPath),
                ),
              ),
            ],
          ),
          const SizedBox(height: 8),
          Row(
            children: [
              Expanded(
                child: _buildActionTile(
                  context,
                  icon: Icons.map_outlined,
                  iconColor: ProPalette.amberWarning,
                  title: 'India Heatmap',
                  subtitle: 'Live complaint map',
                  onTap: () => context.push(AppRoutes.heatmapPath),
                ),
              ),
              const SizedBox(width: 8),
              Expanded(
                child: _buildActionTile(
                  context,
                  icon: Icons.qr_code_2_outlined,
                  iconColor: ProPalette.emeraldVerified,
                  title: 'Report QR',
                  subtitle: 'Share & download',
                  onTap: () => context.push(AppRoutes.reportQrPath),
                ),
              ),
            ],
          ),
          const SizedBox(height: 8),

          // International Cosmetics Quality Check (LOCKED OPTION)
          _buildLockedTile(context, isDark),
        ],
      ),
    );
  }

  Widget _buildActionTile(
    BuildContext context, {
    required IconData icon,
    required Color iconColor,
    required String title,
    required String subtitle,
    required VoidCallback onTap,
  }) {
    final isDark = Theme.of(context).brightness == Brightness.dark;

    return InkWell(
      onTap: onTap,
      borderRadius: BorderRadius.circular(8),
      child: Container(
        padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 10),
        decoration: BoxDecoration(
          color: isDark ? const Color(0xFF0F172A) : const Color(0xFFF8FAFC),
          borderRadius: BorderRadius.circular(8),
          border: Border.all(color: isDark ? Colors.white10 : Colors.black12),
        ),
        child: Row(
          children: [
            Container(
              padding: const EdgeInsets.all(6),
              decoration: BoxDecoration(
                color: iconColor.withValues(alpha: 0.12),
                shape: BoxShape.circle,
              ),
              child: Icon(icon, color: iconColor, size: 16),
            ),
            const SizedBox(width: 8),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    title,
                    style: const TextStyle(fontWeight: FontWeight.bold, fontSize: 12),
                    maxLines: 1,
                    overflow: TextOverflow.ellipsis,
                  ),
                  Text(
                    subtitle,
                    style: const TextStyle(fontSize: 10, color: Colors.grey),
                    maxLines: 1,
                    overflow: TextOverflow.ellipsis,
                  ),
                ],
              ),
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildLockedTile(BuildContext context, bool isDark) {
    return InkWell(
      onTap: () => _showPipelineDialog(context),
      borderRadius: BorderRadius.circular(8),
      child: Container(
        width: double.infinity,
        padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 8),
        decoration: BoxDecoration(
          color: isDark ? const Color(0xFF0F172A).withValues(alpha: 0.5) : const Color(0xFFF1F5F9),
          borderRadius: BorderRadius.circular(8),
          border: Border.all(color: Colors.grey.withValues(alpha: 0.25)),
        ),
        child: Row(
          children: [
            Container(
              padding: const EdgeInsets.all(6),
              decoration: BoxDecoration(
                color: Colors.purple.withValues(alpha: 0.12),
                shape: BoxShape.circle,
              ),
              child: const Icon(Icons.science_outlined, color: Colors.purple, size: 16),
            ),
            const SizedBox(width: 8),
            const Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    'International Cosmetics Quality Check',
                    style: TextStyle(fontWeight: FontWeight.bold, fontSize: 12),
                  ),
                  Text(
                    'CDSCO & DGFT import compliance standards',
                    style: TextStyle(fontSize: 10, color: Colors.grey),
                  ),
                ],
              ),
            ),
            Container(
              padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 2),
              decoration: BoxDecoration(
                color: Colors.grey.withValues(alpha: 0.2),
                borderRadius: BorderRadius.circular(4),
              ),
              child: const Row(
                mainAxisSize: MainAxisSize.min,
                children: [
                  Icon(Icons.lock_outline, size: 10, color: Colors.grey),
                  SizedBox(width: 3),
                  Text(
                    'Pipeline',
                    style: TextStyle(fontSize: 9, fontWeight: FontWeight.bold, color: Colors.grey),
                  ),
                ],
              ),
            ),
          ],
        ),
      ),
    );
  }

  void _showPipelineDialog(BuildContext context) {
    showDialog(
      context: context,
      builder: (ctx) => AlertDialog(
        title: const Row(
          children: [
            Icon(Icons.lock_clock, color: Colors.purple),
            SizedBox(width: 8),
            Text('Feature in Pipeline'),
          ],
        ),
        content: const Text(
          'International Cosmetics Quality Check is currently in regulatory pipeline integration with CDSCO & DGFT.\n\n'
          'Status: Technical architecture defined. Direct laboratory testing verification is awaiting final Ministry clearance.',
          style: TextStyle(fontSize: 13, height: 1.4),
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.of(ctx).pop(),
            child: const Text('Understood'),
          ),
        ],
      ),
    );
  }
}
