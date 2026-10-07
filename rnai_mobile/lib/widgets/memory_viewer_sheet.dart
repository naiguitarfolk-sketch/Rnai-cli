import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_markdown/flutter_markdown.dart';
import '../services/api_service.dart';
import '../theme/app_theme.dart';

class MemoryViewerSheet extends StatefulWidget {
  final String sessionId;
  final String sessionTitle;
  final ApiService apiService;

  const MemoryViewerSheet({
    super.key,
    required this.sessionId,
    required this.sessionTitle,
    required this.apiService,
  });

  @override
  State<MemoryViewerSheet> createState() => _MemoryViewerSheetState();
}

class _MemoryViewerSheetState extends State<MemoryViewerSheet> {
  bool _isLoading = true;
  String _memoryContent = '';
  String _memoryPath = '';
  String? _error;

  @override
  void initState() {
    super.initState();
    _loadMemory();
  }

  Future<void> _loadMemory() async {
    setState(() {
      _isLoading = true;
      _error = null;
    });

    final res = await widget.apiService.getSessionMemory(widget.sessionId);
    if (!mounted) return;

    if (res['ok'] == true) {
      setState(() {
        _isLoading = false;
        _memoryContent = res['content'] ?? '';
        _memoryPath = res['path'] ?? '';
      });
    } else {
      setState(() {
        _isLoading = false;
        _error = res['error'] ?? 'ไม่พบไฟล์ Memory.md ของเซสชันนี้';
      });
    }
  }

  void _copyToClipboard() {
    Clipboard.setData(ClipboardData(text: _memoryContent));
    ScaffoldMessenger.of(context).showSnackBar(
      const SnackBar(content: Text('คัดลอก Memory.md เรียบร้อยแล้ว')),
    );
  }

  @override
  Widget build(BuildContext context) {
    final isDark = Theme.of(context).brightness == Brightness.dark;

    return Container(
      constraints: BoxConstraints(
        maxHeight: MediaQuery.of(context).size.height * 0.85,
      ),
      decoration: BoxDecoration(
        color: Theme.of(context).scaffoldBackgroundColor,
        borderRadius: const BorderRadius.vertical(top: Radius.circular(24)),
      ),
      child: Column(
        children: [
          // Drag handle
          Center(
            child: Container(
              margin: const EdgeInsets.symmetric(vertical: 10),
              width: 40,
              height: 4,
              decoration: BoxDecoration(
                color: Colors.grey.withAlpha(80),
                borderRadius: BorderRadius.circular(2),
              ),
            ),
          ),

          // Header
          Padding(
            padding: const EdgeInsets.symmetric(horizontal: 18, vertical: 8),
            child: Row(
              children: [
                Container(
                  padding: const EdgeInsets.all(8),
                  decoration: BoxDecoration(
                    color: AppColors.accent.withAlpha(25),
                    borderRadius: BorderRadius.circular(10),
                  ),
                  child: const Icon(
                    Icons.history_edu,
                    color: AppColors.accent,
                    size: 22,
                  ),
                ),
                const SizedBox(width: 12),
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Row(
                        children: [
                          Flexible(
                            child: Text(
                              'Memory.md',
                              style: Theme.of(context).textTheme.titleMedium?.copyWith(
                                    fontWeight: FontWeight.bold,
                                  ),
                              overflow: TextOverflow.ellipsis,
                            ),
                          ),
                          const SizedBox(width: 8),
                          Container(
                            padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 2),
                            decoration: BoxDecoration(
                              color: AppColors.primary.withAlpha(25),
                              borderRadius: BorderRadius.circular(6),
                            ),
                            child: const Text(
                              'Live Sync',
                              style: TextStyle(
                                fontSize: 10,
                                fontWeight: FontWeight.bold,
                                color: AppColors.primary,
                              ),
                            ),
                          ),
                        ],
                      ),
                      Text(
                        widget.sessionTitle,
                        style: TextStyle(
                          fontSize: 12,
                          color: isDark ? Colors.grey[400] : Colors.grey[600],
                        ),
                        maxLines: 1,
                        overflow: TextOverflow.ellipsis,
                      ),
                    ],
                  ),
                ),
                IconButton(
                  icon: const Icon(Icons.refresh),
                  tooltip: 'รีเฟรช',
                  onPressed: _loadMemory,
                ),
                IconButton(
                  icon: const Icon(Icons.copy_rounded),
                  tooltip: 'คัดลอกเนื้อหา',
                  onPressed: _memoryContent.isNotEmpty ? _copyToClipboard : null,
                ),
              ],
            ),
          ),

