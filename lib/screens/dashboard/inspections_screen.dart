import 'dart:convert';

import 'package:flutter/material.dart';
import 'package:supabase_flutter/supabase_flutter.dart';

import 'inspection_details_screen.dart';

class InspectionsScreen extends StatefulWidget {
  const InspectionsScreen({super.key});

  @override
  State<InspectionsScreen> createState() => _InspectionsScreenState();
}

class _InspectionsScreenState extends State<InspectionsScreen> {
  static const _pageSize = 10;
  late Future<_InspectionData> _inspectionsFuture;
  final _searchController = TextEditingController();
  String _statusFilter = 'All';
  int _page = 0;

  @override
  void initState() {
    super.initState();
    _inspectionsFuture = _loadInspections();
    _searchController.addListener(_resetPage);
  }

  @override
  void dispose() {
    _searchController
      ..removeListener(_resetPage)
      ..dispose();
    super.dispose();
  }

  Future<_InspectionData> _loadInspections() async {
    final client = Supabase.instance.client;
    final results = await Future.wait<dynamic>([
      client.from('inspections').select('product_name').count(CountOption.exact),
      client
        .from('inspections')
        .select(
          'product_name, mrp, net_quantity, manufacturer, address, '
          'packing_date, customer_care, ai_report, image_url, inspected_at, '
          'is_compliant, missing_information, possible_issues',
        )
        .order('inspected_at', ascending: false)
        .limit(200),
    ]);
    return _InspectionData(
      total: (results[0] as PostgrestResponse).count,
      rows: List<Map<String, dynamic>>.from(results[1]),
    );
  }

  void _resetPage() {
    if (mounted && _page != 0) setState(() => _page = 0);
  }

  Future<void> _refresh() async {
    setState(() => _inspectionsFuture = _loadInspections());
    await _inspectionsFuture;
  }

  List<Map<String, dynamic>> _filtered(List<Map<String, dynamic>> inspections) {
    final search = _searchController.text.trim().toLowerCase();
    return inspections.where((inspection) {
      final matchesStatus =
          _statusFilter == 'All' ||
          (_statusFilter == 'Compliant'
              ? inspection['is_compliant'] == true
              : inspection['is_compliant'] == false);
      final product =
          inspection['product_name']?.toString().toLowerCase() ?? '';
      final manufacturer =
          inspection['manufacturer']?.toString().toLowerCase() ?? '';
      return matchesStatus &&
          (search.isEmpty ||
              product.contains(search) ||
              manufacturer.contains(search));
    }).toList();
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: const Color(0xFFD9E8F6),
      body: SafeArea(
        child: FutureBuilder<_InspectionData>(
          future: _inspectionsFuture,
          builder: (context, snapshot) {
            if (snapshot.connectionState == ConnectionState.waiting) {
              return const Center(child: CircularProgressIndicator());
            }
            if (snapshot.hasError) {
              return _ErrorState(error: snapshot.error!, onRetry: _refresh);
            }
            final inspections = _filtered(snapshot.data?.rows ?? const []);
            return _PageContent(
              inspections: inspections,
              total: snapshot.data?.total ?? 0,
              page: _page,
              pageSize: _pageSize,
              searchController: _searchController,
              statusFilter: _statusFilter,
              onFilterChanged: (value) => setState(() {
                _statusFilter = value;
                _page = 0;
              }),
              onPageChanged: (page) => setState(() => _page = page),
              onRefresh: _refresh,
            );
          },
        ),
      ),
    );
  }
}

class _PageContent extends StatelessWidget {
  const _PageContent({
    required this.inspections,
    required this.total,
    required this.page,
    required this.pageSize,
    required this.searchController,
    required this.statusFilter,
    required this.onFilterChanged,
    required this.onPageChanged,
    required this.onRefresh,
  });

  final List<Map<String, dynamic>> inspections;
  final int total;
  final int page;
  final int pageSize;
  final TextEditingController searchController;
  final String statusFilter;
  final ValueChanged<String> onFilterChanged;
  final ValueChanged<int> onPageChanged;
  final Future<void> Function() onRefresh;

