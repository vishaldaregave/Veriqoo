import 'package:flutter/material.dart';
import 'package:flutter/foundation.dart';
import 'package:google_mlkit_text_recognition/google_mlkit_text_recognition.dart';
import 'package:image_picker/image_picker.dart';
import 'package:supabase_flutter/supabase_flutter.dart';

import 'screens/dashboard/dashboard_screen.dart';
import 'screens/dashboard/inspections_screen.dart';
import 'screens/dashboard/products_screen.dart';
import 'services/compliance_analysis.dart';
import 'services/gemini_ai_analysis_service.dart';
import 'services/legal_rules_retrieval_service.dart';
import 'services/supabase_service.dart';

Future<void> main() async {
  WidgetsFlutterBinding.ensureInitialized();

  const supabaseUrl = String.fromEnvironment('SUPABASE_URL');
  const supabaseKey = String.fromEnvironment('SUPABASE_KEY');

  if (supabaseUrl.isEmpty || supabaseKey.isEmpty) {
    throw StateError(
      'Supabase is not configured. Pass SUPABASE_URL and SUPABASE_KEY '
      'with --dart-define.',
    );
  }

  await Supabase.initialize(url: supabaseUrl, publishableKey: supabaseKey);

  runApp(const LegalCheckApp());
}

class LegalCheckApp extends StatelessWidget {
  const LegalCheckApp({super.key});

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      debugShowCheckedModeBanner: false,
      title: 'VERIQO',
      initialRoute: kIsWeb ? '/dashboard' : '/',
      routes: {
        '/': (_) => const HomeScreen(),
        '/dashboard': (_) => const DashboardScreen(),
        '/inspections': (_) => const InspectionsScreen(),
        '/products': (_) => const ProductsScreen(),
      },
      theme: ThemeData(
        useMaterial3: true,
        scaffoldBackgroundColor: const Color(0xFFF7F7F3),
        fontFamily: 'Roboto',
        colorScheme: ColorScheme.fromSeed(
          seedColor: const Color(0xFF183B32),
          brightness: Brightness.light,
        ),
      ),
    );
  }
}

class HomeScreen extends StatefulWidget {
  const HomeScreen({super.key});

  @override
  State<HomeScreen> createState() => _HomeScreenState();
}

class _HomeScreenState extends State<HomeScreen> {
  int selectedIndex = 0;

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: const Color(0xFFF7F7F3),

      appBar: AppBar(
        backgroundColor: const Color(0xFFF7F7F3),
        surfaceTintColor: Colors.transparent,
        elevation: 0,
        automaticallyImplyLeading: false,

        title: const Row(
          children: [
            Icon(Icons.verified_outlined, color: Color(0xFF183B32), size: 27),
            SizedBox(width: 10),
            Text(
              'VERIQO',
              style: TextStyle(
                color: Color(0xFF17201D),
                fontSize: 23,
                fontWeight: FontWeight.w700,
                letterSpacing: -0.5,
              ),
            ),
          ],
        ),

        actions: [
          IconButton(
            onPressed: () {},
            icon: const Icon(
              Icons.notifications_none_rounded,
              color: Color(0xFF17201D),
            ),
          ),
          const SizedBox(width: 8),
        ],
      ),

      body: _buildSelectedPage(),

