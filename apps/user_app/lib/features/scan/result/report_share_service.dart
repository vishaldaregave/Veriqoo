import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:share_plus/share_plus.dart';

/// Shares a report summary as plain text.
///
/// Injected behind a provider so widget tests can supply a fake that records
/// the payload instead of opening the OS share sheet.
abstract class ReportSharer {
  Future<void> share(String text);
}

/// Production [ReportSharer] backed by `share_plus` (v13).
///
/// Wraps exactly one call — `SharePlus.instance.share(ShareParams(text: ...))`
/// — the v10+ API that supersedes the old top-level `Share.share`.
class SharePlusReportSharer implements ReportSharer {
  const SharePlusReportSharer();

  @override
  Future<void> share(String text) async {
    await SharePlus.instance.share(ShareParams(text: text));
  }
}

/// Provides the [ReportSharer]. Overridden in tests with a recording fake so no
/// native share sheet is ever opened.
final reportSharerProvider =
    Provider<ReportSharer>((ref) => const SharePlusReportSharer());
