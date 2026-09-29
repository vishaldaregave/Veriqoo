import 'dart:convert';

import 'package:flutter/material.dart';
import 'package:supabase_flutter/supabase_flutter.dart';

import 'inspection_details_screen.dart';

class ProductsScreen extends StatefulWidget {
  const ProductsScreen({super.key});
  @override
  State<ProductsScreen> createState() => _ProductsScreenState();
}

class _ProductsScreenState extends State<ProductsScreen> {
  static const pageSize = 10;
  late Future<List<_Product>> future;
  final search = TextEditingController();
  String filter = 'All';
  int page = 0;

  @override
  void initState() {
    super.initState();
    future = loadProducts();
    search.addListener(() => setState(() => page = 0));
  }

  @override
  void dispose() {
    search.dispose();
    super.dispose();
  }

  Future<List<_Product>> loadProducts() async {
    final result = await Supabase.instance.client
        .from('inspections')
        .select(
          'product_name, mrp, net_quantity, manufacturer, address, packing_date, customer_care, ai_report, image_url, inspected_at, is_compliant, missing_information, possible_issues',
        )
        .order('inspected_at', ascending: false)
        .limit(500);
    final grouped = <String, _Product>{};
    for (final record in List<Map<String, dynamic>>.from(result)) {
      final name = value(record['product_name'], 'Unnamed product');
      final maker = value(record['manufacturer'], 'Manufacturer unavailable');
      final key = '${name.toLowerCase()}|${maker.toLowerCase()}';
      final old = grouped[key];
      grouped[key] = old == null
          ? _Product(
              name: name,
              maker: maker,
              count: 1,
              issues: issueCount(record['possible_issues']),
              latest: record,
            )
          : old.copy(
              count: old.count + 1,
              issues: old.issues + issueCount(record['possible_issues']),
            );
    }
    return grouped.values.toList();
  }

  List<_Product> filtered(List<_Product> products) {
    final term = search.text.trim().toLowerCase();
    return products.where((product) {
      final textMatch =
          term.isEmpty ||
          product.name.toLowerCase().contains(term) ||
          product.maker.toLowerCase().contains(term);
      final compliant = product.latest['is_compliant'] == true;
      final statusMatch =
          filter == 'All' || (filter == 'Compliant' ? compliant : !compliant);
      return textMatch && statusMatch;
    }).toList();
  }

  Future<void> refresh() async {
    setState(() => future = loadProducts());
    await future;
  }

  @override
  Widget build(BuildContext context) => Scaffold(
    backgroundColor: const Color(0xFFD9E8F6),
    body: SafeArea(
      child: FutureBuilder<List<_Product>>(
        future: future,
        builder: (context, snapshot) {
          if (snapshot.connectionState == ConnectionState.waiting)
            return const Center(child: CircularProgressIndicator());
          if (snapshot.hasError)
            return _Error(error: snapshot.error!, retry: refresh);
          final list = filtered(snapshot.data ?? const []);
          final pages = list.isEmpty ? 1 : (list.length / pageSize).ceil();
          final current = page.clamp(0, pages - 1);
          return _ProductPage(
            products: list.skip(current * pageSize).take(pageSize).toList(),
            total: list.length,
            page: current,
            pages: pages,
            search: search,
            filter: filter,
            onFilter: (value) => setState(() {
              filter = value;
              page = 0;
            }),
            onPage: (value) => setState(() => page = value),
            onRefresh: refresh,
          );
        },
      ),
    ),
  );
}

class _Product {
  const _Product({
    required this.name,
    required this.maker,
    required this.count,
    required this.issues,
    required this.latest,
  });
  final String name;
  final String maker;
  final int count;
  final int issues;
  final Map<String, dynamic> latest;
  _Product copy({required int count, required int issues}) => _Product(
    name: name,
    maker: maker,
    count: count,
    issues: issues,
    latest: latest,
  );
}

class _ProductPage extends StatelessWidget {
  const _ProductPage({
    required this.products,
    required this.total,
    required this.page,
    required this.pages,
    required this.search,
    required this.filter,
    required this.onFilter,
    required this.onPage,
    required this.onRefresh,
  });
  final List<_Product> products;
  final int total;
  final int page;
  final int pages;
  final TextEditingController search;
  final String filter;
  final ValueChanged<String> onFilter;
  final ValueChanged<int> onPage;
  final Future<void> Function() onRefresh;

