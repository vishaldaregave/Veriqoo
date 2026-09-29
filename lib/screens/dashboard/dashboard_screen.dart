import 'dart:convert';
import 'dart:developer' as developer;

import 'package:flutter/material.dart';
import 'package:supabase_flutter/supabase_flutter.dart';

import 'inspection_details_screen.dart';

class DashboardScreen extends StatefulWidget {
  const DashboardScreen({super.key});

  @override
  State<DashboardScreen> createState() => _DashboardScreenState();
}

class _DashboardScreenState extends State<DashboardScreen> {
  late Future<_DashboardData> _dashboardFuture;

  @override
  void initState() {
    super.initState();
    print('DASHBOARD SCREEN LOADED');
    _dashboardFuture = _loadDashboard();
  }

  Future<_DashboardData> _loadDashboard() async {
    debugPrint('DASHBOARD: loading inspections');
    try {
      final client = Supabase.instance.client;
      final results = await Future.wait<dynamic>([
        _count(client),
        _count(client, compliant: true),
        _count(client, compliant: false),
        _recent(client),
        _analytics(client),
      ]);
      final analytics = results[4] as _AnalyticsData;
      return _DashboardData(
        total: results[0] as int,
        compliant: results[1] as int,
        violations: results[2] as int,
        inspections: results[3] as List<Map<String, dynamic>>,
        trend: analytics.trend,
        topViolations: analytics.topViolations,
      );
    } catch (error, stackTrace) {
      developer.log(
        'Failed to load public.inspections for authority dashboard: $error',
        name: 'authority_dashboard',
        error: error,
        stackTrace: stackTrace,
      );
      rethrow;
    }
  }

  Future<int> _count(SupabaseClient client, {bool? compliant}) async {
    final label = compliant == null
        ? 'total'
        : compliant
        ? 'compliant'
        : 'non-compliant';
    try {
      debugPrint('DASHBOARD: query started ($label count)');
      var query = client.from('inspections').select('product_name');
      if (compliant != null) query = query.eq('is_compliant', compliant);
      final response = await query.count(CountOption.exact);
      debugPrint(
        'DASHBOARD: records received = ${response.count} ($label count)',
      );
      debugPrint(
        'DASHBOARD: first record = count query ($label: ${response.count})',
      );
      debugPrint(
        '[DashboardScreen] $label inspections query result count: ${response.count}',
      );
      return response.count;
    } on PostgrestException catch (error, stackTrace) {
      debugPrint('DASHBOARD: query error = $error');
      debugPrint(
        '[DashboardScreen] $label inspections PostgrestException: '
        '${error.message} (code: ${error.code}, details: ${error.details}, hint: ${error.hint})',
      );
      debugPrintStack(stackTrace: stackTrace);
      rethrow;
    } catch (error, stackTrace) {
      debugPrint('DASHBOARD: query error = $error');
      debugPrint('[DashboardScreen] $label inspections query error: $error');
      debugPrintStack(stackTrace: stackTrace);
      rethrow;
    }
  }

  Future<List<Map<String, dynamic>>> _recent(SupabaseClient client) async {
    try {
      debugPrint('DASHBOARD: query started (latest inspections)');
      final response = await client
          .from('inspections')
          .select(
            'product_name, mrp, net_quantity, manufacturer, address, '
            'packing_date, customer_care, ai_report, image_url, inspected_at, '
            'is_compliant, missing_information, possible_issues',
          )
          .order('inspected_at', ascending: false)
          .limit(50);
      final inspections = List<Map<String, dynamic>>.from(response);
      debugPrint(
        '[DashboardScreen] recent inspections query result count: ${inspections.length}',
      );
      debugPrint('DASHBOARD: records received = ${inspections.length}');
      debugPrint(
        'DASHBOARD: first record = ${inspections.isEmpty ? '<none>' : inspections.first}',
      );
      return inspections;
    } on PostgrestException catch (error, stackTrace) {
      debugPrint('DASHBOARD: query error = $error');
      debugPrint(
        '[DashboardScreen] recent inspections PostgrestException: '
        '${error.message} (code: ${error.code}, details: ${error.details}, hint: ${error.hint})',
      );
      debugPrintStack(stackTrace: stackTrace);
      rethrow;
    } catch (error, stackTrace) {
      debugPrint('DASHBOARD: query error = $error');
      debugPrint('[DashboardScreen] recent inspections query error: $error');
      debugPrintStack(stackTrace: stackTrace);
      rethrow;
    }
  }