          if (_memoryPath.isNotEmpty)
            Padding(
              padding: const EdgeInsets.symmetric(horizontal: 18, vertical: 4),
              child: Align(
                alignment: Alignment.centerLeft,
                child: Text(
                  'ตำแหน่ง: $_memoryPath',
                  style: TextStyle(
                    fontSize: 11,
                    color: isDark ? Colors.grey[500] : Colors.grey[600],
                    fontFamily: 'monospace',
                  ),
                  maxLines: 1,
                  overflow: TextOverflow.ellipsis,
                ),
              ),
            ),

          const Divider(height: 16),

          // Content
          Expanded(
            child: _isLoading
                ? const Center(child: CircularProgressIndicator())
                : _error != null
                    ? Center(
                        child: Padding(
                          padding: const EdgeInsets.all(24.0),
                          child: Column(
                            mainAxisSize: MainAxisSize.min,
                            children: [
                              Icon(Icons.notes_rounded, size: 48, color: Colors.grey[400]),
                              const SizedBox(height: 12),
                              Text(
                                _error!,
                                textAlign: TextAlign.center,
                                style: TextStyle(color: Colors.grey[600]),
                              ),
                              const SizedBox(height: 12),
                              ElevatedButton.icon(
                                onPressed: _loadMemory,
                                icon: const Icon(Icons.refresh, size: 18),
                                label: const Text('ลองใหม่'),
                              ),
                            ],
                          ),
                        ),
                      )
                    : _memoryContent.trim().isEmpty
                        ? Center(
                            child: Text(
                              'ยังไม่มีการบันทึกความจำสำหรับบทสนทนานี้',
                              style: TextStyle(color: Colors.grey[500]),
                            ),
                          )
                        : Markdown(
                            data: _memoryContent,
                            padding: const EdgeInsets.all(18),
                            selectable: true,
                            styleSheet: MarkdownStyleSheet.fromTheme(Theme.of(context)).copyWith(
                              h1: const TextStyle(
                                fontSize: 18,
                                fontWeight: FontWeight.bold,
                                fontFamilyFallback: AppTheme.thaiFontFallbacks,
                              ),
                              h2: const TextStyle(
                                fontSize: 15,
                                fontWeight: FontWeight.bold,
                                fontFamilyFallback: AppTheme.thaiFontFallbacks,
                              ),
                              h3: const TextStyle(
                                fontSize: 13.5,
                                fontWeight: FontWeight.bold,
                                fontFamilyFallback: AppTheme.thaiFontFallbacks,
                              ),
                              p: const TextStyle(
                                fontSize: 13,
                                height: 1.4,
                                fontFamilyFallback: AppTheme.thaiFontFallbacks,
                              ),
                              listBullet: const TextStyle(
                                fontSize: 13,
                                fontFamilyFallback: AppTheme.thaiFontFallbacks,
                              ),
                              blockquote: TextStyle(
                                fontSize: 12.5,
                                color: isDark ? Colors.grey[300] : Colors.grey[800],
                                fontFamilyFallback: AppTheme.thaiFontFallbacks,
                              ),
                              blockquoteDecoration: BoxDecoration(
                                color: isDark ? const Color(0xFF242C33) : const Color(0xFFEBF3F8),
                                borderRadius: BorderRadius.circular(8),
                                border: const Border(
                                  left: BorderSide(color: AppColors.primary, width: 3.5),
                                ),
                              ),
                            ),
                          ),
          ),
        ],
      ),
    );
  }
}