  @override
  Widget build(BuildContext context) => Center(
    child: ConstrainedBox(
      constraints: const BoxConstraints(maxWidth: 1440),
      child: ListView(
        padding: const EdgeInsets.all(22),
        children: [
          _bar(context),
          const SizedBox(height: 14),
          Row(
            children: [
              const Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      'Products',
                      style: TextStyle(
                        fontSize: 25,
                        fontWeight: FontWeight.w700,
                        color: Color(0xFF16243A),
                      ),
                    ),
                    SizedBox(height: 4),
                    Text(
                      'Products grouped from recorded inspection data.',
                      style: TextStyle(fontSize: 10, color: Color(0xFF53647A)),
                    ),
                  ],
                ),
              ),
              IconButton(
                onPressed: onRefresh,
                tooltip: 'Refresh products',
                icon: const Icon(Icons.refresh_rounded),
              ),
            ],
          ),
          const SizedBox(height: 14),
          _Panel(
            child: Wrap(
              spacing: 14,
              runSpacing: 10,
              children: [
                SizedBox(
                  width: 320,
                  height: 38,
                  child: TextField(
                    controller: search,
                    decoration: const InputDecoration(
                      hintText: 'Search product or manufacturer',
                      prefixIcon: Icon(Icons.search_rounded),
                      border: OutlineInputBorder(),
                    ),
                  ),
                ),
                SegmentedButton<String>(
                  segments: const [
                    ButtonSegment(value: 'All', label: Text('All')),
                    ButtonSegment(value: 'Compliant', label: Text('Compliant')),
                    ButtonSegment(value: 'Violation', label: Text('Violation')),
                  ],
                  selected: {filter},
                  onSelectionChanged: (value) => onFilter(value.first),
                ),
              ],
            ),
          ),
          const SizedBox(height: 14),
          _Panel(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  '$total products',
                  style: const TextStyle(
                    fontSize: 12,
                    color: Color(0xFF53647A),
                  ),
                ),
                const SizedBox(height: 10),
                if (products.isEmpty)
                  const _Empty()
                else
                  SingleChildScrollView(
                    scrollDirection: Axis.horizontal,
                    child: SizedBox(
                      width: 1040,
                      child: Column(
                        children: [
                          const _Line(
                            cells: [
                              'PRODUCT',
                              'MANUFACTURER',
                              'INSPECTIONS',
                              'LATEST INSPECTION',
                              'STATUS',
                              'VIOLATIONS',
                              'ACTION',
                            ],
                            header: true,
                          ),
                          ...products.map(
                            (product) => _ProductLine(product: product),
                          ),
                        ],
                      ),
                    ),
                  ),
              ],
            ),
          ),
          const SizedBox(height: 10),
          Row(
            mainAxisAlignment: MainAxisAlignment.end,
            children: [
              IconButton(
                onPressed: page > 0 ? () => onPage(page - 1) : null,
                icon: const Icon(Icons.chevron_left_rounded),
              ),
              Text(
                '${page + 1} / $pages',
                style: const TextStyle(fontSize: 11, color: Color(0xFF53647A)),
              ),
              IconButton(
                onPressed: page + 1 < pages ? () => onPage(page + 1) : null,
                icon: const Icon(Icons.chevron_right_rounded),
              ),
            ],
          ),
        ],
      ),
    ),
  );

  Widget _bar(BuildContext context) => Container(
    height: 48,
    padding: const EdgeInsets.symmetric(horizontal: 14),
    decoration: BoxDecoration(
      color: Colors.white,
      borderRadius: BorderRadius.circular(9),
    ),
    child: Row(
      children: [
        const Icon(Icons.square_rounded, color: Color(0xFF6251EF), size: 20),
        const SizedBox(width: 7),
        const Text(
          'LegalMetrology AI',
          style: TextStyle(fontSize: 11, fontWeight: FontWeight.w700),
        ),
        const SizedBox(width: 26),
        _Nav(
          label: 'Dashboard',
          onTap: () => Navigator.of(context).pushReplacementNamed('/dashboard'),
        ),
        const _Nav(label: 'Products', active: true),
        _Nav(
          label: 'Inspections',
          onTap: () =>
              Navigator.of(context).pushReplacementNamed('/inspections'),
        ),
        const _Nav(label: 'Compliance'),
        const _Nav(label: 'Reports'),
        const Spacer(),
        const Icon(Icons.notifications_none_rounded, size: 17),
        const SizedBox(width: 10),
        const CircleAvatar(
          radius: 10,
          backgroundColor: Color(0xFF183B32),
          child: Icon(Icons.person, size: 13, color: Colors.white),
        ),
      ],
    ),
  );
}

class _ProductLine extends StatelessWidget {
  const _ProductLine({required this.product});
  final _Product product;
  @override
  Widget build(BuildContext context) {
    final compliant = product.latest['is_compliant'] == true;
    final date = DateTime.tryParse(
      product.latest['inspected_at']?.toString() ?? '',
    );
    return _Line(
      cells: [
        product.name,
        product.maker,
        '${product.count}',
        date == null
            ? '-'
            : '${date.day.toString().padLeft(2, '0')}/${date.month.toString().padLeft(2, '0')} ${date.hour.toString().padLeft(2, '0')}:${date.minute.toString().padLeft(2, '0')}',
        compliant ? 'Compliant' : 'Violation',
        '${product.issues}',
        'View Report',
      ],
      result: compliant ? const Color(0xFF1D9B5C) : const Color(0xFFD34E55),
      action: () => Navigator.of(context).push(
        MaterialPageRoute<void>(
          builder: (_) => InspectionDetailsScreen(inspection: product.latest),
        ),
      ),
    );
  }
}