      bottomNavigationBar: NavigationBar(
        backgroundColor: Colors.white,
        surfaceTintColor: Colors.transparent,
        elevation: 8,
        selectedIndex: selectedIndex,

        onDestinationSelected: (index) {
          setState(() {
            selectedIndex = index;
          });
        },

        destinations: const [
          NavigationDestination(
            icon: Icon(Icons.home_outlined),
            selectedIcon: Icon(Icons.home_rounded),
            label: 'Home',
          ),
          NavigationDestination(
            icon: Icon(Icons.qr_code_scanner_rounded),
            selectedIcon: Icon(Icons.qr_code_scanner_rounded),
            label: 'Scan',
          ),
          NavigationDestination(
            icon: Icon(Icons.history_rounded),
            selectedIcon: Icon(Icons.history_rounded),
            label: 'History',
          ),
          NavigationDestination(
            icon: Icon(Icons.person_outline_rounded),
            selectedIcon: Icon(Icons.person_rounded),
            label: 'Profile',
          ),
        ],
      ),
    );
  }

  Widget _buildSelectedPage() {
    switch (selectedIndex) {
      case 1:
        return const ScanScreen();
      case 2:
        return const RecordsScreen(title: 'Inspection History');
      case 3:
        return const ProfileScreen();
      default:
        return _buildHome();
    }
  }

  Widget _buildHome() {
    return SafeArea(
      child: SingleChildScrollView(
        physics: const BouncingScrollPhysics(),
        padding: const EdgeInsets.fromLTRB(20, 8, 20, 30),

        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            // HEADER
            const Text(
              'Product Compliance',
              style: TextStyle(
                fontSize: 30,
                fontWeight: FontWeight.w700,
                color: Color(0xFF17201D),
                letterSpacing: -0.8,
              ),
            ),

            const SizedBox(height: 6),

            const Text(
              'Inspect packaged products against mandatory declarations.',
              style: TextStyle(
                fontSize: 14,
                height: 1.5,
                color: Color(0xFF68716D),
              ),
            ),

            const SizedBox(height: 24),

            // SCAN CARD
            Container(
              width: double.infinity,
              padding: const EdgeInsets.all(22),

              decoration: BoxDecoration(
                color: const Color(0xFF183B32),
                borderRadius: BorderRadius.circular(22),
              ),

              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Container(
                    height: 48,
                    width: 48,

                    decoration: BoxDecoration(
                      color: Colors.white.withValues(alpha: 0.12),
                      borderRadius: BorderRadius.circular(14),
                    ),

                    child: const Icon(
                      Icons.qr_code_scanner_rounded,
                      color: Colors.white,
                      size: 28,
                    ),
                  ),

                  const SizedBox(height: 20),

                  const Text(
                    'Inspect a Product',
                    style: TextStyle(
                      color: Colors.white,
                      fontSize: 23,
                      fontWeight: FontWeight.w700,
                    ),
                  ),

                  const SizedBox(height: 7),

                  const Text(
                    'Capture product images from different angles '
                    'and check required declarations.',
                    style: TextStyle(
                      color: Color(0xFFD4E1DC),
                      fontSize: 14,
                      height: 1.45,
                    ),
                  ),

                  const SizedBox(height: 20),

                  SizedBox(
                    width: double.infinity,
                    height: 50,

                    child: ElevatedButton(
                      onPressed: () {
                        Navigator.push(
                          context,
                          MaterialPageRoute(builder: (_) => const ScanScreen()),
                        );
                      },

                      style: ElevatedButton.styleFrom(
                        backgroundColor: Colors.white,
                        foregroundColor: const Color(0xFF183B32),
                        elevation: 0,
                        shape: RoundedRectangleBorder(
                          borderRadius: BorderRadius.circular(13),
                        ),
                      ),

                      child: const Row(
                        mainAxisAlignment: MainAxisAlignment.center,
                        children: [
                          Icon(Icons.camera_alt_outlined),
                          SizedBox(width: 9),
                          Text(
                            'Start Inspection',
                            style: TextStyle(
                              fontSize: 15,
                              fontWeight: FontWeight.w700,
                            ),
                          ),
                        ],
                      ),
                    ),
                  ),
                ],
              ),
            ),

            const SizedBox(height: 28),

            // SEARCH
            const Text(
              'Search Records',
              style: TextStyle(
                fontSize: 18,
                fontWeight: FontWeight.w700,
                color: Color(0xFF17201D),
              ),
            ),

            const SizedBox(height: 12),

            TextField(
              decoration: InputDecoration(
                hintText: 'Search product or inspection...',
                hintStyle: const TextStyle(
                  color: Color(0xFF8A918E),
                  fontSize: 14,
                ),

                prefixIcon: const Icon(
                  Icons.search_rounded,
                  color: Color(0xFF68716D),
                ),

                filled: true,
                fillColor: Colors.white,

                contentPadding: const EdgeInsets.symmetric(vertical: 16),

                border: OutlineInputBorder(
                  borderRadius: BorderRadius.circular(14),
                  borderSide: BorderSide.none,
                ),
              ),
            ),

            const SizedBox(height: 28),

            // OVERVIEW
            const Text(
              'Overview',
              style: TextStyle(
                fontSize: 18,
                fontWeight: FontWeight.w700,
                color: Color(0xFF17201D),
              ),
            ),

            const SizedBox(height: 12),

            Row(
              children: [
                Expanded(
                  child: _statCard(
                    icon: Icons.inventory_2_outlined,
                    number: '0',
                    label: 'Inspected',
                    iconColor: const Color(0xFF183B32),
                    onTap: () {
                      Navigator.push(
                        context,
                        MaterialPageRoute(
                          builder: (_) =>
                              const RecordsScreen(title: 'Inspected Products'),
                        ),
                      );
                    },
                  ),
                ),

                const SizedBox(width: 12),

                Expanded(
                  child: _statCard(
                    icon: Icons.warning_amber_rounded,
                    number: '0',
                    label: 'Violations',
                    iconColor: const Color(0xFFA35D00),
                    onTap: () {
                      Navigator.push(
                        context,
                        MaterialPageRoute(
                          builder: (_) => const RecordsScreen(
                            title: 'Violations',
                            showViolations: true,
                          ),
                        ),
                      );
                    },
                  ),
                ),
              ],
            ),

            const SizedBox(height: 28),

            // RECENT
            Row(
              mainAxisAlignment: MainAxisAlignment.spaceBetween,
              children: [
                const Text(
                  'Recent Inspections',
                  style: TextStyle(
                    fontSize: 18,
                    fontWeight: FontWeight.w700,
                    color: Color(0xFF17201D),
                  ),
                ),

                TextButton(
                  onPressed: () {
                    setState(() {
                      selectedIndex = 2;
                    });
                  },
                  child: const Text(
                    'View all',
                    style: TextStyle(
                      color: Color(0xFF183B32),
                      fontWeight: FontWeight.w600,
                    ),
                  ),
                ),
              ],
            ),

            const SizedBox(height: 4),

            Container(
              width: double.infinity,
              padding: const EdgeInsets.symmetric(vertical: 35, horizontal: 20),

              decoration: BoxDecoration(
                color: Colors.white,
                borderRadius: BorderRadius.circular(18),
              ),

              child: Column(
                children: [
                  Container(
                    height: 58,
                    width: 58,

                    decoration: BoxDecoration(
                      color: const Color(0xFFF0F2EF),
                      shape: BoxShape.circle,
                    ),

                    child: const Icon(
                      Icons.assignment_outlined,
                      color: Color(0xFF68716D),
                      size: 29,
                    ),
                  ),

                  const SizedBox(height: 14),

                  const Text(
                    'No inspections yet',
                    style: TextStyle(
                      fontSize: 16,
                      fontWeight: FontWeight.w600,
                      color: Color(0xFF303835),
                    ),
                  ),

                  const SizedBox(height: 5),

                  const Text(
                    'Your scanned products will appear here.',
                    textAlign: TextAlign.center,
                    style: TextStyle(fontSize: 13, color: Color(0xFF7B8380)),
                  ),
                ],
              ),
            ),
          ],
        ),
      ),
    );
  }

  Widget _statCard({
    required IconData icon,
    required String number,
    required String label,
    required Color iconColor,
    required VoidCallback onTap,
  }) {
    return InkWell(
      onTap: onTap,
      borderRadius: BorderRadius.circular(17),
      child: Container(
        padding: const EdgeInsets.all(17),
        decoration: BoxDecoration(
          color: Colors.white,
          borderRadius: BorderRadius.circular(17),
        ),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Icon(icon, color: iconColor, size: 26),

            const SizedBox(height: 13),

            Text(
              number,
              style: const TextStyle(
                fontSize: 25,
                fontWeight: FontWeight.w700,
                color: Color(0xFF17201D),
              ),
            ),

            const SizedBox(height: 2),

            Text(
              label,
              style: const TextStyle(fontSize: 13, color: Color(0xFF737B77)),
            ),
          ],
        ),
      ),
    );
  }
}