  Future<_AnalyticsData> _analytics(SupabaseClient client) async {
    try {
      final cutoff = DateTime.now()
          .toUtc()
          .subtract(const Duration(days: 30))
          .toIso8601String();
      debugPrint('DASHBOARD: query started (analytics)');
      final response = await client
          .from('inspections')
          .select('inspected_at, is_compliant, possible_issues')
          .gte('inspected_at', cutoff)
          .order('inspected_at', ascending: true);
      final records = List<Map<String, dynamic>>.from(response);
      debugPrint('DASHBOARD: records received = ${records.length} (analytics)');
      debugPrint(
        'DASHBOARD: first record = ${records.isEmpty ? '<none>' : records.first}',
      );

      final dailyTotals = <DateTime, int>{};
      final dailyCompliant = <DateTime, int>{};
      final issueCounts = <String, _IssueCount>{};
      for (final record in records) {
        final inspectedAt = DateTime.tryParse(
          record['inspected_at']?.toString() ?? '',
        );
        if (inspectedAt != null) {
          final day = DateTime.utc(
            inspectedAt.year,
            inspectedAt.month,
            inspectedAt.day,
          );
          dailyTotals[day] = (dailyTotals[day] ?? 0) + 1;
          if (record['is_compliant'] == true) {
            dailyCompliant[day] = (dailyCompliant[day] ?? 0) + 1;
          }
        }
        for (final title in _issueTitles(record['possible_issues'])) {
          final key = title.toLowerCase();
          final current = issueCounts[key];
          issueCounts[key] = _IssueCount(
            title: current?.title ?? title,
            count: (current?.count ?? 0) + 1,
          );
        }
      }

      final trend = dailyTotals.entries
          .map(
            (entry) => _TrendPoint(
              day: entry.key,
              rate: ((dailyCompliant[entry.key] ?? 0) / entry.value * 100)
                  .round(),
            ),
          )
          .toList();
      final topViolations = issueCounts.values.toList()
        ..sort((a, b) => b.count.compareTo(a.count));
      return _AnalyticsData(
        trend: trend,
        topViolations: topViolations.take(4).toList(),
      );
    } on PostgrestException catch (error, stackTrace) {
      debugPrint('DASHBOARD: query error = $error');
      debugPrintStack(stackTrace: stackTrace);
      rethrow;
    } catch (error, stackTrace) {
      debugPrint('DASHBOARD: query error = $error');
      debugPrintStack(stackTrace: stackTrace);
      rethrow;
    }
  }

  Future<void> _refresh() async {
    setState(() => _dashboardFuture = _loadDashboard());
    await _dashboardFuture;
  }

  @override
  Widget build(BuildContext context) {
    print('DASHBOARD BUILD');
    return Scaffold(
      backgroundColor: const Color(0xFFD9E8F6),
      body: FutureBuilder<_DashboardData>(
        future: _dashboardFuture,
        builder: (context, snapshot) {
          if (snapshot.connectionState == ConnectionState.waiting) {
            return const Center(child: CircularProgressIndicator());
          }
          if (snapshot.hasError) {
            return _ErrorState(error: snapshot.error!, onRetry: _refresh);
          }
          return _DashboardView(data: snapshot.data!);
        },
      ),
    );
  }
}

class _DashboardData {
  const _DashboardData({
    required this.total,
    required this.compliant,
    required this.violations,
    required this.inspections,
    required this.trend,
    required this.topViolations,
  });
  final int total;
  final int compliant;
  final int violations;
  final List<Map<String, dynamic>> inspections;
  final List<_TrendPoint> trend;
  final List<_IssueCount> topViolations;
  int get rate => total == 0 ? 0 : (compliant / total * 100).round();
}

class _AnalyticsData {
  const _AnalyticsData({required this.trend, required this.topViolations});
  final List<_TrendPoint> trend;
  final List<_IssueCount> topViolations;
}

class _TrendPoint {
  const _TrendPoint({required this.day, required this.rate});
  final DateTime day;
  final int rate;
}

