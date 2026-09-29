import 'dart:convert';

import 'package:flutter/material.dart';

class InspectionDetailsScreen extends StatelessWidget {
  const InspectionDetailsScreen({super.key, required this.inspection});

  final Map<String, dynamic> inspection;

  @override
  Widget build(BuildContext context) {
    final isCompliant = inspection['is_compliant'] == true;
    final productName = _text(inspection['product_name'], fallback: 'Unnamed product');
    final inspectedAt = _dateTime(inspection['inspected_at']);

    return Scaffold(
      backgroundColor: const Color(0xFFD9E8F6),
      appBar: AppBar(
        backgroundColor: Colors.transparent,
        surfaceTintColor: Colors.transparent,
        title: const Text('Inspection Report'),
        leading: IconButton(
          tooltip: 'Back to dashboard',
          onPressed: () => Navigator.of(context).pop(),
          icon: const Icon(Icons.arrow_back_rounded),
        ),
      ),
      body: SafeArea(
        child: Center(
          child: ConstrainedBox(
            constraints: const BoxConstraints(maxWidth: 1100),
            child: ListView(
              padding: const EdgeInsets.fromLTRB(22, 8, 22, 32),
              children: [
                _Header(
                  productName: productName,
                  isCompliant: isCompliant,
                  inspectedAt: inspectedAt,
                ),
                const SizedBox(height: 14),
                _ProductInformation(inspection: inspection),
                const SizedBox(height: 14),
                LayoutBuilder(
                  builder: (context, constraints) {
                    final information = _InformationSection(
                      title: 'Information Missing',
                      icon: Icons.info_outline_rounded,
                      value: _displayValue(inspection['missing_information']),
                    );
                    final issues = _InformationSection(
                      title: 'Possible Issues',
                      icon: Icons.warning_amber_rounded,
                      value: _displayValue(inspection['possible_issues']),
                      accent: const Color(0xFFB86512),
                    );
                    if (constraints.maxWidth < 680) {
                      return Column(
                        children: [information, const SizedBox(height: 14), issues],
                      );
                    }
                    return Row(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Expanded(child: information),
                        const SizedBox(width: 14),
                        Expanded(child: issues),
                      ],
                    );
                  },
                ),
                const SizedBox(height: 14),
                _ReportSection(
                  title: 'AI Compliance Report',
                  icon: Icons.auto_awesome_outlined,
                  value: _displayValue(inspection['ai_report']),
                ),
                const SizedBox(height: 14),
                _ProductImage(imageUrl: _text(inspection['image_url'])),
              ],
            ),
          ),
        ),
      ),
    );
  }
}

class _Header extends StatelessWidget {
  const _Header({required this.productName, required this.isCompliant, required this.inspectedAt});

  final String productName;
  final bool isCompliant;
  final DateTime? inspectedAt;

  @override
  Widget build(BuildContext context) {
    return _Panel(
      child: LayoutBuilder(
        builder: (context, constraints) {
          final details = Wrap(
            spacing: 18,
            runSpacing: 8,
            children: [
              _Meta(label: 'Status', value: isCompliant ? 'Compliant' : 'Violation', color: isCompliant ? const Color(0xFF1D9B5C) : const Color(0xFFD34E55)),
              _Meta(label: 'Inspected', value: _formatDateTime(inspectedAt)),
            ],
          );
          return constraints.maxWidth < 520
              ? Column(crossAxisAlignment: CrossAxisAlignment.start, children: [_Title(productName: productName, isCompliant: isCompliant), const SizedBox(height: 14), details])
              : Row(children: [Expanded(child: _Title(productName: productName, isCompliant: isCompliant)), details]);
        },
      ),
    );
  }
}

class _Title extends StatelessWidget {
  const _Title({required this.productName, required this.isCompliant});
  final String productName;
  final bool isCompliant;

  @override
  Widget build(BuildContext context) {
    return Row(
      children: [
        CircleAvatar(
          radius: 22,
          backgroundColor: isCompliant ? const Color(0xFFE6F3EA) : const Color(0xFFFFF0DD),
          child: Icon(
            isCompliant ? Icons.check_rounded : Icons.priority_high_rounded,
            color: isCompliant ? const Color(0xFF287A55) : const Color(0xFFB86512),
          ),
        ),
        const SizedBox(width: 12),
        Expanded(
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              const Text('Inspection details', style: TextStyle(fontSize: 11, color: Color(0xFF68716D))),
              const SizedBox(height: 2),
              Text(productName, maxLines: 2, overflow: TextOverflow.ellipsis, style: const TextStyle(fontSize: 22, fontWeight: FontWeight.w700, color: Color(0xFF172033)),),
            ],
          ),
        ),
      ],
    );
  }
}

class _Meta extends StatelessWidget {
  const _Meta({required this.label, required this.value, this.color});
  final String label;
  final String value;
  final Color? color;
  @override
  Widget build(BuildContext context) => Column(crossAxisAlignment: CrossAxisAlignment.start, children: [Text(label, style: const TextStyle(fontSize: 9, color: Color(0xFF8090A4))), const SizedBox(height: 3), Text(value, style: TextStyle(fontSize: 12, fontWeight: FontWeight.w700, color: color ?? const Color(0xFF172033)))]);
}

class _ProductInformation extends StatelessWidget {
  const _ProductInformation({required this.inspection});
  final Map<String, dynamic> inspection;

