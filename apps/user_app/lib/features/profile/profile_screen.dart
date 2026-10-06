import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:supabase_flutter/supabase_flutter.dart';
import 'package:flutter_application_1/app/routes.dart';
import 'package:flutter_application_1/core/theme/pro_palette.dart';
import 'package:flutter_application_1/features/auth/auth_actions.dart';

/// Screen 12: More / Profile Screen matching the design board.
///
/// Features:
/// - User Profile Header (Avatar "A", Ajinkya Magar, email)
/// - Navigation options: My Reports, Favourites, Notifications, Settings, Help & Support, About Veriqoo, Consumer Protection Suite
/// - Elegant wavy gold/emerald Veriqoo brand card at bottom
class ProfileScreen extends ConsumerWidget {
  const ProfileScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final user = Supabase.instance.client.auth.currentUser;
    final userEmail = user?.email ?? 'ajinkya.magar@example.com';
    final userName = userEmail.contains('@')
        ? userEmail.split('@').first.replaceAll('.', ' ').toUpperCase()
        : 'Ajinkya Magar';

    return Scaffold(
      backgroundColor: ProPalette.background,
      body: SafeArea(
        child: SingleChildScrollView(
          padding: const EdgeInsets.symmetric(horizontal: 20, vertical: 20),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              // 1. Profile Header
              Row(
                children: [
                  const CircleAvatar(
                    radius: 28,
                    backgroundColor: Color(0xFF6366F1),
                    child: Text(
                      'A',
                      style: TextStyle(
                        color: Colors.white,
                        fontSize: 24,
                        fontWeight: FontWeight.w700,
                      ),
                    ),
                  ),
                  const SizedBox(width: 16),
                  Expanded(
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text(
                          userName.isNotEmpty ? userName : 'Ajinkya Magar',
                          style: const TextStyle(
                            fontSize: 18,
                            fontWeight: FontWeight.w800,
                            color: ProPalette.textHeading,
                          ),
                        ),
                        const SizedBox(height: 2),
                        Text(
                          userEmail,
                          style: const TextStyle(
                            fontSize: 13,
                            color: ProPalette.textMuted,
                          ),
                          maxLines: 1,
                          overflow: TextOverflow.ellipsis,
                        ),
                      ],
                    ),
                  ),
                ],
              ),
              const SizedBox(height: 28),

              // 2. Main Menu Actions
              Container(
                decoration: ProPalette.cardDecoration(context, radius: 16),
                child: Column(
                  children: [
                    _buildMenuRow(
                      icon: Icons.description_outlined,
                      label: 'My Reports',
                      onTap: () => context.push('/reports'),
                    ),
                    const Divider(height: 1, indent: 56, color: Color(0xFFF1F5F9)),
                    _buildMenuRow(
                      icon: Icons.favorite_border_rounded,
                      label: 'Favourites',
                      onTap: () => context.go(AppRoutes.historyPath),
                    ),
                    const Divider(height: 1, indent: 56, color: Color(0xFFF1F5F9)),
                    _buildMenuRow(
                      icon: Icons.notifications_none_rounded,
                      label: 'Notifications',
                      onTap: () => context.push(AppRoutes.notificationsPath),
                    ),
                    const Divider(height: 1, indent: 56, color: Color(0xFFF1F5F9)),
                    _buildMenuRow(
                      icon: Icons.shield_outlined,
                      label: 'Consumer Protection Suite',
                      onTap: () => context.push(AppRoutes.consumerProtectionPath),
                    ),
                  ],
                ),
              ),
              const SizedBox(height: 16),

              // 3. Settings & Support Section
              Container(
                decoration: ProPalette.cardDecoration(context, radius: 16),
                child: Column(
                  children: [
                    _buildMenuRow(
                      icon: Icons.settings_outlined,
                      label: 'Settings',
                      onTap: () => context.push(AppRoutes.settingsPath),
                    ),
                    const Divider(height: 1, indent: 56, color: Color(0xFFF1F5F9)),
                    _buildMenuRow(
                      icon: Icons.help_outline_rounded,
                      label: 'Help & Support',
                      onTap: () => _showHelpDialog(context),
                    ),
                    const Divider(height: 1, indent: 56, color: Color(0xFFF1F5F9)),
                    _buildMenuRow(
                      icon: Icons.info_outline_rounded,
                      label: 'About Veriqoo',
                      onTap: () => _showAboutDialog(context),
                    ),
                    const Divider(height: 1, indent: 56, color: Color(0xFFF1F5F9)),
                    _buildMenuRow(
                      icon: Icons.logout_rounded,
                      label: 'Sign Out',
                      iconColor: ProPalette.crimsonViolation,
                      textColor: ProPalette.crimsonViolation,
                      onTap: () => ref.read(authActionsProvider).signOut(),
                    ),
                  ],
                ),
              ),
              const SizedBox(height: 28),

              // 4. Bottom Brand Graphic Card (matching Screen 12 in mockup)
              Container(
                height: 110,
                decoration: BoxDecoration(
                  gradient: const LinearGradient(
                    colors: [Color(0xFF0E3326), Color(0xFF1B4E3C)],
                    begin: Alignment.topLeft,
                    end: Alignment.bottomRight,
                  ),
                  borderRadius: BorderRadius.circular(16),
                  boxShadow: [
                    BoxShadow(
                      color: const Color(0xFF0E3326).withValues(alpha: 0.15),
                      blurRadius: 10,
                      offset: const Offset(0, 4),
                    ),
                  ],
                ),
                child: Stack(
                  children: [
                    Positioned(
                      right: -20,
                      bottom: -30,
                      child: Icon(
                        Icons.verified_user_rounded,
                        size: 140,
                        color: Colors.white.withValues(alpha: 0.05),
                      ),
                    ),
                    Center(
                      child: Column(
                        mainAxisAlignment: MainAxisAlignment.center,
                        children: const [
                          Text(
                            'VERIQOO',
                            style: TextStyle(
                              color: Colors.white,
                              fontSize: 18,
                              fontWeight: FontWeight.w900,
                              letterSpacing: 3.0,
                            ),
                          ),
                          SizedBox(height: 4),
                          Text(
                            "Know What's on Your Pack",
                            style: TextStyle(
                              color: Color(0xFFD4AF37),
                              fontSize: 12,
                              fontWeight: FontWeight.w500,
                            ),
                          ),
                          SizedBox(height: 2),
                          Text(
                            'v1.0.0',
                            style: TextStyle(
                              color: Colors.white38,
                              fontSize: 10,
                            ),
                          ),
                        ],
                      ),
                    ),
                  ],
                ),
              ),
              const SizedBox(height: 32),
            ],
          ),
        ),
      ),
    );
  }

  Widget _buildMenuRow({
    required IconData icon,
    required String label,
    required VoidCallback onTap,
    Color? iconColor,
    Color? textColor,
  }) {
    return ListTile(
      leading: Icon(icon, color: iconColor ?? ProPalette.textHeading, size: 22),
      title: Text(
        label,
        style: TextStyle(
          fontSize: 14,
          fontWeight: FontWeight.w600,
          color: textColor ?? ProPalette.textHeading,
        ),
      ),
      trailing: const Icon(Icons.arrow_forward_ios_rounded, size: 14, color: Color(0xFF94A3B8)),
      onTap: onTap,
    );
  }

  void _showHelpDialog(BuildContext context) {
    showDialog(
      context: context,
      builder: (context) => AlertDialog(
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(16)),
        title: const Text('Help & Support'),
        content: const Text(
          'For Legal Metrology queries or grievance assistance, use the Multilingual Voice Copilot or email support@veriqoo.gov.in.\n\nNational Consumer Helpline: 1915',
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(context),
            child: const Text('OK', style: TextStyle(color: ProPalette.primaryForest)),
          ),
        ],
      ),
    );
  }

  void _showAboutDialog(BuildContext context) {
    showDialog(
      context: context,
      builder: (context) => AlertDialog(
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(16)),
        title: const Text('About VERIQOO'),
        content: const Text(
          'VERIQOO is an AI-powered Legal Metrology & Consumer Protection platform engineered for rapid packaging compliance verification across India.',
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(context),
            child: const Text('Close', style: TextStyle(color: ProPalette.primaryForest)),
          ),
        ],
      ),
    );
  }
}