class _IssueCount {
  const _IssueCount({required this.title, required this.count});
  final String title;
  final int count;
}

class _DashboardView extends StatelessWidget {
  const _DashboardView({required this.data});
  final _DashboardData data;

  @override
  Widget build(BuildContext context) {
    return SafeArea(
      child: Center(
        child: ConstrainedBox(
          constraints: const BoxConstraints(maxWidth: 1440),
          child: Padding(
            padding: const EdgeInsets.all(22),
            child: DecoratedBox(
              decoration: BoxDecoration(
                color: const Color(0xFFD9E8F6),
                borderRadius: BorderRadius.circular(18),
              ),
              child: ListView(
                padding: const EdgeInsets.fromLTRB(14, 14, 14, 18),
                children: [
                  const _TopBar(),
                  const SizedBox(height: 14),
                  const _Greeting(),
                  const SizedBox(height: 14),
                  _Stats(data: data),
                  const SizedBox(height: 14),
                  _Analytics(data: data),
                  const SizedBox(height: 14),
                  _LowerPanels(data: data),
                  const SizedBox(height: 14),
                  _RecentTable(data: data),
                ],
              ),
            ),
          ),
        ),
      ),
    );
  }
}

class _TopBar extends StatelessWidget {
  const _TopBar();

  @override
  Widget build(BuildContext context) {
    return Container(
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
            'VERIQO',
            style: TextStyle(fontSize: 11, fontWeight: FontWeight.w700),
          ),
          const SizedBox(width: 26),
          _Nav(
            label: 'Dashboard',
            active: true,
            onTap: () => Navigator.of(context).pushReplacementNamed('/dashboard'),
          ),
          _Nav(
            label: 'Products',
            onTap: () => Navigator.of(context).pushReplacementNamed('/products'),
          ),
          _Nav(
            label: 'Inspections',
            onTap: () => Navigator.of(context).pushReplacementNamed('/inspections'),
          ),
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

class _Greeting extends StatelessWidget {
  const _Greeting();

  @override
  Widget build(BuildContext context) => Row(
    crossAxisAlignment: CrossAxisAlignment.end,
    children: [
      const Expanded(
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(
              'Good morning, Inspector!',
              style: TextStyle(
                fontSize: 20,
                fontWeight: FontWeight.w700,
                color: Color(0xFF16243A),
              ),
            ),
            SizedBox(height: 3),
            Text(
              'Monitor product compliance and enforcement activity under Legal Metrology PC Rules, 2011.',
              style: TextStyle(fontSize: 9, color: Color(0xFF53647A)),
            ),
          ],
        ),
      ),
      SizedBox(
        width: 220,
        height: 32,
        child: TextField(
          decoration: InputDecoration(
            hintText: 'Search products...',
            hintStyle: const TextStyle(fontSize: 9, color: Color(0xFF9AA7B8)),
            prefixIcon: const Icon(
              Icons.search,
              size: 15,
              color: Color(0xFF9AA7B8),
            ),
            filled: true,
            fillColor: Colors.white,
            contentPadding: EdgeInsets.zero,
            border: OutlineInputBorder(
              borderRadius: BorderRadius.circular(5),
              borderSide: BorderSide.none,
            ),
          ),
        ),
      ),
      const SizedBox(width: 10),
      SizedBox(
        height: 32,
        child: FilledButton.icon(
          onPressed: () {},
          icon: const Icon(Icons.add, size: 13),
          label: const Text('New Inspection', style: TextStyle(fontSize: 9)),
          style: FilledButton.styleFrom(
            backgroundColor: Colors.white,
            foregroundColor: const Color(0xFF17283E),
            elevation: 0,
            padding: const EdgeInsets.symmetric(horizontal: 10),
          ),
        ),
      ),
    ],
  );
}

class _Stats extends StatelessWidget {
  const _Stats({required this.data});
  final _DashboardData data;

