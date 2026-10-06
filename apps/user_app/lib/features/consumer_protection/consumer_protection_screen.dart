import 'package:flutter/material.dart';
import '../../core/theme/pro_palette.dart';
import 'ad_detector_screen.dart';
import 'heatmap_screen.dart';

/// Master Hub for Veriqoo Consumer Protection & Citizen Defense Features.
///
/// Features:
/// 1. Social Media & Instagram Ad Clickbait Detector
/// 2. India Grievance Density Heatmap
/// 3. International Cosmetics Quality Check (Pipeline / Locked option)
/// 4. National Consumer Helpline Information (1915)
class ConsumerProtectionScreen extends StatelessWidget {
  const ConsumerProtectionScreen({super.key});

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final isDark = theme.brightness == Brightness.dark;

    return Scaffold(
      appBar: AppBar(
        title: const Text('Consumer Protection'),
      ),
      body: ListView(
        padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
        children: [
          // 1. Hero Citizen Shield Banner
          _buildHeroBanner(context, isDark),

          const SizedBox(height: 16),

          // 2. Instagram Ad Clickbait Detector
          _buildFeatureCard(
            context,
            icon: Icons.campaign_outlined,
            iconColor: ProPalette.crimsonViolation,
            title: 'Instagram & Social Ad Shield',
            subtitle: 'Real-time floating overlay that flags deceptive claims, inflated discounts, and fake endorsements.',
            badgeText: 'Overlay Guard Active',
            badgeColor: ProPalette.crimsonViolation,
            onTap: () {
              Navigator.of(context).push(
                MaterialPageRoute(builder: (_) => const AdDetectorScreen()),
              );
            },
          ),

          const SizedBox(height: 12),

          // 3. India Complaints Heatmap
          _buildFeatureCard(
            context,
            icon: Icons.map_outlined,
            iconColor: ProPalette.amberWarning,
            title: 'India Complaints Heatmap',
            subtitle: 'Live state-by-state grievance density map with automatic 15-second refresh stream.',
            badgeText: 'Live Stream',
            badgeColor: ProPalette.amberWarning,
            onTap: () {
              Navigator.of(context).push(
                MaterialPageRoute(builder: (_) => const HeatmapScreen()),
              );
            },
          ),

          const SizedBox(height: 12),

          // 4. International Product Quality Check (PIPELINE - NOT OPENABLE)
          _buildLockedPipelineCard(context, isDark),

          const SizedBox(height: 24),

          // 5. National Consumer Helpline Info Card
          _buildHelplineCard(context, isDark),

          const SizedBox(height: 32),
        ],
      ),
    );
  }

  Widget _buildHeroBanner(BuildContext context, bool isDark) {
    return Container(
      decoration: BoxDecoration(
        gradient: LinearGradient(
          colors: isDark
              ? [const Color(0xFF1E293B), const Color(0xFF0F172A)]
              : [const Color(0xFFEEF2FF), const Color(0xFFE0E7FF)],
          begin: Alignment.topLeft,
          end: Alignment.bottomRight,
        ),
        borderRadius: BorderRadius.circular(12),
        border: Border.all(color: ProPalette.electricBlue.withValues(alpha: 0.3)),
      ),
      padding: const EdgeInsets.all(16),
      child: Row(
        children: [
          Container(
            padding: const EdgeInsets.all(12),
            decoration: BoxDecoration(
              color: ProPalette.electricBlue.withValues(alpha: 0.15),
              shape: BoxShape.circle,
            ),
            child: const Icon(Icons.shield_outlined, color: ProPalette.electricBlue, size: 28),
          ),
          const SizedBox(width: 14),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                const Text(
                  'Consumer Rights & Defense',
                  style: TextStyle(fontWeight: FontWeight.bold, fontSize: 16),
                ),
                const SizedBox(height: 4),
                Text(
                  'Empowering Indian consumers with AI verification, legal metrology enforcement, and grievance escalation.',
                  style: TextStyle(fontSize: 12, color: isDark ? Colors.white70 : Colors.black87),
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildFeatureCard(
    BuildContext context, {
    required IconData icon,
    required Color iconColor,
    required String title,
    required String subtitle,
    required String badgeText,
    required Color badgeColor,
    required VoidCallback onTap,
  }) {
    return InkWell(
      onTap: onTap,
      borderRadius: BorderRadius.circular(12),
      child: Container(
        decoration: ProPalette.cardDecoration(context),
        padding: const EdgeInsets.all(16),
        child: Row(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Container(
              padding: const EdgeInsets.all(10),
              decoration: BoxDecoration(
                color: iconColor.withValues(alpha: 0.12),
                borderRadius: BorderRadius.circular(10),
              ),
              child: Icon(icon, color: iconColor, size: 24),
            ),
            const SizedBox(width: 14),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Row(
                    children: [
                      Expanded(
                        child: Text(
                          title,
                          style: const TextStyle(fontWeight: FontWeight.bold, fontSize: 14),
                        ),
                      ),
                      Container(
                        padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 2),
                        decoration: ProPalette.badgeDecoration(color: badgeColor, radius: 4),
                        child: Text(
                          badgeText,
                          style: TextStyle(
                            fontSize: 10,
                            fontWeight: FontWeight.bold,
                            color: badgeColor,
                          ),
                        ),
                      ),
                    ],
                  ),
                  const SizedBox(height: 4),
                  Text(
                    subtitle,
                    style: const TextStyle(fontSize: 12, color: Colors.grey),
                  ),
                ],
              ),
            ),
            const SizedBox(width: 6),
            const Icon(Icons.chevron_right, color: Colors.grey, size: 20),
          ],
        ),
      ),
    );
  }

  /// Feature: International Product Quality Check (Locked / Not Openable)
  Widget _buildLockedPipelineCard(BuildContext context, bool isDark) {
    return InkWell(
      onTap: () => _showPipelineLockedDialog(context),
      borderRadius: BorderRadius.circular(12),
      child: Container(
        decoration: BoxDecoration(
          color: isDark ? const Color(0xFF1E293B).withValues(alpha: 0.6) : const Color(0xFFF8FAFC),
          borderRadius: BorderRadius.circular(12),
          border: Border.all(
            color: Colors.grey.withValues(alpha: 0.3),
            width: 1.2,
          ),
        ),
        padding: const EdgeInsets.all(16),
        child: Row(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Container(
              padding: const EdgeInsets.all(10),
              decoration: BoxDecoration(
                color: Colors.purple.withValues(alpha: 0.12),
                borderRadius: BorderRadius.circular(10),
              ),
              child: const Icon(Icons.science_outlined, color: Colors.purple, size: 24),
            ),
            const SizedBox(width: 14),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Row(
                    children: [
                      const Expanded(
                        child: Text(
                          'International Cosmetics Quality Check',
                          style: TextStyle(fontWeight: FontWeight.bold, fontSize: 14),
                        ),
                      ),
                      Container(
                        padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 2),
                        decoration: BoxDecoration(
                          color: Colors.grey.withValues(alpha: 0.2),
                          borderRadius: BorderRadius.circular(4),
                          border: Border.all(color: Colors.grey.withValues(alpha: 0.4)),
                        ),
                        child: const Row(
                          mainAxisSize: MainAxisSize.min,
                          children: [
                            Icon(Icons.lock_outline, size: 10, color: Colors.grey),
                            SizedBox(width: 3),
                            Text(
                              'In Pipeline',
                              style: TextStyle(
                                fontSize: 10,
                                fontWeight: FontWeight.bold,
                                color: Colors.grey,
                              ),
                            ),
                          ],
                        ),
                      ),
                    ],
                  ),
                  const SizedBox(height: 4),
                  const Text(
                    'Cross-border cosmetic lab certifications, heavy metal testing, and DGFT import approval verification.',
                    style: TextStyle(fontSize: 12, color: Colors.grey),
                  ),
                  const SizedBox(height: 6),
                  const Text(
                    'Under technical review - Tap for regulatory notice',
                    style: TextStyle(fontSize: 11, color: Colors.purple, fontWeight: FontWeight.w500),
                  ),
                ],
              ),
            ),
            const SizedBox(width: 6),
            const Icon(Icons.lock_outline, color: Colors.grey, size: 18),
          ],
        ),
      ),
    );
  }

  void _showPipelineLockedDialog(BuildContext context) {
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
        content: const Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(
              'International Product Quality & Cosmetics Audit is currently under regulatory pipeline integration.',
              style: TextStyle(fontWeight: FontWeight.bold, fontSize: 13),
            ),
            SizedBox(height: 10),
            Text(
              'This module requires direct API authorization from the Central Drugs Standard Control Organisation (CDSCO) '
              'and the Directorate General of Foreign Trade (DGFT) for batch testing verification.\n\n'
              'Status: Architecture draft ready. Pending final regulatory gazette approval. This option is currently locked for inspection.',
              style: TextStyle(fontSize: 12, color: Colors.grey, height: 1.4),
            ),
          ],
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

  Widget _buildHelplineCard(BuildContext context, bool isDark) {
    return Container(
      decoration: ProPalette.cardDecoration(context),
      padding: const EdgeInsets.all(14),
      child: Row(
        children: [
          Container(
            padding: const EdgeInsets.all(8),
            decoration: BoxDecoration(
              color: ProPalette.emeraldVerified.withValues(alpha: 0.12),
              shape: BoxShape.circle,
            ),
            child: const Icon(Icons.phone_in_talk, color: ProPalette.emeraldVerified, size: 20),
          ),
          const SizedBox(width: 12),
          const Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  'National Consumer Helpline: 1915',
                  style: TextStyle(fontWeight: FontWeight.bold, fontSize: 13),
                ),
                Text(
                  'Direct government escalation toll-free number (Govt. of India)',
                  style: TextStyle(fontSize: 11, color: Colors.grey),
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }
}
