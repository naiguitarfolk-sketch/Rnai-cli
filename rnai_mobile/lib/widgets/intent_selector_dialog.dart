import 'package:flutter/material.dart';
import '../theme/app_theme.dart';

class IntentOption {
  final String id;
  final String title;
  final String subtitle;
  final IconData icon;
  final Color color;

  const IntentOption({
    required this.id,
    required this.title,
    required this.subtitle,
    required this.icon,
    required this.color,
  });
}

class IntentSelectorDialog extends StatefulWidget {
  final String? defaultUserInstructions;
  final Function(Map<String, dynamic> data) onConfirm;

  const IntentSelectorDialog({
    super.key,
    this.defaultUserInstructions,
    required this.onConfirm,
  });

  @override
  State<IntentSelectorDialog> createState() => _IntentSelectorDialogState();
}

class _IntentSelectorDialogState extends State<IntentSelectorDialog> {
  final _titleController = TextEditingController();
  final _promptController = TextEditingController();
  late TextEditingController _contextController;

  String _selectedIntent = 'general';
  bool _createFolder = true;
  bool _createMemory = true;

  final List<IntentOption> _intents = const [
    IntentOption(
      id: 'summary',
      title: 'สรุป & วิเคราะห์',
      subtitle: 'สกัดใจความสำคัญ เอกสาร สถิติ',
      icon: Icons.auto_awesome,
      color: Color(0xFF1E88E5),
    ),
    IntentOption(
      id: 'lesson',
      title: 'การสอน & บทเรียน',
      subtitle: 'วางแผนสอน ทำข้อสอบ สื่อการเรียน',
      icon: Icons.school,
      color: Color(0xFF43A047),
    ),
    IntentOption(
      id: 'coding',
      title: 'เขียนโค้ด & พัฒนา',
      subtitle: 'ออกแบบระบบ แก้บั๊ก วิเคราะห์โค้ด',
      icon: Icons.code,
      color: Color(0xFF8E24AA),
    ),
    IntentOption(
      id: 'planning',
      title: 'วางแผน & กลยุทธ์',
      subtitle: 'Roadmap, KPI, แผนงานระยะยาว',
      icon: Icons.insights,
      color: Color(0xFFFB8C00),
    ),
    IntentOption(
      id: 'research',
      title: 'ค้นคว้า & วิจัย',
      subtitle: 'รวบรวมทฤษฎี งานวิจัย อ้างอิง',
      icon: Icons.manage_search,
      color: Color(0xFF00ACC1),
    ),
    IntentOption(
      id: 'general',
      title: 'สนทนาทั่วไป',
      subtitle: 'ถามตอบอิสระ ปรึกษาหัวข้อรอบตัว',
      icon: Icons.chat_bubble_outline,
      color: Color(0xFFD77757),
    ),
  ];

  @override
  void initState() {
    super.initState();
    _contextController = TextEditingController(
      text: widget.defaultUserInstructions ?? '',
    );
  }

  @override
  void dispose() {
    _titleController.dispose();
    _promptController.dispose();
    _contextController.dispose();
    super.dispose();
  }