  @override
  Widget build(BuildContext context) => LayoutBuilder(
    builder: (context, constraints) {
      final width = constraints.maxWidth >= 850
          ? (constraints.maxWidth - 30) / 4
          : (constraints.maxWidth - 10) / 2;
      return Wrap(
        spacing: 10,
        runSpacing: 10,
        children: [
          _Stat(
            label: 'Products Scanned',
            value: _format(data.total),
            trend: '${data.total}',
            trendCaption: 'records',
            color: const Color(0xFF1D9B5C),
            width: width,
          ),
          _Stat(
            label: 'Compliant Products',
            value: _format(data.compliant),
            trend: '${data.rate}%',
            trendCaption: 'of total',
            color: const Color(0xFFC07B18),
            width: width,
          ),
          _Stat(
            label: 'Violations Detected',
            value: _format(data.violations),
            trend: '${data.violations}',
            trendCaption: 'records',
            color: const Color(0xFFD34E55),
            width: width,
          ),
          _Stat(
            label: 'Inspections Completed',
            value: _format(data.total),
            trend: '${data.total}',
            trendCaption: 'records',
            color: const Color(0xFF1D9B5C),
            width: width,
          ),
        ],
      );
    },
  );

  static String _format(int value) => value.toString().replaceAllMapped(
    RegExp(r'\B(?=(\d{3})+(?!\d))'),
    (match) => ',',
  );
}

class _Stat extends StatelessWidget {
  const _Stat({
    required this.label,
    required this.value,
    required this.trend,
    required this.trendCaption,
    required this.color,
    required this.width,
  });
  final String label;
  final String value;
  final String trend;
  final String trendCaption;
  final Color color;
  final double width;

  @override
  Widget build(BuildContext context) => SizedBox(
    width: width,
    child: _Panel(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(
            label,
            style: const TextStyle(fontSize: 9, color: Color(0xFF344054)),
          ),
          const SizedBox(height: 6),
          Text(
            value,
            style: const TextStyle(
              fontSize: 21,
              fontWeight: FontWeight.w700,
              color: Color(0xFF172033),
            ),
          ),
          const SizedBox(height: 5),
          Row(
            children: [
              Text(
                trend,
                style: TextStyle(
                  fontSize: 8,
                  color: color,
                  fontWeight: FontWeight.w700,
                ),
              ),
              const SizedBox(width: 4),
              Text(
                trendCaption,
                style: TextStyle(fontSize: 8, color: Color(0xFF9AA7B8)),
              ),
            ],
          ),
        ],
      ),
    ),
  );
}

class _Analytics extends StatelessWidget {
  const _Analytics({required this.data});
  final _DashboardData data;

  @override
  Widget build(BuildContext context) => LayoutBuilder(
    builder: (context, constraints) {
      final chart = _Trend(data: data);
      final risk = _Risk(data: data);
      return constraints.maxWidth < 680
          ? Column(children: [chart, const SizedBox(height: 12), risk])
          : Row(
              children: [
                Expanded(flex: 2, child: chart),
                const SizedBox(width: 12),
                Expanded(child: risk),
              ],
            );
    },
  );
}

class _Trend extends StatelessWidget {
  const _Trend({required this.data});
  final _DashboardData data;

  static int _averageTrend(List<_TrendPoint> points) =>
      (points.map((point) => point.rate).reduce((a, b) => a + b) /
              points.length)
          .round();

  @override
  Widget build(BuildContext context) => _Panel(
    child: Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        const Text(
          'Compliance Trend',
          style: TextStyle(
            fontSize: 12,
            fontWeight: FontWeight.w700,
            color: Color(0xFF172033),
          ),
        ),
        Text(
          data.trend.isEmpty
              ? 'No inspection data | Last 30 days'
              : '${_averageTrend(data.trend)}% Average Compliance | Last 30 days',
          style: const TextStyle(fontSize: 8, color: Color(0xFF8090A4)),
        ),
        const SizedBox(height: 8),
        SizedBox(
          height: 88,
          child: CustomPaint(
            painter: _TrendPainter(points: data.trend),
            child: const SizedBox.expand(),
          ),
        ),
      ],
    ),
  );
}

class _TrendPainter extends CustomPainter {
  const _TrendPainter({required this.points});
  final List<_TrendPoint> points;

