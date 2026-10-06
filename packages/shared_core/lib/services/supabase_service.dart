import 'package:image_picker/image_picker.dart';
import 'package:supabase_flutter/supabase_flutter.dart';

import 'compliance_analysis.dart';

class SupabaseService {
  SupabaseService({SupabaseClient? client})
    : _client = client ?? Supabase.instance.client;

  final SupabaseClient _client;

  Future<void> testConnection() async {
    await _client.from('supabase_test').insert({
      'message': 'Supabase connection test',
      'created_at': DateTime.now().toUtc().toIso8601String(),
    });
  }

  Future<void> saveInspectionReport({
    required ComplianceAnalysis analysis,
    required String ocrText,
    XFile? primaryImage,
    String? imageUrl,
    DateTime? inspectedAt,
  }) async {
    String? accessibleImageUrl = imageUrl;
    if (accessibleImageUrl == null && primaryImage != null) {
      try {
        accessibleImageUrl = await uploadInspectionImage(primaryImage);
      } catch (error) {
        // Storage upload failed or bucket restricted; proceed with null URL
        // so the database row is guaranteed to be saved.
      }
    }

    await _client.from('inspections').insert({
      'product_name': analysis.productName,
      'mrp': analysis.mrp,
      'net_quantity': analysis.netQuantity,
      'manufacturer': analysis.manufacturer,
      'address': analysis.address,
      'packing_date': analysis.packingDate,
      'customer_care': analysis.customerCare,
      'missing_information': analysis.missingInformation,
      'possible_issues': analysis.possibleIssues
          .map((issue) => issue.toJson())
          .toList(),
      'is_compliant': analysis.isCompliant,
      'ocr_text': ocrText,
      'ai_report': analysis.toJson(),
      'inspected_at': (inspectedAt ?? DateTime.now()).toUtc().toIso8601String(),
      'image_url': accessibleImageUrl,
    });
  }

  Future<String> uploadInspectionImage(XFile image) async {
    const bucketName = 'inspection-images';
    final bytes = await image.readAsBytes();
    final extension = _fileExtension(image.name);
    final path = '${DateTime.now().toUtc().microsecondsSinceEpoch}.$extension';

    await _client.storage
        .from(bucketName)
        .uploadBinary(
          path,
          bytes,
          fileOptions: FileOptions(
            contentType: _contentType(extension),
            upsert: false,
          ),
        );

    return _client.storage.from(bucketName).getPublicUrl(path);
  }

  String _fileExtension(String fileName) {
    final dot = fileName.lastIndexOf('.');
    if (dot < 0 || dot == fileName.length - 1) return 'jpg';
    final extension = fileName.substring(dot + 1).toLowerCase();
    return RegExp(r'^[a-z0-9]+$').hasMatch(extension) ? extension : 'jpg';
  }

  String _contentType(String extension) {
    switch (extension) {
      case 'png':
        return 'image/png';
      case 'webp':
        return 'image/webp';
      default:
        return 'image/jpeg';
    }
  }
}