class RecordsScreen extends StatelessWidget {
  const RecordsScreen({
    super.key,
    required this.title,
    this.showViolations = false,
  });

  final String title;
  final bool showViolations;

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: const Color(0xFFF7F7F3),
      appBar: AppBar(
        title: Text(title),
        backgroundColor: const Color(0xFFF7F7F3),
      ),
      body: Center(
        child: Padding(
          padding: const EdgeInsets.all(24),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              Icon(
                showViolations
                    ? Icons.check_circle_outline_rounded
                    : Icons.assignment_outlined,
                size: 58,
                color: const Color(0xFF68716D),
              ),
              const SizedBox(height: 16),
              Text(
                showViolations ? 'No violations yet' : 'No inspections yet',
                style: const TextStyle(
                  fontSize: 18,
                  fontWeight: FontWeight.w700,
                  color: Color(0xFF303835),
                ),
              ),
              const SizedBox(height: 8),
              Text(
                showViolations
                    ? 'Products with possible issues will appear here.'
                    : 'Your scanned products will appear here after analysis.',
                textAlign: TextAlign.center,
                style: const TextStyle(color: Color(0xFF7B8380)),
              ),
            ],
          ),
        ),
      ),
    );
  }
}

class ProfileScreen extends StatelessWidget {
  const ProfileScreen({super.key});

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: const Color(0xFFF7F7F3),
      appBar: AppBar(
        title: const Text('Profile'),
        backgroundColor: const Color(0xFFF7F7F3),
      ),
      body: ListView(
        padding: const EdgeInsets.all(20),
        children: [
          Container(
            padding: const EdgeInsets.all(20),
            decoration: BoxDecoration(
              color: Colors.white,
              borderRadius: BorderRadius.circular(18),
            ),
            child: const Row(
              children: [
                CircleAvatar(
                  radius: 28,
                  backgroundColor: Color(0xFFEAF4EF),
                  child: Icon(Icons.person_rounded, color: Color(0xFF183B32)),
                ),
                SizedBox(width: 14),
                Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      'LegalCheck User',
                      style: TextStyle(
                        fontSize: 17,
                        fontWeight: FontWeight.w700,
                      ),
                    ),
                    SizedBox(height: 4),
                    Text(
                      'Product inspector',
                      style: TextStyle(color: Color(0xFF68716D)),
                    ),
                  ],
                ),
              ],
            ),
          ),
          const SizedBox(height: 16),
          Card(
            elevation: 0,
            color: Colors.white,
            child: ListTile(
              leading: const Icon(
                Icons.history_rounded,
                color: Color(0xFF183B32),
              ),
              title: const Text('Inspection history'),
              subtitle: const Text('Review your previous inspections'),
              trailing: const Icon(Icons.chevron_right_rounded),
              onTap: () {
                Navigator.push(
                  context,
                  MaterialPageRoute(
                    builder: (_) =>
                        const RecordsScreen(title: 'Inspection History'),
                  ),
                );
              },
            ),
          ),
        ],
      ),
    );
  }
}