  @override
  void paint(Canvas canvas, Size size) {
    canvas.drawRect(Offset.zero & size, Paint()..color = const Color(0xFFF7F9FB));
    const left = 30.0, right = 8.0, top = 8.0, bottom = 20.0;
    final w = size.width - left - right;
    final h = size.height - top - bottom;
    final grid = Paint()..color = const Color(0xFFDDE5EC)..strokeWidth = 1;
    for (var i = 0; i <= 4; i++) {
      final y = top + h * i / 4;
      canvas.drawLine(Offset(left, y), Offset(size.width - right, y), grid);
      _paintText(canvas, const ['100%', '75%', '50%', '25%', '0%'][i], Offset(1, y - 4));
    }
    if (points.isEmpty) {
      _paintText(canvas, 'No inspection data for the last 30 days', Offset(left + 12, top + h / 2 - 5), color: const Color(0xFF8090A4), fontSize: 8);
      return;
    }
    final offsets = <Offset>[];
    for (var i = 0; i < points.length; i++) {
      final x = points.length == 1 ? left + w / 2 : left + (i / (points.length - 1)) * w;
      final rate = points[i].rate.clamp(0, 100);
      offsets.add(Offset(x, top + (1 - rate / 100) * h));
    }
    final path = Path()..moveTo(offsets.first.dx, offsets.first.dy);
    for (final point in offsets.skip(1)) { path.lineTo(point.dx, point.dy); }
    canvas.drawPath(path, Paint()..color = const Color(0xFF2964D8)..strokeWidth = 2..style = PaintingStyle.stroke);
    for (var i = 0; i < offsets.length; i++) {
      final point = offsets[i];
      canvas.drawCircle(point, 3, Paint()..color = const Color(0xFF2964D8));
      canvas.drawCircle(point, 1.2, Paint()..color = Colors.white);
      _paintText(canvas, '${points[i].rate}%', Offset(point.dx + 5, (point.dy - 15).clamp(top, size.height - 30)), color: const Color(0xFF2964D8), fontSize: 7, fontWeight: FontWeight.w700);
    }
    final labelCount = points.length < 4 ? points.length : 4;
    for (var i = 0; i < labelCount; i++) {
      final index = labelCount == 1 ? 0 : (i * (points.length - 1) / (labelCount - 1)).round();
      final point = offsets[index];
      final date = _formatDay(points[index].day);
      final tp = TextPainter(text: TextSpan(text: date, style: const TextStyle(fontSize: 7, color: Color(0xFF718096))), textDirection: TextDirection.ltr)..layout();
      tp.paint(canvas, Offset((point.dx - tp.width / 2).clamp(left, size.width - right - tp.width), size.height - 14));
    }
  }

  String _formatDay(DateTime day) => '${day.month}/${day.day}';

  void _paintText(Canvas canvas, String text, Offset offset, {Color color = const Color(0xFF9AA7B8), double fontSize = 7, FontWeight fontWeight = FontWeight.w400}) {
    (TextPainter(text: TextSpan(text: text, style: TextStyle(fontSize: fontSize, color: color, fontWeight: fontWeight)), textDirection: TextDirection.ltr)..layout()).paint(canvas, offset);
  }

  @override
  bool shouldRepaint(covariant _TrendPainter oldDelegate) => oldDelegate.points != points;
}

class _Risk extends StatelessWidget {
  const _Risk({required this.data});
  final _DashboardData data;

  @override
  Widget build(BuildContext context) {
    return _Panel(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const Text(
            'Compliance Risk',
            style: TextStyle(
              fontSize: 12,
              fontWeight: FontWeight.w700,
              color: Color(0xFF172033),
            ),
          ),
          const SizedBox(height: 8),
          Row(
            children: [
              SizedBox(
                width: 108,
                height: 108,
                child: CustomPaint(
                  painter: _RiskPainter(
                    compliant: data.compliant,
                    violations: data.violations,
                  ),
                ),
              ),
              const SizedBox(width: 12),
              Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  _Legend(
                    color: const Color(0xFF26B962),
                    text: '${data.rate}% COMPLIANT',
                  ),
                  _Legend(
                    color: const Color(0xFFE95757),
                    text:
                        '${data.total == 0 ? 0 : (data.violations / data.total * 100).round()}% NON-COMPLIANT',
                  ),
                ],
              ),
            ],
          ),
        ],
      ),
    );
  }
}

class _RiskPainter extends CustomPainter {
  const _RiskPainter({required this.compliant, required this.violations});
  final int compliant;
  final int violations;

