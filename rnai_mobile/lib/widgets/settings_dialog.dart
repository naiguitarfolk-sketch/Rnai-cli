import 'package:flutter/material.dart';
import 'package:http/http.dart' as http;
import '../services/api_service.dart';
import '../theme/app_theme.dart';

class SettingsDialog extends StatefulWidget {
  final ApiService apiService;
  final VoidCallback onConfigChanged;

  const SettingsDialog({
    super.key,
    required this.apiService,
    required this.onConfigChanged,
  });

  @override
  State<SettingsDialog> createState() => _SettingsDialogState();
}

class _SettingsDialogState extends State<SettingsDialog> {
  late TextEditingController _urlController;
  late bool _isStudentMode;
  bool _isTesting = false;
  String? _testResult;
  bool? _testSuccess;

  @override
  void initState() {
    super.initState();
    _urlController = TextEditingController(text: widget.apiService.baseUrl);
    _isStudentMode = widget.apiService.isStudentMode;
  }

  @override
  void dispose() {
    _urlController.dispose();
    super.dispose();
  }

  Future<void> _testConnection() async {
    final url = _urlController.text.trim().replaceAll(RegExp(r'/+$'), '');
    if (url.isEmpty) return;

    setState(() {
      _isTesting = true;
      _testResult = null;
      _testSuccess = null;
    });

    try {
      final res = await http.get(Uri.parse('$url/api/status')).timeout(
            const Duration(seconds: 5),
          );
      if (res.statusCode == 200) {
        setState(() {
          _isTesting = false;
          _testSuccess = true;
          _testResult = 'เชื่อมต่อเซิร์ฟเวอร์สำเร็จ! (HTTP 200)';
        });
      } else {
        setState(() {
          _isTesting = false;
          _testSuccess = false;
          _testResult = 'เซิร์ฟเวอร์ตอบกลับสถานะ ${res.statusCode}';
        });
      }
    } catch (e) {
      // ลอง ping /api/sessions
      try {
        final res = await http.get(Uri.parse('$url/api/sessions')).timeout(
              const Duration(seconds: 5),
            );
        if (res.statusCode == 200) {
          setState(() {
            _isTesting = false;
            _testSuccess = true;
            _testResult = 'เชื่อมต่อเซิร์ฟเวอร์สำเร็จ! (HTTP 200)';
          });
          return;
        }
      } catch (_) {}

      setState(() {
        _isTesting = false;
        _testSuccess = false;
        _testResult = 'เชื่อมต่อไม่สำเร็จ: กรุณาตรวจสอบ IP / Port และเปิด rnai ui';
      });
    }
  }

  Future<void> _save() async {
    final newUrl = _urlController.text.trim();
    if (newUrl.isNotEmpty) {
      await widget.apiService.setBaseUrl(newUrl);
    }
    await widget.apiService.setStudentMode(_isStudentMode);
    widget.onConfigChanged();
    if (mounted) Navigator.of(context).pop();
  }