  @override
  Widget build(BuildContext context) {
    final pageCount = inspections.isEmpty
        ? 1
        : (inspections.length / pageSize).ceil();
    final safePage = page >= pageCount ? pageCount - 1 : page;
    final start = safePage * pageSize;
    final rows = inspections.skip(start).take(pageSize).toList();

    return Center(
      child: ConstrainedBox(
        constraints: const BoxConstraints(maxWidth: 1440),
        child: ListView(
          padding: const EdgeInsets.all(22),
          children: [
            const _TopBar(),
            const SizedBox(height: 14),
            Row(
              crossAxisAlignment: CrossAxisAlignment.end,
              children: [
                const Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(
                        'Inspections',
                        style: TextStyle(
                          fontSize: 25,
                          fontWeight: FontWeight.w700,
                          color: Color(0xFF16243A),
                        ),
                      ),
                      SizedBox(height: 4),
                      Text(
                        'Review product inspections and compliance outcomes.',
                        style: TextStyle(
                          fontSize: 10,
                          color: Color(0xFF53647A),
                        ),
                      ),
                    ],
                  ),
                ),
                IconButton(
                  onPressed: onRefresh,
                  tooltip: 'Refresh inspections',
                  icon: const Icon(Icons.refresh_rounded),
                ),
              ],
            ),
            const SizedBox(height: 14),
            _Toolbar(
              searchController: searchController,
              statusFilter: statusFilter,
              onFilterChanged: onFilterChanged,
            ),
            const SizedBox(height: 14),
            _TablePanel(rows: rows, total: total, filteredCount: inspections.length),
            const SizedBox(height: 10),
            _Pagination(
              page: safePage,
              pageCount: pageCount,
              onPageChanged: onPageChanged,
            ),
          ],
        ),
      ),
    );
  }
}

class _InspectionData {
  const _InspectionData({required this.total, required this.rows});

  final int total;
  final List<Map<String, dynamic>> rows;
}

class _TopBar extends StatelessWidget {
  const _TopBar();

  @override
  Widget build(BuildContext context) => Container(
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
        _Nav(
          label: 'Products',
          onTap: () => Navigator.of(context).pushReplacementNamed('/products'),
        ),
        const _Nav(label: 'Inspections', active: true),
        const _Nav(label: 'Compliance'),
        const _Nav(label: 'Reports'),
        const Spacer(),
        IconButton(
          onPressed: () {},
          tooltip: 'Notifications',
          icon: const Icon(Icons.notifications_none_rounded, size: 17),
          padding: EdgeInsets.zero,
          constraints: const BoxConstraints.tightFor(width: 28, height: 32),
        ),
        const Icon(
          Icons.help_outline_rounded,
          size: 17,
          color: Color(0xFF344054),
        ),
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

class _Toolbar extends StatelessWidget {
  const _Toolbar({
    required this.searchController,
    required this.statusFilter,
    required this.onFilterChanged,
  });
  final TextEditingController searchController;
  final String statusFilter;
  final ValueChanged<String> onFilterChanged;

  @override
  Widget build(BuildContext context) => _Panel(
    child: Wrap(
      spacing: 14,
      runSpacing: 10,
      crossAxisAlignment: WrapCrossAlignment.center,
      children: [
        SizedBox(
          width: 300,
          height: 38,
          child: TextField(
            controller: searchController,
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
          selected: {statusFilter},
          onSelectionChanged: (selection) => onFilterChanged(selection.first),
        ),
      ],
    ),
  );
}

class _TablePanel extends StatelessWidget {
  const _TablePanel({required this.rows, required this.total, required this.filteredCount});
  final List<Map<String, dynamic>> rows;
  final int total;
  final int filteredCount;

  @override
  Widget build(BuildContext context) {
    return _Panel(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(
            'Total inspections: $total  |  Showing: $filteredCount',
            style: const TextStyle(fontSize: 12, color: Color(0xFF53647A)),
          ),
          const SizedBox(height: 10),
          if (rows.isEmpty)
            const _Empty()
          else
            SingleChildScrollView(
              scrollDirection: Axis.horizontal,
              child: SizedBox(
                width: 1080,
                child: Column(
                  children: [
                    const _Line(
                      cells: [
                        'PRODUCT',
                        'MRP',
                        'NET QUANTITY',
                        'INSPECTION DATE/TIME',
                        'RESULT',
                        'VIOLATIONS',
                        'ACTION',
                      ],
                      header: true,
                    ),
                    ...rows.map(
                      (inspection) => _InspectionLine(inspection: inspection),
                    ),
                  ],
                ),
              ),
            ),
        ],
      ),
    );
  }
}

class _InspectionLine extends StatelessWidget {
  const _InspectionLine({required this.inspection});
  final Map<String, dynamic> inspection;

