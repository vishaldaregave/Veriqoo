import 'package:flutter/material.dart';
import 'package:flutter_application_1/core/theme/pro_palette.dart';

/// Screen 11: Regulatory Library Screen matching the design board.
///
/// Features:
/// - Search bar ("Search regulations, clauses...")
/// - Filter chips: "All", "Legal Metrology", "FSSAI", "BIS"
/// - List of statutory Act cards with colored icon containers and subtitles
/// - Interactive clause inspection sheet
class RegulatoryLibraryScreen extends StatefulWidget {
  const RegulatoryLibraryScreen({super.key});

  @override
  State<RegulatoryLibraryScreen> createState() => _RegulatoryLibraryScreenState();
}

class _RegulatoryLibraryScreenState extends State<RegulatoryLibraryScreen> {
  String _activeFilter = 'All';
  final TextEditingController _searchController = TextEditingController();

  final List<String> _filters = ['All', 'Legal Metrology', 'FSSAI', 'BIS'];

  final List<Map<String, dynamic>> _regulations = [
    {
      'title': 'Legal Metrology Act, 2009',
      'subtitle': 'Primary legislation',
      'category': 'Legal Metrology',
      'icon': Icons.description_outlined,
      'iconColor': ProPalette.purpleAct,
      'iconBg': ProPalette.purpleBg,
      'clauses': [
        {'clause': 'Section 18', 'name': 'Declarations on pre-packaged commodities'},
        {'clause': 'Section 36', 'name': 'Penalty for non-standard packages & MRP violations'},
      ],
    },
    {
      'title': 'Packaged Commodities Rules, 2011',
      'subtitle': 'Labelling and declarations',
      'category': 'Legal Metrology',
      'icon': Icons.eco_outlined,
      'iconColor': ProPalette.emeraldText,
      'iconBg': ProPalette.emeraldBg,
      'clauses': [
        {'clause': 'Rule 6(1)(a)', 'name': 'Name and address of manufacturer/packer'},
        {'clause': 'Rule 6(1)(b)', 'name': 'Common or generic name of commodity'},
        {'clause': 'Rule 6(1)(c)', 'name': 'Net quantity in standard unit of weight or measure'},
        {'clause': 'Rule 6(1)(d)', 'name': 'Month and year of manufacture or packing'},
        {'clause': 'Rule 6(1)(e)', 'name': 'Maximum retail price (MRP) inclusive of all taxes'},
        {'clause': 'Rule 6(1)(f)', 'name': 'Consumer grievance redressal details (name, address, phone, email)'},
      ],
    },
    {
      'title': 'FSSAI Labelling Regulations',
      'subtitle': 'Food labelling requirements',
      'category': 'FSSAI',
      'icon': Icons.shield_outlined,
      'iconColor': ProPalette.amberWarning,
      'iconBg': ProPalette.amberBg,
      'clauses': [
        {'clause': 'FSSAI Sec 5', 'name': 'List of ingredients in descending order of weight'},
        {'clause': 'FSSAI Sec 7', 'name': 'Nutritional information per 100g or per serve'},
        {'clause': 'FSSAI Sec 8', 'name': 'Veg / Non-Veg logo (green or brown symbol)'},
      ],
    },
    {
      'title': 'BIS Certification Requirements',
      'subtitle': 'Product certification standards',
      'category': 'BIS',
      'icon': Icons.verified_outlined,
      'iconColor': ProPalette.blueStandard,
      'iconBg': ProPalette.blueBg,
      'clauses': [
        {'clause': 'IS 14543', 'name': 'Packaged Drinking Water standards'},
        {'clause': 'IS 4984', 'name': 'Standard specifications for quality testing'},
      ],
    },
  ];