class _Line extends StatelessWidget {
  const _Line({
    required this.cells,
    this.header = false,
    this.result,
    this.action,
  });
  final List<String> cells;
  final bool header;
  final Color? result;
  final VoidCallback? action;
  @override
  Widget build(BuildContext context) => Container(
    padding: const EdgeInsets.symmetric(vertical: 9),
    decoration: BoxDecoration(
      border: Border(
        bottom: BorderSide(
          color: const Color(0xFFE8EDF2),
          width: header ? 1 : .7,
        ),
      ),
    ),
    child: Row(
      children: cells
          .asMap()
          .entries
          .map(
            (entry) => SizedBox(
              width: entry.key == 0 ? 220 : 136,
              child: entry.key == cells.length - 1 && action != null
                  ? TextButton(
                      onPressed: action,
                      child: Text(
                        entry.value,
                        style: const TextStyle(
                          fontSize: 9,
                          color: Color(0xFF2964D8),
                        ),
                      ),
                    )
                  : Text(
                      entry.value,
                      maxLines: 1,
                      overflow: TextOverflow.ellipsis,
                      style: TextStyle(
                        fontSize: header ? 8 : 10,
                        color:
                            result ??
                            (header
                                ? const Color(0xFF718096)
                                : const Color(0xFF344054)),
                        fontWeight: header || (result != null && entry.key == 4)
                            ? FontWeight.w700
                            : FontWeight.w400,
                      ),
                    ),
            ),
          )
          .toList(),
    ),
  );
}

class _Nav extends StatelessWidget {
  const _Nav({required this.label, this.active = false, this.onTap});
  final String label;
  final bool active;
  final VoidCallback? onTap;
  @override
  Widget build(BuildContext context) => Padding(
    padding: const EdgeInsets.only(right: 18),
    child: InkWell(
      onTap: onTap,
      borderRadius: BorderRadius.circular(4),
      child: Container(
        padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 6),
        decoration: active
            ? BoxDecoration(
                color: const Color(0xFFE8F0FF),
                border: Border.all(color: const Color(0xFF80A9FF)),
                borderRadius: BorderRadius.circular(4),
              )
            : null,
        child: Text(
          label,
          style: TextStyle(
            fontSize: 10,
            color: active ? const Color(0xFF2964D8) : const Color(0xFF344054),
            fontWeight: active ? FontWeight.w600 : FontWeight.w400,
          ),
        ),
      ),
    ),
  );
}

class _Panel extends StatelessWidget {
  const _Panel({required this.child});
  final Widget child;
  @override
  Widget build(BuildContext context) => Container(
    padding: const EdgeInsets.all(16),
    decoration: BoxDecoration(
      color: Colors.white,
      borderRadius: BorderRadius.circular(9),
      border: Border.all(color: const Color(0xFFB9D0E6)),
    ),
    child: child,
  );
}

class _Empty extends StatelessWidget {
  const _Empty();
  @override
  Widget build(BuildContext context) => const Padding(
    padding: EdgeInsets.all(35),
    child: Center(
      child: Text(
        'No products found.',
        style: TextStyle(fontSize: 12, color: Color(0xFF68716D)),
      ),
    ),
  );
}

class _Error extends StatelessWidget {
  const _Error({required this.error, required this.retry});
  final Object error;
  final Future<void> Function() retry;
  @override
  Widget build(BuildContext context) => Center(
    child: Column(
      mainAxisSize: MainAxisSize.min,
      children: [
        const Icon(Icons.cloud_off_rounded, size: 48, color: Color(0xFF68716D)),
        const SizedBox(height: 12),
        const Text('Unable to load products.'),
        const SizedBox(height: 6),
        SizedBox(
          width: 420,
          child: Text(
            error.toString(),
            textAlign: TextAlign.center,
            maxLines: 3,
            overflow: TextOverflow.ellipsis,
          ),
        ),
        const SizedBox(height: 12),
        FilledButton.icon(
          onPressed: retry,
          icon: const Icon(Icons.refresh_rounded),
          label: const Text('Try again'),
        ),
      ],
    ),
  );
}

String value(Object? input, String fallback) {
  final text = input?.toString().trim() ?? '';
  return text.isEmpty ? fallback : text;
}

int issueCount(Object? input) {
  final text = input?.toString().trim() ?? '';
  if (text.isEmpty) return 0;
  try {
    final decoded = jsonDecode(text);
    if (decoded is List) return decoded.length;
    if (decoded is Map) return 1;
  } on FormatException {
    // Plain TEXT issue descriptions count as one issue.
  }
  return 1;
}