  @override
  Widget build(BuildContext context) {
    final compliant = inspection['is_compliant'] == true;
    final date = DateTime.tryParse(
      inspection['inspected_at']?.toString() ?? '',
    );
    final cells = [
      inspection['product_name']?.toString() ?? 'Unnamed product',
      inspection['mrp']?.toString() ?? '-',
      inspection['net_quantity']?.toString() ?? '-',
      date == null ? '-' : _date(date),
      compliant ? 'Compliant' : 'Violation',
      '${_issueCount(inspection['possible_issues'])}',
      'View Report',
    ];
    return _Line(
      cells: cells,
      resultColor: compliant
          ? const Color(0xFF1D9B5C)
          : const Color(0xFFD34E55),
      onAction: () => Navigator.of(context).push(
        MaterialPageRoute<void>(
          builder: (_) => InspectionDetailsScreen(inspection: inspection),
        ),
      ),
    );
  }

  String _date(DateTime value) =>
      '${value.day.toString().padLeft(2, '0')}/${value.month.toString().padLeft(2, '0')} ${value.hour.toString().padLeft(2, '0')}:${value.minute.toString().padLeft(2, '0')}';
}

class _Line extends StatelessWidget {
  const _Line({
    required this.cells,
    this.header = false,
    this.resultColor,
    this.onAction,
  });
  final List<String> cells;
  final bool header;
  final Color? resultColor;
  final VoidCallback? onAction;

  @override
  Widget build(BuildContext context) {
    return Container(
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
        children: cells.asMap().entries.map((entry) {
          final isAction = entry.key == cells.length - 1 && onAction != null;
          return SizedBox(
            width: entry.key == 0 ? 240 : 140,
            child: isAction
                ? TextButton(
                    onPressed: onAction,
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
                          resultColor ??
                          (header
                              ? const Color(0xFF718096)
                              : const Color(0xFF344054)),
                      fontWeight:
                          header || (resultColor != null && entry.key == 4)
                          ? FontWeight.w700
                          : FontWeight.w400,
                    ),
                  ),
          );
        }).toList(),
      ),
    );
  }
}

class _Pagination extends StatelessWidget {
  const _Pagination({
    required this.page,
    required this.pageCount,
    required this.onPageChanged,
  });
  final int page;
  final int pageCount;
  final ValueChanged<int> onPageChanged;
  @override
  Widget build(BuildContext context) => Row(
    mainAxisAlignment: MainAxisAlignment.end,
    children: [
      IconButton(
        onPressed: page > 0 ? () => onPageChanged(page - 1) : null,
        icon: const Icon(Icons.chevron_left_rounded),
      ),
      Text(
        '${page + 1} / $pageCount',
        style: const TextStyle(fontSize: 11, color: Color(0xFF53647A)),
      ),
      IconButton(
        onPressed: page + 1 < pageCount ? () => onPageChanged(page + 1) : null,
        icon: const Icon(Icons.chevron_right_rounded),
      ),
    ],
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
        'No inspections found.',
        style: TextStyle(fontSize: 12, color: Color(0xFF68716D)),
      ),
    ),
  );
}

class _ErrorState extends StatelessWidget {
  const _ErrorState({required this.error, required this.onRetry});
  final Object error;
  final Future<void> Function() onRetry;
  @override
  Widget build(BuildContext context) => Center(
    child: Column(
      mainAxisSize: MainAxisSize.min,
      children: [
        const Icon(Icons.cloud_off_rounded, size: 48, color: Color(0xFF68716D)),
        const SizedBox(height: 12),
        const Text('Unable to load inspections.'),
        const SizedBox(height: 6),
        SizedBox(
          width: 420,
          child: Text(
            error.toString(),
            textAlign: TextAlign.center,
            maxLines: 3,
            overflow: TextOverflow.ellipsis,
            style: const TextStyle(fontSize: 11, color: Color(0xFF68716D)),
          ),
        ),
        const SizedBox(height: 12),
        FilledButton.icon(
          onPressed: onRetry,
          icon: const Icon(Icons.refresh_rounded),
          label: const Text('Try again'),
        ),
      ],
    ),
  );
}

int _issueCount(Object? value) {
  if (value == null) return 0;
  final text = value.toString().trim();
  if (text.isEmpty) return 0;
  try {
    final decoded = jsonDecode(text);
    if (decoded is List) return decoded.length;
    if (decoded is Map) return 1;
  } on FormatException {
    // Plain issue descriptions are valid TEXT values.
  }
  return 1;
}
