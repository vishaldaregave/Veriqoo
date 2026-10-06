import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';
import 'package:flutter_application_1/core/theme/pro_palette.dart';
import '../features/consumer_protection/voice_copilot_sheet.dart';

/// AppShell: Hosts the 4 branches of the bottom navigation bar matching the design board:
/// 1. Home
/// 2. History
/// 3. Reports
/// 4. More
///
/// Also hosts the floating Multilingual Voice Copilot button.
class AppShell extends StatelessWidget {
  const AppShell({super.key, required this.navigationShell});

  final StatefulNavigationShell navigationShell;

  void _onDestinationSelected(int index) {
    navigationShell.goBranch(
      index,
      initialLocation: index == navigationShell.currentIndex,
    );
  }

  @override
  Widget build(BuildContext context) {
    final currentIndex = navigationShell.currentIndex;

    return Scaffold(
      backgroundColor: ProPalette.background,
      body: navigationShell,
      floatingActionButton: Padding(
        padding: const EdgeInsets.only(bottom: 12),
        child: FloatingActionButton(
          heroTag: 'voiceCopilotEverywhereFab',
          backgroundColor: const Color(0xFF0E3326),
          foregroundColor: const Color(0xFFA7F3D0),
          elevation: 4,
          tooltip: 'Multilingual Voice Copilot',
          onPressed: () => showVoiceCopilot(context),
          child: const Icon(Icons.mic, size: 24),
        ),
      ),
      floatingActionButtonLocation: FloatingActionButtonLocation.endFloat,
      bottomNavigationBar: Container(
        decoration: const BoxDecoration(
          color: Colors.white,
          border: Border(
            top: BorderSide(color: Color(0xFFE5E7EB), width: 1.0),
          ),
        ),
        child: SafeArea(
          top: false,
          child: SizedBox(
            height: 60,
            child: Row(
              mainAxisAlignment: MainAxisAlignment.spaceAround,
              children: [
                _buildNavItem(0, Icons.home_rounded, 'Home', currentIndex),
                _buildNavItem(1, Icons.history_rounded, 'History', currentIndex),
                _buildNavItem(2, Icons.description_outlined, 'Reports', currentIndex),
                _buildNavItem(3, Icons.more_horiz_rounded, 'More', currentIndex),
              ],
            ),
          ),
        ),
      ),
    );
  }

  Widget _buildNavItem(int index, IconData icon, String label, int current) {
    final isSelected = index == current;
    return InkWell(
      onTap: () => _onDestinationSelected(index),
      borderRadius: BorderRadius.circular(12),
      child: Padding(
        padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 6),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            Icon(
              icon,
              size: 22,
              color: isSelected ? const Color(0xFF0E3326) : const Color(0xFF9CA3AF),
            ),
            const SizedBox(height: 3),
            Text(
              label,
              style: TextStyle(
                fontSize: 11,
                fontWeight: isSelected ? FontWeight.w700 : FontWeight.w500,
                color: isSelected ? const Color(0xFF0E3326) : const Color(0xFF9CA3AF),
              ),
            ),
          ],
        ),
      ),
    );
  }
}