  void _submit() {
    final title = _titleController.text.trim();
    if (title.isEmpty) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('กรุณาระบุชื่อโปรเจกต์หรือหัวข้อ')),
      );
      return;
    }

    widget.onConfirm({
      'title': title,
      'intent': _selectedIntent,
      'prompt': _promptController.text.trim(),
      'context': _contextController.text.trim(),
      'create_folder': _createFolder,
      'create_memory': _createMemory,
    });
    Navigator.of(context).pop();
  }

  @override
  Widget build(BuildContext context) {
    final isDark = Theme.of(context).brightness == Brightness.dark;
    final screenHeight = MediaQuery.of(context).size.height;

    return Dialog(
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(20)),
      insetPadding: const EdgeInsets.symmetric(horizontal: 16, vertical: 20),
      child: Container(
        constraints: BoxConstraints(
          maxWidth: 500,
          maxHeight: screenHeight * 0.85,
        ),
        padding: const EdgeInsets.all(18),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            // Header
            Row(
              children: [
                Container(
                  padding: const EdgeInsets.all(8),
                  decoration: BoxDecoration(
                    color: AppColors.primary.withAlpha(25),
                    borderRadius: BorderRadius.circular(10),
                  ),
                  child: const Icon(
                    Icons.add_task,
                    color: AppColors.primary,
                    size: 22,
                  ),
                ),
                const SizedBox(width: 10),
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(
                        'สร้างบทสนทนาใหม่พร้อมความจำนง',
                        style: Theme.of(context).textTheme.titleMedium?.copyWith(
                              fontSize: 16,
                              fontWeight: FontWeight.bold,
                            ),
                      ),
                      Text(
                        'กำหนดเป้าหมายเพื่อบันทึก Memory.md ประจำโครงการ',
                        style: TextStyle(
                          fontSize: 11,
                          color: isDark ? Colors.grey[400] : Colors.grey[600],
                        ),
                      ),
                    ],
                  ),
                ),
                IconButton(
                  icon: const Icon(Icons.close, size: 20),
                  padding: EdgeInsets.zero,
                  constraints: const BoxConstraints(),
                  onPressed: () => Navigator.of(context).pop(),
                  tooltip: 'ปิด',
                ),
              ],
            ),
            const Divider(height: 18),

            // Scrollable Content
            Expanded(
              child: SingleChildScrollView(
                physics: const BouncingScrollPhysics(),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    // Title Field
                    const Text(
                      'ชื่อโปรเจกต์ / หัวข้อบทสนทนา *',
                      style: TextStyle(fontWeight: FontWeight.w600, fontSize: 13),
                    ),
                    const SizedBox(height: 6),
                    TextField(
                      controller: _titleController,
                      decoration: InputDecoration(
                        hintText: 'เช่น วิจัยการตลาด 2026, วางแผนสอน ม.4, วิเคราะห์งบ...',
                        prefixIcon: const Icon(Icons.folder_open, size: 20),
                        filled: true,
                        fillColor: isDark ? const Color(0xFF242C33) : const Color(0xFFF8F9FA),
                        border: OutlineInputBorder(
                          borderRadius: BorderRadius.circular(12),
                          borderSide: BorderSide.none,
                        ),
                        contentPadding: const EdgeInsets.symmetric(horizontal: 14, vertical: 10),
                      ),
                    ),
                    const SizedBox(height: 16),

                    // Intent Matrix
                    const Text(
                      'เลือกเป้าหมาย & ความจำนง (Intent)',
                      style: TextStyle(fontWeight: FontWeight.w600, fontSize: 13),
                    ),
                    const SizedBox(height: 8),
                    GridView.builder(
                      shrinkWrap: true,
                      physics: const NeverScrollableScrollPhysics(),
                      gridDelegate: const SliverGridDelegateWithFixedCrossAxisCount(
                        crossAxisCount: 2,
                        crossAxisSpacing: 8,
                        mainAxisSpacing: 8,
                        childAspectRatio: 2.2,
                      ),
                      itemCount: _intents.length,
                      itemBuilder: (context, idx) {
                        final item = _intents[idx];
                        final isSelected = _selectedIntent == item.id;
                        return InkWell(
                          onTap: () {
                            setState(() {
                              _selectedIntent = item.id;
                            });
                          },
                          borderRadius: BorderRadius.circular(12),
                          child: Container(
                            padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 6),
                            decoration: BoxDecoration(
                              color: isSelected
                                  ? item.color.withAlpha(isDark ? 50 : 25)
                                  : (isDark ? const Color(0xFF242C33) : const Color(0xFFF8F9FA)),
                              border: Border.all(
                                color: isSelected ? item.color : Colors.transparent,
                                width: 1.8,
                              ),
                              borderRadius: BorderRadius.circular(12),
                            ),
                            child: Row(
                              children: [
                                CircleAvatar(
                                  radius: 14,
                                  backgroundColor: item.color.withAlpha(40),
                                  child: Icon(item.icon, size: 16, color: item.color),
                                ),
                                const SizedBox(width: 8),
                                Expanded(
                                  child: Column(
                                    crossAxisAlignment: CrossAxisAlignment.start,
                                    mainAxisAlignment: MainAxisAlignment.center,
                                    children: [
                                      Text(
                                        item.title,
                                        style: TextStyle(
                                          fontWeight: FontWeight.bold,
                                          fontSize: 11,
                                          color: isSelected ? item.color : null,
                                        ),
                                        maxLines: 1,
                                        overflow: TextOverflow.ellipsis,
                                      ),
                                      Text(
                                        item.subtitle,
                                        style: TextStyle(
                                          fontSize: 9.5,
                                          color: isDark ? Colors.grey[400] : Colors.grey[600],
                                        ),
                                        maxLines: 1,
                                        overflow: TextOverflow.ellipsis,
                                      ),
                                    ],
                                  ),
                                ),
                              ],
                            ),
                          ),
                        );
                      },
                    ),
                    const SizedBox(height: 16),

                    // Context / Requirements
                    const Text(
                      'บริบทเฉพาะ หรือ กฎเกณฑ์ที่ AI ต้องจำ',
                      style: TextStyle(fontWeight: FontWeight.w600, fontSize: 13),
                    ),
                    const SizedBox(height: 6),
                    TextField(
                      controller: _contextController,
                      maxLines: 2,
                      decoration: InputDecoration(
                        hintText: 'เช่น "ใช้ภาษาทางการ", "เน้นตัวอย่างเป็น Python", "เขียนตอบให้กระชับ"',
                        filled: true,
                        fillColor: isDark ? const Color(0xFF242C33) : const Color(0xFFF8F9FA),
                        border: OutlineInputBorder(
                          borderRadius: BorderRadius.circular(12),
                          borderSide: BorderSide.none,
                        ),
                        contentPadding: const EdgeInsets.symmetric(horizontal: 14, vertical: 10),
                      ),
                    ),
                    const SizedBox(height: 12),

                    // Switches
                    SwitchListTile(
                      contentPadding: EdgeInsets.zero,
                      dense: true,
                      title: const Text('สร้างโฟลเดอร์สำหรับจัดเก็บไฟล์โปรเจกต์นี้', style: TextStyle(fontSize: 12)),
                      subtitle: const Text('จัดระเบียบเอกสารแยกตามโครงการอัตโนมัติ', style: TextStyle(fontSize: 10)),
                      value: _createFolder,
                      activeThumbColor: AppColors.primary,
                      onChanged: (val) => setState(() => _createFolder = val),
                    ),
                    SwitchListTile(
                      contentPadding: EdgeInsets.zero,
                      dense: true,
                      title: const Text('สร้างและอัปเดต Memory.md อัตโนมัติ', style: TextStyle(fontSize: 12)),
                      subtitle: const Text('สรุปสาระสำคัญทุกครั้งที่คุย เพื่อความจำต่อเนื่อง', style: TextStyle(fontSize: 10)),
                      value: _createMemory,
                      activeThumbColor: AppColors.accent,
                      onChanged: (val) => setState(() => _createMemory = val),
                    ),
                  ],
                ),
              ),
            ),

            const SizedBox(height: 12),
            // Sticky Action Buttons
            Row(
              children: [
                Expanded(
                  child: OutlinedButton(
                    onPressed: () => Navigator.of(context).pop(),
                    style: OutlinedButton.styleFrom(
                      padding: const EdgeInsets.symmetric(vertical: 12),
                      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(10)),
                    ),
                    child: const Text('ยกเลิก'),
                  ),
                ),
                const SizedBox(width: 10),
                Expanded(
                  flex: 2,
                  child: ElevatedButton.icon(
                    onPressed: _submit,
                    icon: const Icon(Icons.arrow_forward, size: 18),
                    label: const Text('เริ่มการสนทนา'),
                    style: ElevatedButton.styleFrom(
                      backgroundColor: AppColors.primary,
                      foregroundColor: Colors.white,
                      padding: const EdgeInsets.symmetric(vertical: 12),
                      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(10)),
                    ),
                  ),
                ),
              ],
            ),
          ],
        ),
      ),
    );
  }
}