// ======================================================
// SCAN SCREEN
// ======================================================

class AnalysisResultScreen extends StatelessWidget {
  const AnalysisResultScreen({
    super.key,
    required this.analysis,
    required this.ocrText,
    this.primaryImage,
    this.imageUrl,
  });

  final ComplianceAnalysis analysis;
  final String ocrText;
  final XFile? primaryImage;
  final String? imageUrl;

  Future<void> _saveReport(BuildContext context) async {
    try {
      await SupabaseService().saveInspectionReport(
        analysis: analysis,
        ocrText: ocrText,
        primaryImage: primaryImage,
        imageUrl: imageUrl,
      );

      if (!context.mounted) return;
      ScaffoldMessenger.of(
        context,
      ).showSnackBar(const SnackBar(content: Text('Inspection report saved.')));
    } catch (error) {
      if (!context.mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text('Could not save inspection report: $error')),
      );
    }
  }

  @override
  Widget build(BuildContext context) {
    final productName = analysis.productName.isNotEmpty
        ? analysis.productName
        : 'Unknown Product';
    final hasMissing = analysis.missingInformation.isNotEmpty;
    final hasIssues = analysis.possibleIssues.isNotEmpty;

    return Scaffold(
      backgroundColor: const Color(0xFFF7F7F3),
      appBar: AppBar(
        title: const Text('Product Analysis'),
        backgroundColor: const Color(0xFFF7F7F3),
      ),
      body: SafeArea(
        child: SingleChildScrollView(
          padding: const EdgeInsets.fromLTRB(20, 12, 20, 28),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Center(
                child: Text(
                  'PRODUCT ANALYSIS',
                  style: TextStyle(
                    fontSize: 18,
                    fontWeight: FontWeight.w800,
                    letterSpacing: 1,
                    color: Colors.grey.shade800,
                  ),
                ),
              ),
              const SizedBox(height: 18),
              Center(
                child: Text(
                  productName.toUpperCase(),
                  textAlign: TextAlign.center,
                  style: const TextStyle(
                    fontSize: 28,
                    fontWeight: FontWeight.w800,
                    color: Color(0xFF183B32),
                  ),
                ),
              ),
              const SizedBox(height: 22),
              const Text(
                'Product Details',
                style: TextStyle(
                  fontSize: 18,
                  fontWeight: FontWeight.w700,
                  color: Color(0xFF17201D),
                ),
              ),
              const SizedBox(height: 10),
              Container(
                width: double.infinity,
                padding: const EdgeInsets.all(18),
                decoration: BoxDecoration(
                  color: Colors.white,
                  borderRadius: BorderRadius.circular(18),
                  boxShadow: const [
                    BoxShadow(
                      color: Color(0x11000000),
                      blurRadius: 6,
                      offset: Offset(0, 2),
                    ),
                  ],
                ),
                child: Column(
                  children: [
                    _detailRow(
                      'MRP',
                      analysis.mrp.isNotEmpty ? analysis.mrp : 'Not Found',
                    ),
                    const Divider(height: 1, color: Color(0xFFE6E8E3)),
                    _detailRow(
                      'Net Quantity',
                      analysis.netQuantity.isNotEmpty
                          ? analysis.netQuantity
                          : 'Not Found',
                    ),
                    const Divider(height: 1, color: Color(0xFFE6E8E3)),
                    _detailRow(
                      'Manufacturer',
                      analysis.manufacturer.isNotEmpty
                          ? analysis.manufacturer
                          : 'Not Found',
                    ),
                    const Divider(height: 1, color: Color(0xFFE6E8E3)),
                    _detailRow(
                      'Address',
                      analysis.address.isNotEmpty
                          ? analysis.address
                          : 'Not Found',
                    ),
                    const Divider(height: 1, color: Color(0xFFE6E8E3)),
                    _detailRow(
                      'Packing Date',
                      analysis.packingDate.isNotEmpty
                          ? analysis.packingDate
                          : 'Not Found',
                    ),
                    const Divider(height: 1, color: Color(0xFFE6E8E3)),
                    _detailRow(
                      'Customer Care',
                      analysis.customerCare.isNotEmpty
                          ? analysis.customerCare
                          : 'Not Found',
                    ),
                  ],
                ),
              ),
              const SizedBox(height: 24),
              if (hasMissing)
                _warningSection(
                  title: 'Information Missing',
                  items: analysis.missingInformation,
                  icon: Icons.warning_amber_rounded,
                  color: const Color(0xFFFFF1D9),
                ),
              if (hasIssues)
                _issueWarningSection(
                  title: 'Possible Issues',
                  issues: analysis.possibleIssues,
                  icon: Icons.error_outline_rounded,
                  color: const Color(0xFFFDECEA),
                ),
              if (!hasMissing && !hasIssues)
                Container(
                  width: double.infinity,
                  padding: const EdgeInsets.all(16),
                  decoration: BoxDecoration(
                    color: const Color(0xFFEAF4EF),
                    borderRadius: BorderRadius.circular(16),
                  ),
                  child: const Text(
                    'No major compliance issues were detected from the available OCR data.',
                    style: TextStyle(
                      fontSize: 14,
                      color: Color(0xFF183B32),
                      fontWeight: FontWeight.w600,
                    ),
                  ),
                ),
              const SizedBox(height: 18),
              SizedBox(
                width: double.infinity,
                height: 52,
                child: ElevatedButton.icon(
                  onPressed: () => _saveReport(context),
                  icon: const Icon(Icons.cloud_upload_outlined),
                  label: const Text('Save Inspection Report'),
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }

  Widget _detailRow(String label, String value) {
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 10),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          SizedBox(
            width: 120,
            child: Text(
              label,
              style: const TextStyle(
                fontSize: 12,
                fontWeight: FontWeight.w600,
                color: Color(0xFF68716D),
              ),
            ),
          ),
          Expanded(
            child: Text(
              value,
              style: const TextStyle(
                fontSize: 14,
                fontWeight: FontWeight.w600,
                color: Color(0xFF17201D),
                height: 1.4,
              ),
            ),
          ),
        ],
      ),
    );
  }

  Widget _warningSection({
    required String title,
    required List<String> items,
    required IconData icon,
    required Color color,
  }) {
    return Container(
      width: double.infinity,
      margin: const EdgeInsets.only(bottom: 18),
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: color,
        borderRadius: BorderRadius.circular(16),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(
            title,
            style: const TextStyle(
              fontSize: 18,
              fontWeight: FontWeight.w700,
              color: Color(0xFF17201D),
            ),
          ),
          const SizedBox(height: 10),
          ...items.map((item) {
            return Padding(
              padding: const EdgeInsets.only(bottom: 8),
              child: Row(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Icon(icon, size: 18, color: const Color(0xFF9F4B16)),
                  const SizedBox(width: 8),
                  Expanded(
                    child: Text(
                      item,
                      style: const TextStyle(
                        fontSize: 14,
                        height: 1.5,
                        color: Color(0xFF2F3633),
                      ),
                    ),
                  ),
                ],
              ),
            );
          }),
        ],
      ),
    );
  }

  Widget _issueWarningSection({
    required String title,
    required List<ComplianceIssue> issues,
    required IconData icon,
    required Color color,
  }) {
    return Container(
      width: double.infinity,
      margin: const EdgeInsets.only(bottom: 18),
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: color,
        borderRadius: BorderRadius.circular(16),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(
            title,
            style: const TextStyle(
              fontSize: 18,
              fontWeight: FontWeight.w700,
              color: Color(0xFF17201D),
            ),
          ),
          const SizedBox(height: 10),
          ...issues.map((issue) {
            final issueTitle = issue.title.isNotEmpty ? issue.title : 'Issue';
            final ruleNumbers = issue.ruleNumbers
                .where((rule) => rule.trim().isNotEmpty)
                .toList();
            final ruleTitles = issue.ruleTitles
                .where((rule) => rule.trim().isNotEmpty)
                .toList();
            final hasLegalReference = ruleNumbers.isNotEmpty || ruleTitles.isNotEmpty;
            final hasLegalBasis = (issue.legalBasis ?? '').trim().isNotEmpty;
            final hasEvidence = (issue.ocrEvidence ?? '').trim().isNotEmpty;

            return Padding(
              padding: const EdgeInsets.only(bottom: 12),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  _verificationStatusBadge(issue.verificationStatus),
  const SizedBox(height: 8),
                  Row(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Icon(icon, size: 18, color: const Color(0xFF9F4B16)),
                      const SizedBox(width: 8),
                      Expanded(
                        child: Text(
                          '$issueTitle: ${issue.description}',
                          style: const TextStyle(
                            fontSize: 14,
                            height: 1.5,
                            color: Color(0xFF2F3633),
                          ),
                        ),
                      ),
                    ],
                  ),
                  if (hasLegalReference || hasLegalBasis || hasEvidence) ...[
                    const SizedBox(height: 8),
                    Container(
                      width: double.infinity,
                      padding: const EdgeInsets.all(10),
                      decoration: BoxDecoration(
                        color: Colors.white.withValues(alpha: 0.35),
                        borderRadius: BorderRadius.circular(10),
                      ),
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          const Text(
                            'Legal Reference',
                            style: TextStyle(
                              fontSize: 12,
                              fontWeight: FontWeight.w700,
                              color: Color(0xFF183B32),
                            ),
                          ),
                          if (hasLegalReference) ...[
                            _legalReferenceRow(
                              label: 'Rule Number(s):',
                              value: ruleNumbers.join(', '),
                            ),
                            _legalReferenceRow(
                              label: 'Rule Title(s):',
                              value: ruleTitles.join(', '),
                            ),
                          ],
                          if (hasLegalBasis)
                            _legalReferenceRow(
                              label: 'Legal Basis:',
                              value: issue.legalBasis!,
                            ),
                          if (hasEvidence)
                            _legalReferenceRow(
                              label: 'OCR Evidence:',
                              value: issue.ocrEvidence!,
                            ),
                        ],
                      ),
                    ),
                  ],
                ],
              ),
            );
          }),
        ],
      ),
    );
  }Widget _verificationStatusBadge(
  LegalVerificationStatus status,
) {
  String label;
  Color backgroundColor;
  Color textColor;
  IconData statusIcon;

  switch (status) {
    case LegalVerificationStatus.legallyVerified:
      label = 'LEGALLY VERIFIED VIOLATION';
      backgroundColor = const Color(0xFFFDECEA);
      textColor = const Color(0xFFB3261E);
      statusIcon = Icons.verified_rounded;
      break;

    case LegalVerificationStatus.possibleConcern:
      label = 'POSSIBLE LEGAL CONCERN';
      backgroundColor = const Color(0xFFFFF3E0);
      textColor = const Color(0xFF9F4B16);
      statusIcon = Icons.warning_amber_rounded;
      break;

    case LegalVerificationStatus.cannotDetermine:
      label = 'CANNOT DETERMINE';
      backgroundColor = const Color(0xFFE8F0FE);
      textColor = const Color(0xFF1A73E8);
      statusIcon = Icons.help_outline_rounded;
      break;

    case LegalVerificationStatus.generalObservation:
      label = 'GENERAL OBSERVATION';
      backgroundColor = const Color(0xFFF1F3F4);
      textColor = const Color(0xFF5F6368);
      statusIcon = Icons.visibility_outlined;
      break;
  }

  return Container(
    padding: const EdgeInsets.symmetric(
      horizontal: 10,
      vertical: 6,
    ),
    decoration: BoxDecoration(
      color: backgroundColor,
      borderRadius: BorderRadius.circular(8),
    ),
    child: Row(
      mainAxisSize: MainAxisSize.min,
      children: [
        Icon(
          statusIcon,
          size: 16,
          color: textColor,
        ),
        const SizedBox(width: 6),
        Text(
          label,
          style: TextStyle(
            fontSize: 11,
            fontWeight: FontWeight.w700,
            color: textColor,
          ),
        ),
      ],
    ),
  );
}

  Widget _legalReferenceRow({
    required String label,
    required String value,
  }) {
    return Padding(
      padding: const EdgeInsets.only(bottom: 6),
      child: RichText(
        text: TextSpan(
          style: const TextStyle(
            fontSize: 12,
            height: 1.55,
            color: Color(0xFF2F3633),
          ),
          children: [
            TextSpan(
              text: '$label ',
              style: const TextStyle(fontWeight: FontWeight.w700),
            ),
            TextSpan(text: value),
          ],
        ),
      ),
    );
  }
}