  @override
  void dispose() {
    _searchController.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final query = _searchController.text.trim().toLowerCase();
    final filtered = _regulations.where((item) {
      final matchesFilter = _activeFilter == 'All' || item['category'] == _activeFilter;
      final matchesQuery = query.isEmpty ||
          item['title'].toString().toLowerCase().contains(query) ||
          item['subtitle'].toString().toLowerCase().contains(query);
      return matchesFilter && matchesQuery;
    }).toList();

    return Scaffold(
      backgroundColor: ProPalette.background,
      appBar: AppBar(
        backgroundColor: Colors.white,
        elevation: 0.5,
        leading: IconButton(
          icon: const Icon(Icons.arrow_back_ios_new_rounded, color: ProPalette.textHeading, size: 20),
          onPressed: () => Navigator.of(context).pop(),
        ),
        title: const Text(
          'Regulatory Library',
          style: TextStyle(
            fontSize: 18,
            fontWeight: FontWeight.w700,
            color: ProPalette.textHeading,
          ),
        ),
      ),
      body: SafeArea(
        child: Column(
          children: [
            // 1. Search Bar
            Padding(
              padding: const EdgeInsets.fromLTRB(20, 16, 20, 12),
              child: Container(
                decoration: BoxDecoration(
                  color: Colors.white,
                  borderRadius: BorderRadius.circular(12),
                  border: Border.all(color: ProPalette.cardBorder),
                ),
                child: TextField(
                  controller: _searchController,
                  onChanged: (_) => setState(() {}),
                  decoration: const InputDecoration(
                    hintText: 'Search regulations, clauses...',
                    hintStyle: TextStyle(fontSize: 14, color: ProPalette.textTertiary),
                    prefixIcon: Icon(Icons.search, color: ProPalette.textMuted, size: 20),
                    border: InputBorder.none,
                    contentPadding: EdgeInsets.symmetric(horizontal: 14, vertical: 12),
                  ),
                ),
              ),
            ),

            // 2. Filter Chips
            SizedBox(
              height: 38,
              child: ListView.separated(
                scrollDirection: Axis.horizontal,
                padding: const EdgeInsets.symmetric(horizontal: 20),
                separatorBuilder: (_, __) => const SizedBox(width: 8),
                itemCount: _filters.length,
                itemBuilder: (context, index) {
                  final filter = _filters[index];
                  final isSelected = filter == _activeFilter;
                  return GestureDetector(
                    onTap: () => setState(() => _activeFilter = filter),
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

            // 3. Regulation Cards List
            Expanded(
              child: ListView.separated(
                padding: const EdgeInsets.symmetric(horizontal: 20, vertical: 8),
                separatorBuilder: (_, __) => const SizedBox(height: 12),
                itemCount: filtered.length,
                itemBuilder: (context, index) {
                  final item = filtered[index];
                  return Container(
                    decoration: ProPalette.cardDecoration(context, radius: 14),
                    child: ListTile(
                      contentPadding: const EdgeInsets.symmetric(horizontal: 16, vertical: 6),
                      leading: Container(
                        width: 44,
                        height: 44,
                        decoration: BoxDecoration(
                          color: item['iconBg'] as Color,
                          borderRadius: BorderRadius.circular(10),
                        ),
                        child: Icon(item['icon'] as IconData, color: item['iconColor'] as Color, size: 24),
                      ),
                      title: Text(
                        item['title'] as String,
                        style: const TextStyle(
                          fontSize: 14,
                          fontWeight: FontWeight.w700,
                          color: ProPalette.textHeading,
                        ),
                      ),
                      subtitle: Text(
                        item['subtitle'] as String,
                        style: const TextStyle(
                          fontSize: 12,
                          color: ProPalette.textMuted,
                        ),
                      ),
                      trailing: const Icon(Icons.arrow_forward_ios_rounded, size: 14, color: Color(0xFF94A3B8)),
                      onTap: () => _showClauseDetailsSheet(context, item),
                    ),
                  );
                },
              ),
            ),
          ],
        ),
      ),
    );
  }

  void _showClauseDetailsSheet(BuildContext context, Map<String, dynamic> item) {
    final clauses = item['clauses'] as List<Map<String, String>>;
    showModalBottomSheet(
      context: context,
      shape: const RoundedRectangleBorder(
        borderRadius: BorderRadius.vertical(top: Radius.circular(20)),
      ),
      builder: (context) {
        return SafeArea(
          child: Padding(
            padding: const EdgeInsets.all(24.0),
            child: Column(
              mainAxisSize: MainAxisSize.min,
              crossAxisAlignment: CrossAxisAlignment.stretch,
              children: [
                Row(
                  children: [
                    Container(
                      width: 40,
                      height: 40,
                      decoration: BoxDecoration(
                        color: item['iconBg'] as Color,
                        borderRadius: BorderRadius.circular(8),
                      ),
                      child: Icon(item['icon'] as IconData, color: item['iconColor'] as Color, size: 22),
                    ),
                    const SizedBox(width: 12),
                    Expanded(
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Text(
                            item['title'] as String,
                            style: const TextStyle(fontSize: 15, fontWeight: FontWeight.w700, color: ProPalette.textHeading),
                          ),
                          Text(item['subtitle'] as String, style: const TextStyle(fontSize: 12, color: ProPalette.textMuted)),
                        ],
                      ),
                    ),
                  ],
                ),
                const SizedBox(height: 20),
                const Divider(),
                const SizedBox(height: 8),
                const Text(
                  'Statutory Clauses & Provisions',
                  style: TextStyle(fontSize: 13, fontWeight: FontWeight.w700, color: ProPalette.textHeading),
                ),
                const SizedBox(height: 12),
                ...clauses.map((c) {
                  return Padding(
                    padding: const EdgeInsets.only(bottom: 12.0),
                    child: Row(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Container(
                          padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
                          decoration: BoxDecoration(
                            color: const Color(0xFFFEF3C7),
                            borderRadius: BorderRadius.circular(6),
                          ),
                          child: Text(
                            c['clause']!,
                            style: const TextStyle(fontSize: 11, fontWeight: FontWeight.w700, color: Color(0xFFB45309)),
                          ),
                        ),
                        const SizedBox(width: 10),
                        Expanded(
                          child: Text(
                            c['name']!,
                            style: const TextStyle(fontSize: 13, color: ProPalette.textHeading),
                          ),
                        ),
                      ],
                    ),
                  );
                }),
              ],
            ),
          ),
        );
      },
    );
  }
}
