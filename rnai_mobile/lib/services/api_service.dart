import 'dart:convert';
import 'package:http/http.dart' as http;
import 'package:shared_preferences/shared_preferences.dart';
import '../models/session_info.dart';
import '../models/doc_info.dart';

class ApiService {
  static const String _keyBaseUrl = 'rnai_base_url';
  static const String _keyIsStudentMode = 'rnai_student_mode';
  static const String _defaultUrl = 'http://127.0.0.1:8765';

  String _baseUrl = _defaultUrl;
  bool _isStudentMode = false;

  String get baseUrl => _baseUrl;
  bool get isStudentMode => _isStudentMode;

  Future<void> init() async {
    final prefs = await SharedPreferences.getInstance();
    _baseUrl = prefs.getString(_keyBaseUrl) ?? _defaultUrl;
    _isStudentMode = prefs.getBool(_keyIsStudentMode) ?? false;
  }

  Future<void> setBaseUrl(String url) async {
    _baseUrl = url.trim().replaceAll(RegExp(r'/+$'), '');
    final prefs = await SharedPreferences.getInstance();
    await prefs.setString(_keyBaseUrl, _baseUrl);
  }

  Future<void> setStudentMode(bool enabled) async {
    _isStudentMode = enabled;
    final prefs = await SharedPreferences.getInstance();
    await prefs.setBool(_keyIsStudentMode, enabled);
  }

  Map<String, String> get _headers => {
        'Content-Type': 'application/json; charset=utf-8',
        'Accept': 'application/json',
      };

  /// ส่งข้อความแชท (รองรับทั้งโหมดปกติและ Student Edition)
  Future<Map<String, dynamic>> sendMessage(
    String message, {
    String? sessionId,
    String? model,
  }) async {
    final endpoint = _isStudentMode ? '/api/student/chat' : '/api/chat';
    final uri = Uri.parse('$_baseUrl$endpoint');
    final body = jsonEncode({
      'message': message,
      'session_id': sessionId ?? '',
      'model': model ?? (_isStudentMode ? 'student' : 'rnai'),
    });

    try {
      final res = await http.post(uri, headers: _headers, body: body).timeout(
        const Duration(seconds: 120),
      );
      if (res.statusCode == 200) {
        return jsonDecode(utf8.decode(res.bodyBytes)) as Map<String, dynamic>;
      } else {
        return {
          'error': 'เซิร์ฟเวอร์ส่งสถานะ ${res.statusCode}: ${res.body}',
        };
      }
    } catch (e) {
      return {'error': 'เชื่อมต่อไม่สำเร็จ: $e'};
    }
  }

  /// ดึงรายการ Recents / Sessions
  Future<List<SessionInfo>> getSessions() async {
    final uri = Uri.parse('$_baseUrl/api/sessions');
    try {
      final res = await http.get(uri).timeout(const Duration(seconds: 15));
      if (res.statusCode == 200) {
        final List list = jsonDecode(utf8.decode(res.bodyBytes));
        return list.map((item) => SessionInfo.fromJson(item)).toList();
      }
    } catch (_) {}
    return [];
  }

  /// สร้างเซสชันใหม่พร้อมความจำนง บริบท และไฟล์ Memory.md
  Future<Map<String, dynamic>> createSessionWithIntent({
    required String title,
    required String intent,
    String? prompt,
    String? context,
    String? folderPath,
    String? model,
  }) async {
    final uri = Uri.parse('$_baseUrl/api/sessions/create');
    final body = jsonEncode({
      'title': title,
      'intent': intent,
      'prompt': prompt ?? '',
      'context': context ?? '',
      'folder_path': folderPath ?? '',
      'model': model ?? (_isStudentMode ? 'student' : 'rnai'),
      'create_folder': true,
      'create_memory': true,
    });

    try {
      final res = await http.post(uri, headers: _headers, body: body).timeout(
        const Duration(seconds: 15),
      );
      return jsonDecode(utf8.decode(res.bodyBytes)) as Map<String, dynamic>;
    } catch (e) {
      return {'ok': false, 'error': e.toString()};
    }
  }

  /// ดึงข้อความในเซสชัน
  Future<Map<String, dynamic>?> getSessionDetail(String sessionId) async {
    final uri = Uri.parse('$_baseUrl/api/sessions/$sessionId');
    try {
      final res = await http.get(uri).timeout(const Duration(seconds: 15));
      if (res.statusCode == 200) {
        return jsonDecode(utf8.decode(res.bodyBytes)) as Map<String, dynamic>;
      }
    } catch (_) {}
    return null;
  }

  /// ดึงเนื้อหาไฟล์ Memory.md
  Future<Map<String, dynamic>> getSessionMemory(String sessionId) async {
    final uri = Uri.parse('$_baseUrl/api/sessions/$sessionId/memory');
    try {
      final res = await http.get(uri).timeout(const Duration(seconds: 15));
      if (res.statusCode == 200) {
        return jsonDecode(utf8.decode(res.bodyBytes)) as Map<String, dynamic>;
      }
      return {'ok': false, 'error': 'สถานะ ${res.statusCode}'};
    } catch (e) {
      return {'ok': false, 'error': e.toString()};
    }
  }

  /// ลบเซสชัน
  Future<bool> deleteSession(String sessionId) async {
    final uri = Uri.parse('$_baseUrl/api/sessions/$sessionId');
    try {
      final res = await http.delete(uri).timeout(const Duration(seconds: 10));
      return res.statusCode == 200;
    } catch (_) {
      return false;
    }
  }

  /// ดึงรายการเอกสารใน Document Hub
  Future<List<DocInfo>> getDocuments() async {
    final uri = Uri.parse('$_baseUrl/api/documents');
    try {
      final res = await http.get(uri).timeout(const Duration(seconds: 15));
      if (res.statusCode == 200) {
        final List list = jsonDecode(utf8.decode(res.bodyBytes));
        return list.map((item) => DocInfo.fromJson(item)).toList();
      }
    } catch (_) {}
    return [];
  }

  /// อัปโหลดเอกสารเข้าเซิร์ฟเวอร์
  Future<Map<String, dynamic>> uploadDocument(
    String filename,
    List<int> bytes,
  ) async {
    final uri = Uri.parse('$_baseUrl/api/documents/upload');
    final base64Content = base64Encode(bytes);
    final body = jsonEncode({
      'filename': filename,
      'content': base64Content,
      'subfolder': 'documents',
    });

    try {
      final res = await http.post(uri, headers: _headers, body: body).timeout(
        const Duration(seconds: 60),
      );
      return jsonDecode(utf8.decode(res.bodyBytes)) as Map<String, dynamic>;
    } catch (e) {
      return {'ok': false, 'error': e.toString()};
    }
  }

  /// อ่านตัวอย่างเนื้อหาเอกสาร
  Future<Map<String, dynamic>> extractDocPreview(String path) async {
    final uri = Uri.parse(
      '$_baseUrl/api/documents/preview?path=${Uri.encodeComponent(path)}',
    );
    try {
      final res = await http.get(uri).timeout(const Duration(seconds: 30));
      return jsonDecode(utf8.decode(res.bodyBytes)) as Map<String, dynamic>;
    } catch (e) {
      return {'ok': false, 'error': e.toString()};
    }
  }
}
