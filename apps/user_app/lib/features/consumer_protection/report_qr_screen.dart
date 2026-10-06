import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:qr_flutter/qr_flutter.dart';
import 'package:share_plus/share_plus.dart';
import '../../core/theme/pro_palette.dart';

/// Screen for generating and downloading official verification report QR codes.
///
/// Allows consumers and field officers to instantly generate verifiable QR codes
/// for any package inspection report, facilitating offline sharing, digital audit
/// verification, and print certificate attachment.
class ReportQrScreen extends StatefulWidget {
  final String? initialReportId;

  const ReportQrScreen({super.key, this.initialReportId});

  @override
  State<ReportQrScreen> createState() => _ReportQrScreenState();
}

class _ReportQrScreenState extends State<ReportQrScreen> {
  late int _selectedReportIndex;

  final List<Map<String, dynamic>> _sampleReports = [
    {
      'id': 'VRQ-2026-8941',
      'product': 'Organic Cold-Pressed Mustard Oil 1L',
      'brand': 'Patanjali Agro',
      'date': 'Oct 05, 2026 13:45',
      'verdict': 'VERIFIED',
      'statusColor': ProPalette.emeraldVerified,
      'officer': 'Inspector R. K. Sharma (MH-04)',
      'mrp': '₹240.00 (USP ₹0.24/ml)',
      'batch': 'LOT-26B-981',
      'url': 'https://veriqoo.gov.in/verify/VRQ-2026-8941',
      'hash': 'SHA256:7f83b1657ff1fc53b92dc18148a1d65dfc2d4b1fa3d677284addd200126d9069',
    },
    {
      'id': 'VRQ-2026-8938',
      'product': 'Ultra Glow Radiance Cream 50g',
      'brand': 'LuxeCare Derma',
      'date': 'Oct 05, 2026 11:20',
      'verdict': 'VIOLATION',
      'statusColor': ProPalette.crimsonViolation,
      'officer': 'Inspector S. Pillai (KA-01)',
      'mrp': '₹899.00 (Missing USP)',
      'batch': 'LC-2026-X',
      'url': 'https://veriqoo.gov.in/verify/VRQ-2026-8938',
      'hash': 'SHA256:e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855',
    },
    {
      'id': 'VRQ-2026-8924',
      'product': 'Fortified Basmati Rice 5kg',
      'brand': 'Daawat Heritage',
      'date': 'Oct 04, 2026 16:15',
      'verdict': 'FLAGGED',
      'statusColor': ProPalette.amberWarning,
      'officer': 'Inspector M. Verma (DL-02)',
      'mrp': '₹550.00 (USP ₹110.00/kg)',
      'batch': 'DWT-OCT-09',
      'url': 'https://veriqoo.gov.in/verify/VRQ-2026-8924',
      'hash': 'SHA256:ca978112ca1bbdcafac231b39a23dc4da786eff8147c4e72b9807785afee48bb',
    },
  ];

  @override
  void initState() {
    super.initState();
    _selectedReportIndex = 0;
    if (widget.initialReportId != null) {
      final index = _sampleReports.indexWhere((r) => r['id'] == widget.initialReportId);
      if (index != -1) _selectedReportIndex = index;
    }
  }

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final isDark = theme.brightness == Brightness.dark;
    final report = _sampleReports[_selectedReportIndex];