class ScanScreen extends StatefulWidget {
  const ScanScreen({super.key});

  @override
  State<ScanScreen> createState() => _ScanScreenState();
}

class _ScanScreenState extends State<ScanScreen> {
  final ImagePicker _picker = ImagePicker();
  final TextRecognizer _textRecognizer = TextRecognizer();
  final GeminiAIAnalysisService _aiAnalysisService = GeminiAIAnalysisService(
    apiKey: const String.fromEnvironment('GEMINI_API_KEY', defaultValue: ''),
  );
  final LegalRulesRetrievalService _legalRulesRetrievalService =
      LegalRulesRetrievalService();
  final List<XFile> _capturedImages = [];
  final Map<String, String> _ocrResultsByImagePath = {};
  String extractedText = 'No text detected yet.';
  bool _isProcessingOcr = false;
  bool _isAnalyzing = false;

  Future<void> runOcrOnImage(XFile image) async {
    try {
      setState(() {
        _isProcessingOcr = true;
      });

      final inputImage = InputImage.fromFilePath(image.path);
      final recognizedText = await _textRecognizer.processImage(inputImage);

      final text = recognizedText.text.trim();

      if (!mounted) return;

      setState(() {
        extractedText = text.isNotEmpty
            ? text
            : 'No text detected in this image.';
        _ocrResultsByImagePath[image.path] = extractedText;
        _isProcessingOcr = false;
      });
      debugPrint(
        'OCR result collected for ${image.path}: ${extractedText.length} characters',
      );
    } catch (e) {
      if (!mounted) return;

      setState(() {
        extractedText = 'OCR failed for this image.';
        _ocrResultsByImagePath[image.path] = extractedText;
        _isProcessingOcr = false;
      });
      debugPrint('OCR failed for ${image.path}: $e');
    }
  }