  @override
  void paint(Canvas canvas, Size size) {
    final center = size.center(Offset.zero);
    final radius = size.shortestSide / 2 - 10;
    final total = compliant + violations;
    canvas.drawCircle(center, radius, Paint()..color = const Color(0xFFE5EBF0)..style = PaintingStyle.stroke..strokeWidth = 11);
    if (total > 0) {
      const pi = 3.141592653589793;
      var start = -pi / 2;
      final compliantSweep = compliant / total * 2 * pi;
      final violationSweep = violations / total * 2 * pi;
      if (compliantSweep > 0) {
        canvas.drawArc(Rect.fromCircle(center: center, radius: radius), start, compliantSweep, false, Paint()..color = const Color(0xFF26B962)..style = PaintingStyle.stroke..strokeWidth = 11..strokeCap = StrokeCap.round);
        start += compliantSweep;
      }
      if (violationSweep > 0) {
        canvas.drawArc(Rect.fromCircle(center: center, radius: radius), start, violationSweep, false, Paint()..color = const Color(0xFFE95757)..style = PaintingStyle.stroke..strokeWidth = 11..strokeCap = StrokeCap.round);
      }
    }
    final rate = total == 0 ? 0 : (compliant / total * 100).round();
    _paintCenteredText(canvas, '$rate%', center.translate(0, -7), 16, FontWeight.w700, const Color(0xFF172033));
    _paintCenteredText(canvas, total == 0 ? 'NO DATA' : 'COMPLIANT', center.translate(0, 11), 6.5, FontWeight.w600, const Color(0xFF718096));
  }

  void _paintCenteredText(Canvas canvas, String text, Offset center, double fontSize, FontWeight fontWeight, Color color) {
    final tp = TextPainter(text: TextSpan(text: text, style: TextStyle(fontSize: fontSize, fontWeight: fontWeight, color: color)), textDirection: TextDirection.ltr)..layout();
    tp.paint(canvas, Offset(center.dx - tp.width / 2, center.dy - tp.height / 2));
  }

  @override
  bool shouldRepaint(covariant _RiskPainter oldDelegate) => oldDelegate.compliant != compliant || oldDelegate.violations != violations;
}

class _Legend extends StatelessWidget {
  const _Legend({required this.color, required this.text});
  final Color color;
  final String text;
  @override
  Widget build(BuildContext context) => Padding(
    padding: const EdgeInsets.only(bottom: 9),
    child: Row(
      children: [
        Container(width: 18, height: 3, color: color),
        const SizedBox(width: 6),
        Text(
          text,
          style: TextStyle(
            fontSize: 8,
            color: color,
            fontWeight: FontWeight.w700,
          ),
        ),
      ],
    ),
  );
}

class _LowerPanels extends StatelessWidget {
  const _LowerPanels({required this.data});
  final _DashboardData data;
  @override
  Widget build(BuildContext context) {
    final insights = _Panel(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const Text(
            'AI Insights',
            style: TextStyle(fontSize: 12, fontWeight: FontWeight.w700),
          ),
          Align(
            alignment: Alignment.topRight,
            child: Text(
              data.trend.isEmpty
                  ? 'No trend data'
                  : 'Based on recorded inspections',
              style: const TextStyle(fontSize: 8, fontWeight: FontWeight.w700),
            ),
          ),
          const _Insight(
            icon: Icons.info_outline,
            text:
                'Most violations this month are related to missing mandatory declarations and incorrect MRP formatting.',
          ),
          const _Insight(
            icon: Icons.add_circle_outline,
            text:
                'Recommendation: prioritize products with repeated violations.',
          ),
          const _Insight(
            icon: Icons.add_circle_outline,
            text: 'Compliance trends are calculated from recorded inspections.',
          ),
          Align(
            alignment: Alignment.centerRight,
            child: TextButton(
              onPressed: () {},
              child: const Text(
                'Review Auto-Flagged Batches',
                style: TextStyle(fontSize: 9, fontWeight: FontWeight.w700),
              ),
            ),
          ),
        ],
      ),
    );
    final violations = _Panel(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            mainAxisAlignment: MainAxisAlignment.spaceBetween,
            children: [
              const Text(
                'Top Violations',
                style: TextStyle(fontSize: 12, fontWeight: FontWeight.w700),
              ),
              TextButton(
                onPressed: () {},
                child: const Text(
                  'View All',
                  style: TextStyle(fontSize: 8, color: Color(0xFF2964D8)),
                ),
              ),
            ],
          ),
          if (data.topViolations.isEmpty)
            const Padding(
              padding: EdgeInsets.symmetric(vertical: 18),
              child: Text(
                'No violation details recorded.',
                style: TextStyle(fontSize: 9, color: Color(0xFF68716D)),
              ),
            )
          else
            ...data.topViolations.map(
              (issue) => _Violation(label: issue.title, count: issue.count),
            ),
        ],
      ),
    );
    return LayoutBuilder(
      builder: (context, constraints) => constraints.maxWidth < 680
          ? Column(children: [violations, const SizedBox(height: 12), insights])
          : Row(
              children: [
                Expanded(child: violations),
                const SizedBox(width: 12),
                Expanded(child: insights),
              ],
            ),
    );
  }
}