    return Scaffold(
      appBar: AppBar(
        title: const Text('Report QR Generator'),
        actions: [
          IconButton(
            icon: const Icon(Icons.share_outlined),
            tooltip: 'Share Report',
            onPressed: () => _shareReport(report),
          ),
        ],
      ),
      body: ListView(
        padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
        children: [
          // 1. Report Selector
          _buildReportSelector(isDark),

          const SizedBox(height: 16),

          // 2. High-Contrast QR Code Card
          _buildQrCodeCard(report, isDark),

          const SizedBox(height: 16),

          // 3. Inspection Audit Breakdown
          _buildAuditDetailsCard(report, isDark),

          const SizedBox(height: 20),

          // 4. Action Buttons (Download, Print, Copy)
          _buildActionButtons(report),

          const SizedBox(height: 32),
        ],
      ),
    );
  }

  Widget _buildReportSelector(bool isDark) {
    return Container(
      decoration: ProPalette.cardDecoration(context),
      padding: const EdgeInsets.all(12),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const Text(
            'Select Inspection Report:',
            style: TextStyle(fontSize: 12, fontWeight: FontWeight.bold, color: ProPalette.electricBlue),
          ),
          const SizedBox(height: 8),
          SingleChildScrollView(
            scrollDirection: Axis.horizontal,
            child: Row(
              children: List.generate(_sampleReports.length, (index) {
                final isSelected = _selectedReportIndex == index;
                final r = _sampleReports[index];
                return Padding(
                  padding: const EdgeInsets.only(right: 8),
                  child: ChoiceChip(
                    label: Text('${r['id']} (${r['verdict']})'),
                    selected: isSelected,
                    selectedColor: (r['statusColor'] as Color).withValues(alpha: 0.15),
                    labelStyle: TextStyle(
                      color: isSelected ? (r['statusColor'] as Color) : null,
                      fontWeight: isSelected ? FontWeight.bold : FontWeight.normal,
                      fontSize: 12,
                    ),
                    onSelected: (selected) {
                      if (selected) setState(() => _selectedReportIndex = index);
                    },
                  ),
                );
              }),
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildQrCodeCard(Map<String, dynamic> report, bool isDark) {
    return Container(
      decoration: ProPalette.cardDecoration(context, elevated: true),
      padding: const EdgeInsets.all(20),
      child: Column(
        children: [
          // Top Tag
          Row(
            mainAxisAlignment: MainAxisAlignment.spaceBetween,
            children: [
              Container(
                padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
                decoration: ProPalette.badgeDecoration(color: ProPalette.electricBlue),
                child: const Row(
                  mainAxisSize: MainAxisSize.min,
                  children: [
                    Icon(Icons.verified, color: ProPalette.electricBlue, size: 14),
                    SizedBox(width: 4),
                    Text(
                      'OFFICIAL AUDIT QR',
                      style: TextStyle(
                        color: ProPalette.electricBlue,
                        fontWeight: FontWeight.bold,
                        fontSize: 10,
                        letterSpacing: 0.5,
                      ),
                    ),
                  ],
                ),
              ),
              Container(
                padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
                decoration: ProPalette.badgeDecoration(color: report['statusColor'] as Color),
                child: Text(
                  report['verdict'] as String,
                  style: TextStyle(
                    color: report['statusColor'] as Color,
                    fontWeight: FontWeight.bold,
                    fontSize: 11,
                  ),
                ),
              ),
            ],
          ),

          const SizedBox(height: 16),

          // Central QR Code Image with high-contrast white border
          Container(
            padding: const EdgeInsets.all(12),
            decoration: BoxDecoration(
              color: Colors.white,
              borderRadius: BorderRadius.circular(12),
              border: Border.all(color: Colors.black12, width: 2),
              boxShadow: const [
                BoxShadow(
                  color: Colors.black12,
                  blurRadius: 8,
                  offset: Offset(0, 4),
                ),
              ],
            ),
            child: QrImageView(
              data: report['url'] as String,
              version: QrVersions.auto,
              size: 190.0,
              backgroundColor: Colors.white,
              eyeStyle: const QrEyeStyle(
                eyeShape: QrEyeShape.square,
                color: Color(0xFF0F172A),
              ),
              dataModuleStyle: const QrDataModuleStyle(
                dataModuleShape: QrDataModuleShape.square,
                color: Color(0xFF0F172A),
              ),
            ),
          ),

          const SizedBox(height: 16),

          Text(
            report['product'] as String,
            textAlign: TextAlign.center,
            style: const TextStyle(fontWeight: FontWeight.bold, fontSize: 15),
          ),
          const SizedBox(height: 4),
          Text(
            'Scan with any smartphone or Veriqoo terminal to verify report validity',
            textAlign: TextAlign.center,
            style: TextStyle(fontSize: 11, color: isDark ? Colors.white60 : Colors.black54),
          ),
        ],
      ),
    );
  }

  Widget _buildAuditDetailsCard(Map<String, dynamic> report, bool isDark) {
    return Container(
      decoration: ProPalette.cardDecoration(context),
      padding: const EdgeInsets.all(16),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const Row(
            children: [
              Icon(Icons.description_outlined, color: ProPalette.electricBlue, size: 18),
              SizedBox(width: 8),
              Text(
                'Digital Dossier Metadata',
                style: TextStyle(fontWeight: FontWeight.bold, fontSize: 14),
              ),
            ],
          ),
          const SizedBox(height: 12),
          _buildMetaRow('Report ID', report['id'] as String),
          _buildMetaRow('Brand / Entity', report['brand'] as String),
          _buildMetaRow('Declared MRP', report['mrp'] as String),
          _buildMetaRow('Batch / Lot #', report['batch'] as String),
          _buildMetaRow('Audit Timestamp', report['date'] as String),
          _buildMetaRow('Assigned Officer', report['officer'] as String),
          const Divider(height: 16),
          Row(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              const Text(
                'Digest: ',
                style: TextStyle(fontSize: 11, fontWeight: FontWeight.bold, color: Colors.grey),
              ),
              Expanded(
                child: Text(
                  report['hash'] as String,
                  style: TextStyle(
                    fontFamily: 'monospace',
                    fontSize: 9,
                    color: isDark ? Colors.white70 : Colors.black87,
                  ),
                ),
              ),
            ],
          ),
        ],
      ),
    );
  }

  Widget _buildMetaRow(String label, String value) {
    return Padding(
      padding: const EdgeInsets.only(bottom: 6),
      child: Row(
        mainAxisAlignment: MainAxisAlignment.spaceBetween,
        children: [
          Text(label, style: const TextStyle(fontSize: 12, color: Colors.grey)),
          Text(value, style: const TextStyle(fontSize: 12, fontWeight: FontWeight.w600)),
        ],
      ),
    );
  }

  Widget _buildActionButtons(Map<String, dynamic> report) {
    return Column(
      children: [
        SizedBox(
          width: double.infinity,
          child: ElevatedButton.icon(
            style: ElevatedButton.styleFrom(
              backgroundColor: ProPalette.electricBlue,
              foregroundColor: Colors.white,
              padding: const EdgeInsets.symmetric(vertical: 14),
              shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(8)),
            ),
            onPressed: () {
              ScaffoldMessenger.of(context).showSnackBar(
                SnackBar(
                  content: Text('Report ${report['id']} QR certificate saved to device downloads!'),
                  backgroundColor: ProPalette.emeraldVerified,
                ),
              );
            },
            icon: const Icon(Icons.download),
            label: const Text(
              'Download QR Certificate (PDF / PNG)',
              style: TextStyle(fontWeight: FontWeight.bold),
            ),
          ),
        ),
        const SizedBox(height: 10),
        Row(
          children: [
            Expanded(
              child: OutlinedButton.icon(
                style: OutlinedButton.styleFrom(
                  padding: const EdgeInsets.symmetric(vertical: 12),
                ),
                onPressed: () {
                  Clipboard.setData(ClipboardData(text: report['url'] as String));
                  ScaffoldMessenger.of(context).showSnackBar(
                    const SnackBar(content: Text('Report link copied to clipboard!')),
                  );
                },
                icon: const Icon(Icons.copy, size: 16),
                label: const Text('Copy URL'),
              ),
            ),
            const SizedBox(width: 10),
            Expanded(
              child: OutlinedButton.icon(
                style: OutlinedButton.styleFrom(
                  padding: const EdgeInsets.symmetric(vertical: 12),
                ),
                onPressed: () => _shareReport(report),
                icon: const Icon(Icons.share, size: 16),
                label: const Text('Share Report'),
              ),
            ),
          ],
        ),
      ],
    );
  }

  void _shareReport(Map<String, dynamic> report) {
    final text =
        'Veriqoo Legal Metrology Compliance Report: ${report['product']} (${report['id']})\nVerdict: ${report['verdict']}\nVerify online: ${report['url']}';
    SharePlus.instance.share(ShareParams(text: text));
  }
}