  @override
  Widget build(BuildContext context) {
    final fields = [
      ('MRP', inspection['mrp']),
      ('Net quantity', inspection['net_quantity']),
      ('Manufacturer', inspection['manufacturer']),
      ('Address', inspection['address']),
      ('Packing date', inspection['packing_date']),
      ('Customer care', inspection['customer_care']),
    ];
    return _ReportSection(
      title: 'Product Information',
      icon: Icons.inventory_2_outlined,
      child: LayoutBuilder(
        builder: (context, constraints) {
          final columns = constraints.maxWidth >= 760 ? 3 : constraints.maxWidth >= 440 ? 2 : 1;
          return GridView.count(
            crossAxisCount: columns,
            crossAxisSpacing: 24,
            mainAxisSpacing: 16,
            childAspectRatio: columns == 1 ? 5.5 : 3.2,
            shrinkWrap: true,
            physics: const NeverScrollableScrollPhysics(),
            children: fields.map((field) => _Field(label: field.$1, value: _text(field.$2))).toList(),
          );
        },
      ),
    );
  }
}

class _Field extends StatelessWidget {
  const _Field({required this.label, required this.value});
  final String label;
  final String value;
  @override
  Widget build(BuildContext context) => Column(crossAxisAlignment: CrossAxisAlignment.start, children: [Text(label, style: const TextStyle(fontSize: 9, color: Color(0xFF8090A4))), const SizedBox(height: 4), Text(value, maxLines: 3, overflow: TextOverflow.ellipsis, style: const TextStyle(fontSize: 12, color: Color(0xFF344054), fontWeight: FontWeight.w600))]);
}

class _InformationSection extends StatelessWidget {
  const _InformationSection({required this.title, required this.icon, required this.value, this.accent});
  final String title;
  final IconData icon;
  final String value;
  final Color? accent;
  @override
  Widget build(BuildContext context) => _ReportSection(title: title, icon: icon, value: value, accent: accent);
}

class _ReportSection extends StatelessWidget {
  const _ReportSection({required this.title, required this.icon, this.value, this.child, this.accent});
  final String title;
  final IconData icon;
  final String? value;
  final Widget? child;
  final Color? accent;

  @override
  Widget build(BuildContext context) => _Panel(child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [Row(children: [Icon(icon, size: 17, color: accent ?? const Color(0xFF2964D8)), const SizedBox(width: 7), Text(title, style: const TextStyle(fontSize: 13, fontWeight: FontWeight.w700, color: Color(0xFF172033)))]), const SizedBox(height: 12), child ?? Text(value ?? 'Not available', style: const TextStyle(fontSize: 12, height: 1.45, color: Color(0xFF344054)))]));
}

class _ProductImage extends StatelessWidget {
  const _ProductImage({required this.imageUrl});
  final String imageUrl;

  @override
  Widget build(BuildContext context) {
    final uri = Uri.tryParse(imageUrl);
    final valid = uri != null && (uri.scheme == 'http' || uri.scheme == 'https') && uri.host.isNotEmpty;
    return _Panel(child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [const Row(children: [Icon(Icons.image_outlined, size: 17, color: Color(0xFF2964D8)), SizedBox(width: 7), Text('Product Image', style: TextStyle(fontSize: 13, fontWeight: FontWeight.w700, color: Color(0xFF172033)))]), const SizedBox(height: 12), ClipRRect(borderRadius: BorderRadius.circular(7), child: valid ? Image.network(imageUrl, height: 220, width: double.infinity, fit: BoxFit.contain, errorBuilder: (_, error, stackTrace) => const _UnavailableImage()) : const _UnavailableImage())]));
  }
}

class _UnavailableImage extends StatelessWidget {
  const _UnavailableImage();
  @override
  Widget build(BuildContext context) => Container(height: 180, width: double.infinity, color: const Color(0xFFF3F6F9), child: const Column(mainAxisAlignment: MainAxisAlignment.center, children: [Icon(Icons.image_not_supported_outlined, size: 38, color: Color(0xFF8090A4)), SizedBox(height: 8), Text('Image unavailable', style: TextStyle(fontSize: 12, color: Color(0xFF68716D)))]));
}

class _Panel extends StatelessWidget {
  const _Panel({required this.child});
  final Widget child;
  @override
  Widget build(BuildContext context) => Container(padding: const EdgeInsets.all(16), decoration: BoxDecoration(color: Colors.white, borderRadius: BorderRadius.circular(9), border: Border.all(color: const Color(0xFFB9D0E6))), child: child);
}

String _text(Object? value, {String fallback = 'Not available'}) {
  if (value == null) return fallback;
  final text = value.toString().trim();
  return text.isEmpty ? fallback : text;
}

String _displayValue(Object? value) {
  if (value == null) return 'Not available';
  if (value is String) return value.trim().isEmpty ? 'Not available' : value;
  if (value is Map || value is List) return const JsonEncoder.withIndent('  ').convert(value);
  return _text(value);
}

DateTime? _dateTime(Object? value) => DateTime.tryParse(value?.toString() ?? '');

String _formatDateTime(DateTime? value) => value == null ? 'Not available' : '${value.day.toString().padLeft(2, '0')}/${value.month.toString().padLeft(2, '0')}/${value.year} ${value.hour.toString().padLeft(2, '0')}:${value.minute.toString().padLeft(2, '0')}';