class _Violation extends StatelessWidget {
  const _Violation({required this.label, required this.count});
  final String label;
  final int count;
  @override
  Widget build(BuildContext context) => Padding(
    padding: const EdgeInsets.symmetric(vertical: 6),
    child: Row(
      mainAxisAlignment: MainAxisAlignment.spaceBetween,
      children: [
        Text(
          label,
          style: const TextStyle(fontSize: 9, color: Color(0xFF344054)),
        ),
        Container(
          padding: const EdgeInsets.symmetric(horizontal: 5, vertical: 2),
          decoration: BoxDecoration(
            color: const Color(0xFFF0F3F7),
            borderRadius: BorderRadius.circular(3),
          ),
          child: Text(
            '$count',
            style: const TextStyle(fontSize: 8, fontWeight: FontWeight.w700),
          ),
        ),
      ],
    ),
  );
}

class _Insight extends StatelessWidget {
  const _Insight({required this.icon, required this.text});
  final IconData icon;
  final String text;
  @override
  Widget build(BuildContext context) => Padding(
    padding: const EdgeInsets.only(bottom: 7),
    child: Row(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Icon(icon, size: 14),
        const SizedBox(width: 8),
        Expanded(
          child: Text(text, style: const TextStyle(fontSize: 9, height: 1.25)),
        ),
      ],
    ),
  );
}

class _RecentTable extends StatelessWidget {
  const _RecentTable({required this.data});
  final _DashboardData data;
  @override
  Widget build(BuildContext context) {
    return _Panel(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            mainAxisAlignment: MainAxisAlignment.spaceBetween,
            children: [
              const Text(
                'Recent Product Scans',
                style: TextStyle(fontSize: 12, fontWeight: FontWeight.w700),
              ),
              OutlinedButton(
                onPressed: () {},
                child: const Text(
                  'View All',
                  style: TextStyle(fontSize: 8, color: Color(0xFF2964D8)),
                ),
              ),
            ],
          ),
          const SizedBox(height: 4),
          if (data.inspections.isEmpty)
            const _EmptyState()
          else
            SingleChildScrollView(
              scrollDirection: Axis.horizontal,
              child: SizedBox(
                width: 822,
                child: Column(
                  children: [
                    const _TableLine(
                      cells: [
                        'PRODUCT',
                        'MRP',
                        'TIME',
                        'RESULT',
                        'VIOLATIONS',
                        'INSPECTOR',
                        'ACTION',
                      ],
                      header: true,
                    ),
                    ...data.inspections
                        .take(8)
                        .map(
                          (item) => _TableLine(
                            cells: [
                              _product(item),
                              item['mrp']?.toString() ?? '-',
                              _time(item),
                              item['is_compliant'] == true
                                  ? 'Compliant'
                                  : 'Violation',
                              '${_issueCount(item['possible_issues'])}',
                              'Field officer',
                              'View Report',
                            ],
                            result: item['is_compliant'] == true
                                ? const Color(0xFF1D9B5C)
                                : const Color(0xFFD34E55),
                            onAction: () {
                              Navigator.of(context).push(
                                MaterialPageRoute<void>(
                                  builder: (_) =>
                                      InspectionDetailsScreen(inspection: item),
                                ),
                              );
                            },
                          ),
                        ),
                  ],
                ),
              ),
            ),
        ],
      ),
    );
  }

  static String _product(Map<String, dynamic> item) =>
      item['product_name']?.toString() ?? 'Unnamed product';
  static String _time(Map<String, dynamic> item) {
    final date = DateTime.tryParse(item['inspected_at']?.toString() ?? '');
    return date == null
        ? '-'
        : '${date.hour.toString().padLeft(2, '0')}:${date.minute.toString().padLeft(2, '0')}';
  }
}

