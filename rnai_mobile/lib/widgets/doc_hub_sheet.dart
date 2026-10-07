import 'package:flutter/material.dart';
import 'package:file_picker/file_picker.dart';
import '../models/doc_info.dart';
import '../services/api_service.dart';
import '../theme/app_theme.dart';

class DocHubSheet extends StatefulWidget {
  final ApiService apiService;
  final Function(String docText) onInsertToChat;

  const DocHubSheet({
    super.key,
    required this.apiService,
    required this.onInsertToChat,
  });

  @override
  State<DocHubSheet> createState() => _DocHubSheetState();
}

class _DocHubSheetState extends State<DocHubSheet> {
  bool _isLoading = true;
  bool _isUploading = false;
  List<DocInfo> _documents = [];
  String? _selectedPreviewText;
  String? _selectedDocName;

  @override
  void initState() {
    super.initState();
    _loadDocs();
  }

  Future<void> _loadDocs() async {
    setState(() => _isLoading = true);
    final docs = await widget.apiService.getDocuments();
    if (!mounted) return;
    setState(() {
      _documents = docs;
      _isLoading = false;
    });
  }

  Future<void> _pickAndUpload() async {
    final result = await FilePicker.platform.pickFiles(
      type: FileType.custom,
      allowedExtensions: ['pdf', 'txt', 'md', 'docx', 'csv', 'json', 'py', 'js', 'html'],
      withData: true,
    );

    if (result == null || result.files.isEmpty) return;

    final file = result.files.first;
    if (file.bytes == null) {
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('ไม่สามารถอ่านไฟล์ได้')),
      );
      return;
    }

    setState(() => _isUploading = true);

    final res = await widget.apiService.uploadDocument(file.name, file.bytes!);
    if (!mounted) return;

    setState(() => _isUploading = false);

    if (res['ok'] == true) {
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text('อัปโหลด ${file.name} สำเร็จแล้ว')),
      );
      _loadDocs();
    } else {
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text('อัปโหลดล้มเหลว: ${res['error'] ?? 'ข้อผิดพลาดไม่ทราบสาเหตุ'}')),
      );
    }
  }

  Future<void> _previewDoc(DocInfo doc) async {
    setState(() {
      _selectedDocName = doc.name;
      _selectedPreviewText = 'กำลังดึงตัวอย่างเอกสาร...';
    });

    final res = await widget.apiService.extractDocPreview(doc.path);
    if (!mounted) return;

    setState(() {
      if (res['ok'] == true) {
        _selectedPreviewText = res['preview'] ?? 'ไม่มีข้อความตัวอย่าง';
      } else {
        _selectedPreviewText = 'ไม่สามารถอ่านตัวอย่างได้: ${res['error']}';
      }
    });
  }

  IconData _getFileIcon(String ext) {
    switch (ext.toLowerCase()) {
      case 'pdf':
        return Icons.picture_as_pdf;
      case 'md':
      case 'txt':
        return Icons.description;
      case 'docx':
      case 'doc':
        return Icons.article;
      case 'py':
      case 'js':
      case 'json':
      case 'html':
        return Icons.code;
      default:
        return Icons.insert_drive_file;
    }
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
                    color: AppColors.primary.withAlpha(25),
                    borderRadius: BorderRadius.circular(10),
                  ),
                  child: const Icon(
                    Icons.folder_shared_outlined,
                    color: AppColors.primary,
                    size: 22,
                  ),
                ),
                const SizedBox(width: 12),
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(
                        'Document Hub (คลังเอกสาร)',
                        style: Theme.of(context).textTheme.titleMedium?.copyWith(
                              fontWeight: FontWeight.bold,
                            ),
                      ),
                      Text(
                        'อัปโหลดไฟล์ และนำมาอ้างอิงในการแชท',
                        style: TextStyle(
                          fontSize: 12,
                          color: isDark ? Colors.grey[400] : Colors.grey[600],
                        ),
                      ),
                    ],
                  ),
                ),
                ElevatedButton.icon(
                  onPressed: _isUploading ? null : _pickAndUpload,
                  icon: _isUploading
                      ? const SizedBox(
                          width: 14,
                          height: 14,
                          child: CircularProgressIndicator(strokeWidth: 2),
                        )
                      : const Icon(Icons.upload_file, size: 16),
                  label: const Text('อัปโหลด'),
                  style: ElevatedButton.styleFrom(
                    backgroundColor: AppColors.accent,
                    foregroundColor: Colors.white,
                    padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
                  ),
                ),
              ],
            ),
          ),
          const Divider(height: 16),

          // Body
          Expanded(
            child: _isLoading
                ? const Center(child: CircularProgressIndicator())
                : _documents.isEmpty
                    ? Center(
                        child: Column(
                          mainAxisSize: MainAxisSize.min,
                          children: [
                            Icon(Icons.cloud_upload_outlined, size: 48, color: Colors.grey[400]),
                            const SizedBox(height: 12),
                            Text(
                              'ยังไม่มีเอกสารในคลัง',
                              style: TextStyle(color: Colors.grey[500]),
                            ),
                            const SizedBox(height: 8),
                            OutlinedButton.icon(
                              onPressed: _pickAndUpload,
                              icon: const Icon(Icons.add),
                              label: const Text('เลือกไฟล์จากเครื่อง'),
                            ),
                          ],
                        ),
                      )
                    : ListView.separated(
                        itemCount: _documents.length,
                        separatorBuilder: (_, index) => const Divider(height: 1),
                        itemBuilder: (context, idx) {
                          final doc = _documents[idx];
                          final ext = doc.extension;
                          return ListTile(
                            leading: CircleAvatar(
                              backgroundColor: AppColors.primary.withAlpha(20),
                              child: Icon(_getFileIcon(ext), color: AppColors.primary, size: 20),
                            ),
                            title: Text(
                              doc.name,
                              style: const TextStyle(fontWeight: FontWeight.w600, fontSize: 13),
                              maxLines: 1,
                              overflow: TextOverflow.ellipsis,
                            ),
                            subtitle: Text(
                              '${doc.sizeFormatted} • อัปเดต ${doc.modified}',
                              style: TextStyle(
                                fontSize: 11,
                                color: isDark ? Colors.grey[400] : Colors.grey[600],
                              ),
                            ),
                            trailing: PopupMenuButton<String>(
                              onSelected: (value) {
                                if (value == 'preview') {
                                  _previewDoc(doc);
                                } else if (value == 'insert') {
                                  widget.onInsertToChat('อ้างอิงเอกสาร: ${doc.name}\n(ที่อยู่: ${doc.path})');
                                  Navigator.of(context).pop();
                                }
                              },
                              itemBuilder: (context) => [
                                const PopupMenuItem(
                                  value: 'insert',
                                  child: Row(
                                    children: [
                                      Icon(Icons.send_rounded, size: 18),
                                      SizedBox(width: 8),
                                      Text('ส่งเข้าแชท'),
                                    ],
                                  ),
                                ),
                                const PopupMenuItem(
                                  value: 'preview',
                                  child: Row(
                                    children: [
                                      Icon(Icons.visibility_outlined, size: 18),
                                      SizedBox(width: 8),
                                      Text('ดูตัวอย่างข้อความ'),
                                    ],
                                  ),
                                ),
                              ],
                            ),
                            onTap: () {
                              widget.onInsertToChat('สรุปเนื้อหาจากเอกสาร: ${doc.name}');
                              Navigator.of(context).pop();
                            },
                          );
                        },
                      ),
          ),

          // Preview Area if selected
          if (_selectedDocName != null)
            Container(
              padding: const EdgeInsets.all(14),
              decoration: BoxDecoration(
                color: isDark ? const Color(0xFF242C33) : const Color(0xFFF1F5F9),
                border: const Border(top: BorderSide(color: Colors.black12)),
              ),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Row(
                    mainAxisAlignment: MainAxisAlignment.spaceBetween,
                    children: [
                      Text(
                        'ตัวอย่าง: $_selectedDocName',
                        style: const TextStyle(fontWeight: FontWeight.bold, fontSize: 12),
                      ),
                      IconButton(
                        icon: const Icon(Icons.close, size: 18),
                        onPressed: () => setState(() => _selectedDocName = null),
                        padding: EdgeInsets.zero,
                        constraints: const BoxConstraints(),
                      ),
                    ],
                  ),
                  const SizedBox(height: 6),
                  Text(
                    _selectedPreviewText ?? '',
                    style: const TextStyle(fontSize: 11),
                    maxLines: 4,
                    overflow: TextOverflow.ellipsis,
                  ),
                ],
              ),
            ),
        ],
      ),
    );
  }
}