  @override
  Widget build(BuildContext context) {
    final isDark = Theme.of(context).brightness == Brightness.dark;

    return Dialog(
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(20)),
      child: Container(
        constraints: const BoxConstraints(maxWidth: 480),
        padding: const EdgeInsets.all(22),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            Row(
              children: [
                Container(
                  padding: const EdgeInsets.all(8),
                  decoration: BoxDecoration(
                    color: AppColors.primary.withAlpha(25),
                    borderRadius: BorderRadius.circular(10),
                  ),
                  child: const Icon(Icons.settings, color: AppColors.primary),
                ),
                const SizedBox(width: 12),
                const Expanded(
                  child: Text(
                    'ตั้งค่าการเชื่อมต่อ (Settings)',
                    style: TextStyle(fontWeight: FontWeight.bold, fontSize: 16),
                  ),
                ),
                IconButton(
                  icon: const Icon(Icons.close),
                  onPressed: () => Navigator.of(context).pop(),
                ),
              ],
            ),
            const Divider(height: 24),

            // Server URL
            const Text(
              'Server Address (URL เซิร์ฟเวอร์)',
              style: TextStyle(fontWeight: FontWeight.w600, fontSize: 13),
            ),
            const SizedBox(height: 6),
            TextField(
              controller: _urlController,
              decoration: InputDecoration(
                hintText: 'http://192.168.1.xxx:8765',
                prefixIcon: const Icon(Icons.dns_outlined, size: 20),
                filled: true,
                fillColor: isDark ? const Color(0xFF242C33) : const Color(0xFFF8F9FA),
                border: OutlineInputBorder(
                  borderRadius: BorderRadius.circular(12),
                  borderSide: BorderSide.none,
                ),
              ),
            ),
            const SizedBox(height: 6),
            Text(
              '• อุปกรณ์จริง: ระบุ LAN IP ของคอมพิวเตอร์ เช่น http://192.168.1.50:8765\n• Simulator: http://127.0.0.1:8765 | Android Emulator: http://10.0.2.2:8765',
              style: TextStyle(fontSize: 11, color: isDark ? Colors.grey[400] : Colors.grey[600]),
            ),
            const SizedBox(height: 12),

            // Quick Preset Buttons
            Wrap(
              spacing: 8,
              children: [
                ActionChip(
                  label: const Text('Localhost (8765)', style: TextStyle(fontSize: 11)),
                  onPressed: () {
                    _urlController.text = 'http://127.0.0.1:8765';
                  },
                ),
                ActionChip(
                  label: const Text('Student UI (8766)', style: TextStyle(fontSize: 11)),
                  onPressed: () {
                    _urlController.text = 'http://127.0.0.1:8766';
                  },
                ),
                ActionChip(
                  label: const Text('Android (10.0.2.2)', style: TextStyle(fontSize: 11)),
                  onPressed: () {
                    _urlController.text = 'http://10.0.2.2:8765';
                  },
                ),
              ],
            ),
            const SizedBox(height: 16),

            // Mode Selector
            SwitchListTile(
              contentPadding: EdgeInsets.zero,
              title: const Text('โหมดนักเรียน (Student Edition)', style: TextStyle(fontSize: 14)),
              subtitle: const Text('ใช้เอ็นจิ้นวิเคราะห์การเรียนรู้และคำถามนำร่อง', style: TextStyle(fontSize: 11)),
              value: _isStudentMode,
              activeThumbColor: AppColors.accent,
              onChanged: (val) {
                setState(() => _isStudentMode = val);
              },
            ),

            const SizedBox(height: 8),

            // Test Connection Button
            OutlinedButton.icon(
              onPressed: _isTesting ? null : _testConnection,
              icon: _isTesting
                  ? const SizedBox(
                      width: 14,
                      height: 14,
                      child: CircularProgressIndicator(strokeWidth: 2),
                    )
                  : const Icon(Icons.wifi_tethering, size: 16),
              label: const Text('ทดสอบการเชื่อมต่อ'),
              style: OutlinedButton.styleFrom(
                shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(10)),
              ),
            ),

            if (_testResult != null)
              Container(
                margin: const EdgeInsets.only(top: 8),
                padding: const EdgeInsets.all(10),
                decoration: BoxDecoration(
                  color: _testSuccess == true
                      ? Colors.green.withAlpha(25)
                      : Colors.red.withAlpha(25),
                  borderRadius: BorderRadius.circular(8),
                ),
                child: Text(
                  _testResult!,
                  style: TextStyle(
                    fontSize: 12,
                    color: _testSuccess == true ? Colors.green[700] : Colors.red[700],
                    fontWeight: FontWeight.w500,
                  ),
                ),
              ),

            const SizedBox(height: 20),

            // Save Button
            ElevatedButton(
              onPressed: _save,
              style: ElevatedButton.styleFrom(
                backgroundColor: AppColors.primary,
                foregroundColor: Colors.white,
                padding: const EdgeInsets.symmetric(vertical: 14),
                shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
              ),
              child: const Text('บันทึกการตั้งค่า'),
            ),
          ],
        ),
      ),
    );
  }
}