  Future<void> analyzeProduct() async {
    if (_isAnalyzing) {
      return;
    }

    if (_capturedImages.isEmpty) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(
            content: Text(
              'Please capture a product image with readable label text first.',
            ),
            behavior: SnackBarBehavior.floating,
          ),
        );
      }
      return;
    }

    debugPrint('Images captured for analysis: ${_capturedImages.length}');

    setState(() {
      _isAnalyzing = true;
    });

    try {
      for (final image in _capturedImages) {
        await runOcrOnImage(image);
      }

      final combinedText = _capturedImages
          .asMap()
          .entries
          .map((entry) {
            final imageNumber = entry.key + 1;
            final image = entry.value;
            final imageText =
                _ocrResultsByImagePath[image.path] ??
                'No OCR result collected for this image.';
            return '===== IMAGE $imageNumber =====\n$imageText';
          })
          .join('\n\n');

      debugPrint(
        'OCR results collected: ${_ocrResultsByImagePath.length} of '
        '${_capturedImages.length} images',
      );
      debugPrint(
        'Sending combined OCR text for analysis: ${combinedText.length} characters',
      );

      var legalContext = '';
      try {
        final retrievedRules =
            await _legalRulesRetrievalService.retrieveLegalContext(
          combinedText,
        );
        legalContext = retrievedRules.formatted;
        debugPrint(
          'RAG: legal context included in Gemini analysis = '
          '${legalContext.isNotEmpty}',
        );
      } catch (error, stackTrace) {
        debugPrint('RAG: retrieval failed; using Gemini fallback = $error');
        debugPrintStack(stackTrace: stackTrace);
      }

      final result = await _aiAnalysisService.analyzeProductLabel(
        combinedText,
        legalContext: legalContext,
      );

      if (!mounted) return;

      Navigator.push(
        context,
        MaterialPageRoute(
          builder: (_) => AnalysisResultScreen(
            analysis: result,
            ocrText: combinedText,
            primaryImage: _capturedImages.first,
          ),
        ),
      );
    } on AIAnalysisException catch (e) {
      if (!mounted) return;

      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text(e.message), behavior: SnackBarBehavior.floating),
      );
    } catch (e) {
      if (!mounted) return;

      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(
          content: Text(
            'Something went wrong while analyzing the product. Please try again.',
          ),
          behavior: SnackBarBehavior.floating,
        ),
      );
    } finally {
      if (mounted) {
        setState(() {
          _isAnalyzing = false;
        });
      }
    }
  }

  Future<void> captureImage() async {
    try {
      final XFile? image = await _picker.pickImage(
        source: ImageSource.camera,
        preferredCameraDevice: CameraDevice.rear,
        imageQuality: 85,
      );

      if (image == null) {
        print('CAMERA CANCELLED');
        return;
      }

      setState(() {
        _capturedImages.add(image);
      });

      await runOcrOnImage(image);

      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(
            content: Text('Image captured. Capture the next image.'),
            behavior: SnackBarBehavior.floating,
          ),
        );
      }

      print('IMAGE CAPTURED: ${image.path}');
    } catch (e) {
      print('CAMERA ERROR: $e');
    }
  }

  @override
  void dispose() {
    _textRecognizer.close();
    _aiAnalysisService.dispose();
    _legalRulesRetrievalService.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final previewImage = _capturedImages.isEmpty ? null : _capturedImages.last;

    return Scaffold(
      body: SafeArea(
        child: Padding(
          padding: const EdgeInsets.all(20),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              const Text(
                'Capture product images',
                style: TextStyle(
                  fontSize: 26,
                  fontWeight: FontWeight.w700,
                  color: Color(0xFF17201D),
                ),
              ),
              const SizedBox(height: 18),
              Expanded(
                child: Container(
                  width: double.infinity,
                  decoration: BoxDecoration(
                    color: const Color(0xFF202522),
                    borderRadius: BorderRadius.circular(22),
                  ),
                  clipBehavior: Clip.antiAlias,
                  child: previewImage != null
                      ? FutureBuilder<Uint8List>(
                          future: previewImage.readAsBytes(),
                          builder: (context, snapshot) {
                            if (!snapshot.hasData) {
                              return const Center(
                                child: CircularProgressIndicator(),
                              );
                            }
                            return Image.memory(
                              snapshot.data!,
                              fit: BoxFit.cover,
                              width: double.infinity,
                              height: double.infinity,
                            );
                          },
                        )
                      : Column(
                          mainAxisAlignment: MainAxisAlignment.center,
                          children: [
                            Container(
                              height: 76,
                              width: 76,
                              decoration: BoxDecoration(
                                color: Colors.white.withValues(alpha: 0.08),
                                shape: BoxShape.circle,
                              ),
                              child: const Icon(
                                Icons.camera_alt_outlined,
                                color: Colors.white,
                                size: 38,
                              ),
                            ),
                            const SizedBox(height: 18),
                            const Text(
                              'Ready for the next image',
                              style: TextStyle(
                                color: Colors.white,
                                fontSize: 17,
                                fontWeight: FontWeight.w600,
                              ),
                            ),
                            const SizedBox(height: 7),
                            const Text(
                              'Position the product inside the frame',
                              style: TextStyle(
                                color: Color(0xFFB7BFBB),
                                fontSize: 13,
                              ),
                            ),
                          ],
                        ),
                ),
              ),
              const SizedBox(height: 18),
              if (_capturedImages.isNotEmpty)
                Padding(
                  padding: const EdgeInsets.only(bottom: 16),
                  child: Text(
                    'Images captured: ${_capturedImages.length}',
                    style: const TextStyle(
                      color: Color(0xFF183B32),
                      fontWeight: FontWeight.w600,
                    ),
                  ),
                ),
              Container(
                width: double.infinity,
                padding: const EdgeInsets.all(12),
                decoration: BoxDecoration(
                  color: const Color(0xFFF5F6F5),
                  borderRadius: BorderRadius.circular(12),
                ),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    const Text(
                      'OCR result',
                      style: TextStyle(
                        fontSize: 12,
                        fontWeight: FontWeight.w700,
                        color: Color(0xFF183B32),
                        letterSpacing: 0.5,
                      ),
                    ),
                    const SizedBox(height: 8),
                    if (_isProcessingOcr)
                      const Row(
                        children: [
                          SizedBox(
                            width: 14,
                            height: 14,
                            child: CircularProgressIndicator(strokeWidth: 2),
                          ),
                          SizedBox(width: 8),
                          Text('Reading product text...'),
                        ],
                      )
                    else
                      ConstrainedBox(
                        constraints: const BoxConstraints(maxHeight: 120),
                        child: SingleChildScrollView(
                          child: Text(
                            extractedText,
                            style: const TextStyle(
                              fontSize: 13,
                              color: Color(0xFF2F3633),
                              height: 1.5,
                            ),
                          ),
                        ),
                      ),
                  ],
                ),
              ),
              const SizedBox(height: 16),
              SizedBox(
                width: double.infinity,
                height: 54,
                child: ElevatedButton.icon(
                  onPressed:
                      (!_isAnalyzing &&
                          !_isProcessingOcr &&
                          _capturedImages.isNotEmpty)
                      ? analyzeProduct
                      : null,
                  icon: _isAnalyzing
                      ? const SizedBox(
                          width: 18,
                          height: 18,
                          child: CircularProgressIndicator(
                            strokeWidth: 2,
                            valueColor: AlwaysStoppedAnimation<Color>(
                              Colors.white,
                            ),
                          ),
                        )
                      : const Icon(Icons.smart_toy_outlined),
                  label: Text(
                    _isAnalyzing ? 'Analyzing product...' : 'Analyze Product',
                    style: const TextStyle(
                      fontSize: 16,
                      fontWeight: FontWeight.w700,
                    ),
                  ),
                  style: ElevatedButton.styleFrom(
                    backgroundColor: const Color(0xFF183B32),
                    foregroundColor: Colors.white,
                    elevation: 0,
                    shape: RoundedRectangleBorder(
                      borderRadius: BorderRadius.circular(14),
                    ),
                  ),
                ),
              ),
              const SizedBox(height: 12),
              SizedBox(
                width: double.infinity,
                height: 54,
                child: ElevatedButton.icon(
                  onPressed: captureImage,
                  icon: const Icon(Icons.camera_alt_rounded),
                  label: const Text(
                    'Capture Next Image',
                    style: TextStyle(fontSize: 16, fontWeight: FontWeight.w700),
                  ),
                  style: ElevatedButton.styleFrom(
                    backgroundColor: const Color(0xFF183B32),
                    foregroundColor: Colors.white,
                    elevation: 0,
                    shape: RoundedRectangleBorder(
                      borderRadius: BorderRadius.circular(14),
                    ),
                  ),
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}