class _TableLine extends StatelessWidget {
  const _TableLine({
    required this.cells,
    this.header = false,
    this.result,
    this.onAction,
  });
  final List<String> cells;
  final bool header;
  final Color? result;
  final VoidCallback? onAction;
  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.symmetric(vertical: 7),
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
          return SizedBox(
            width: entry.key == 0 ? 210 : 102,
            child: entry.key == cells.length - 1 && onAction != null
                ? TextButton(
                    onPressed: onAction,
                    style: TextButton.styleFrom(
                      padding: const EdgeInsets.symmetric(
                        horizontal: 8,
                        vertical: 4,
                      ),
                      minimumSize: Size.zero,
                      tapTargetSize: MaterialTapTargetSize.shrinkWrap,
                      foregroundColor: const Color(0xFF2964D8),
                    ),
                    child: Text(
                      entry.value,
                      style: const TextStyle(fontSize: 8),
                    ),
                  )
                : Text(
                    entry.value,
                    maxLines: 1,
                    overflow: TextOverflow.ellipsis,
                    style: TextStyle(
                      fontSize: header ? 7 : 8,
                      color:
                          result ??
                          (header
                              ? const Color(0xFF718096)
                              : const Color(0xFF344054)),
                      fontWeight: header || (result != null && entry.key == 2)
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

class _Panel extends StatelessWidget {
  const _Panel({required this.child});
  final Widget child;

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.all(12),
      decoration: BoxDecoration(
        color: Colors.white,
        borderRadius: BorderRadius.circular(9),
        border: Border.all(color: const Color(0xFFB9D0E6)),
      ),
      child: child,
    );
  }
}

class _EmptyState extends StatelessWidget {
  const _EmptyState();

  @override
  Widget build(BuildContext context) {
    return const Padding(
      padding: EdgeInsets.all(25),
      child: Center(
        child: Text(
          'No inspections yet',
          style: TextStyle(fontSize: 11, color: Color(0xFF68716D)),
        ),
      ),
    );
  }
}

class _ErrorState extends StatelessWidget {
  const _ErrorState({required this.error, required this.onRetry});
  final Object error;
  final VoidCallback onRetry;

  @override
  Widget build(BuildContext context) {
    return Center(
      child: Column(
        mainAxisSize: MainAxisSize.min,
        children: [
          const Icon(
            Icons.cloud_off_rounded,
            size: 48,
            color: Color(0xFF68716D),
          ),
          const SizedBox(height: 12),
          const Text('Unable to load dashboard data.'),
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
    // The database column is TEXT; plain descriptions are valid values.
  }
  return 1;
}

List<String> _issueTitles(Object? value) {
  if (value == null) return const [];
  final text = value.toString().trim();
  if (text.isEmpty) return const [];

  Object decoded = text;
  try {
    decoded = jsonDecode(text);
  } on FormatException {
    return text
        .split(RegExp(r'[\n;]+'))
        .map((item) => item.trim())
        .where((item) => item.isNotEmpty)
        .toList();
  }

  if (decoded is List) {
    return decoded
        .map(_issueTitle)
        .whereType<String>()
        .where((title) => title.isNotEmpty)
        .toList();
  }
  final title = _issueTitle(decoded);
  return title == null || title.isEmpty ? const [] : [title];
}

String? _issueTitle(Object? value) {
  if (value is String) return value.trim();
  if (value is Map) {
    for (final key in ['title', 'issue', 'name', 'description', 'message']) {
      final candidate = value[key]?.toString().trim();
      if (candidate != null && candidate.isNotEmpty) return candidate;
    }
  }
  return value?.toString().trim();
}
