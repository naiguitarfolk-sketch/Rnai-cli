import 'package:flutter/material.dart';
import '../models/user_profile.dart';
import '../services/profile_service.dart';
import '../theme/app_theme.dart';

class ProfileSheet extends StatefulWidget {
  final UserProfile initialProfile;
  final Function(UserProfile updatedProfile) onSaved;

  const ProfileSheet({
    super.key,
    required this.initialProfile,
    required this.onSaved,
  });

  @override
  State<ProfileSheet> createState() => _ProfileSheetState();
}

class _ProfileSheetState extends State<ProfileSheet> {
  late TextEditingController _nameController;
  late TextEditingController _roleController;
  late TextEditingController _orgController;
  late TextEditingController _emailController;
  late TextEditingController _instructionsController;
  late int _avatarIndex;

  final List<Color> _avatarColors = const [
    AppColors.primary,
    AppColors.accent,
    Color(0xFF1E88E5),
    Color(0xFF43A047),
    Color(0xFF8E24AA),
    Color(0xFF00897B),
  ];

  final List<Map<String, String>> _personaPresets = const [
    {
      'label': 'อาจารย์ & ผู้สอน',
      'role': 'อาจารย์ผู้สอน',
      'text': 'เน้นสร้างแผนการสอน สรุปเนื้อหาเข้าใจง่าย ตัวอย่างประกอบชัดเจน พร้อมแบบฝึกหัดทบทวน',
    },
    {
      'label': 'นักพัฒนาซอฟต์แวร์',
      'role': 'โปรแกรมเมอร์ / นักพัฒนา',
      'text': 'เน้นโค้ดที่สะอาดตาม Best Practice อธิบายสถาปัตยกรรมระบบ แก้บั๊กอย่างตรงจุดและมีประสิทธิภาพ',
    },
    {
      'label': 'นักวิจัย & นักศึกษา',
      'role': 'นักวิจัย / นักศึกษา',
      'text': 'เน้นการอ้างอิงเชิงวิชาการ สรุปใจความสำคัญจากรายงาน วิเคราะห์ข้อมูลอย่างเป็นระบบและเป็นกลาง',
    },
    {
      'label': 'บริหาร & วางแผนกลยุทธ์',
      'role': 'ผู้บริหาร / ที่ปรึกษา',
      'text': 'เน้นภาพรวมเชิงกลยุทธ์ ประเมินความเสี่ยง จุดคุ้มทุน และข้อเสนอแนะที่นำไปปฏิบัติได้จริงทันที',
    },
  ];

  @override
  void initState() {
    super.initState();
    _nameController = TextEditingController(text: widget.initialProfile.name);
    _roleController = TextEditingController(text: widget.initialProfile.role);
    _orgController = TextEditingController(text: widget.initialProfile.organization);
    _emailController = TextEditingController(text: widget.initialProfile.email);
    _instructionsController =
        TextEditingController(text: widget.initialProfile.aiCustomInstructions);
    _avatarIndex = widget.initialProfile.avatarIndex;
  }

  @override
  void dispose() {
    _nameController.dispose();
    _roleController.dispose();
    _orgController.dispose();
    _emailController.dispose();
    _instructionsController.dispose();
    super.dispose();
  }

  void _applyPreset(Map<String, String> preset) {
    setState(() {
      _roleController.text = preset['role'] ?? _roleController.text;
      _instructionsController.text = preset['text'] ?? _instructionsController.text;
    });
  }

  Future<void> _save() async {
    final name = _nameController.text.trim();
    if (name.isEmpty) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('กรุณาระบุชื่อผู้ใช้งาน')),
      );
      return;
    }

    final updated = UserProfile(
      name: name,
      role: _roleController.text.trim(),
      organization: _orgController.text.trim(),
      email: _emailController.text.trim(),
      aiCustomInstructions: _instructionsController.text.trim(),
      avatarIndex: _avatarIndex,
    );

    await ProfileService.saveProfile(updated);
    widget.onSaved(updated);
    if (mounted) {
      Navigator.of(context).pop();
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('บันทึกโปรไฟล์เรียบร้อยแล้ว')),
      );
    }
  }

  @override
  Widget build(BuildContext context) {
    final isDark = Theme.of(context).brightness == Brightness.dark;
    final avatarColor = _avatarColors[_avatarIndex % _avatarColors.length];

    return Container(
      constraints: BoxConstraints(
        maxHeight: MediaQuery.of(context).size.height * 0.90,
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
            padding: const EdgeInsets.symmetric(horizontal: 20, vertical: 6),
            child: Row(
              children: [
                CircleAvatar(
                  radius: 20,
                  backgroundColor: avatarColor,
                  child: Text(
                    _nameController.text.isNotEmpty
                        ? _nameController.text.characters.first.toUpperCase()
                        : 'U',
                    style: const TextStyle(
                      color: Colors.white,
                      fontWeight: FontWeight.bold,
                      fontSize: 18,
                    ),
                  ),
                ),
                const SizedBox(width: 12),
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      const Text(
                        'โปรไฟล์ผู้ใช้งาน (User Profile)',
                        style: TextStyle(fontWeight: FontWeight.bold, fontSize: 16),
                      ),
                      Text(
                        'บันทึกตัวตนและบริบทเฉพาะเพื่อให้ AI ตอบได้ตรงใจ',
                        style: TextStyle(
                          fontSize: 11,
                          color: isDark ? Colors.grey[400] : Colors.grey[600],
                        ),
                      ),
                    ],
                  ),
                ),
                IconButton(
                  icon: const Icon(Icons.close),
                  onPressed: () => Navigator.of(context).pop(),
                ),
              ],
            ),
          ),
          const Divider(height: 16),

          // Scrollable Form
          Expanded(
            child: SingleChildScrollView(
              padding: const EdgeInsets.symmetric(horizontal: 20, vertical: 8),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  // Avatar theme selector
                  const Text(
                    'เลือกสีธีมประจำตัว',
                    style: TextStyle(fontWeight: FontWeight.w600, fontSize: 12),
                  ),
                  const SizedBox(height: 8),
                  Row(
                    children: List.generate(_avatarColors.length, (idx) {
                      final c = _avatarColors[idx];
                      final isSelected = _avatarIndex == idx;
                      return Padding(
                        padding: const EdgeInsets.only(right: 10),
                        child: InkWell(
                          onTap: () => setState(() => _avatarIndex = idx),
                          customBorder: const CircleBorder(),
                          child: Container(
                            width: 32,
                            height: 32,
                            decoration: BoxDecoration(
                              color: c,
                              shape: BoxShape.circle,
                              border: Border.all(
                                color: isSelected ? Colors.white : Colors.transparent,
                                width: 2.5,
                              ),
                              boxShadow: isSelected
                                  ? [
                                      BoxShadow(
                                        color: c.withAlpha(120),
                                        blurRadius: 6,
                                        spreadRadius: 1,
                                      )
                                    ]
                                  : null,
                            ),
                            child: isSelected
                                ? const Icon(Icons.check, size: 16, color: Colors.white)
                                : null,
                          ),
                        ),
                      );
                    }),
                  ),
                  const SizedBox(height: 18),

                  // Name
                  const Text(
                    'ชื่อผู้ใช้งาน / ชื่อเรียก *',
                    style: TextStyle(fontWeight: FontWeight.w600, fontSize: 13),
                  ),
                  const SizedBox(height: 6),
                  TextField(
                    controller: _nameController,
                    onChanged: (_) => setState(() {}),
                    decoration: InputDecoration(
                      hintText: 'เช่น คุณชนา หรือ อาจารย์ชนา',
                      prefixIcon: const Icon(Icons.person_outline, size: 20),
                      filled: true,
                      fillColor: isDark ? const Color(0xFF242C33) : const Color(0xFFF8F9FA),
                      border: OutlineInputBorder(
                        borderRadius: BorderRadius.circular(12),
                        borderSide: BorderSide.none,
                      ),
                      contentPadding: const EdgeInsets.symmetric(horizontal: 14, vertical: 12),
                    ),
                  ),
                  const SizedBox(height: 14),

                  // Role & Organization
                  Row(
                    children: [
                      Expanded(
                        child: Column(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            const Text(
                              'ตำแหน่ง / บทบาท',
                              style: TextStyle(fontWeight: FontWeight.w600, fontSize: 13),
                            ),
                            const SizedBox(height: 6),
                            TextField(
                              controller: _roleController,
                              decoration: InputDecoration(
                                hintText: 'เช่น นักพัฒนา / ผู้สอน',
                                prefixIcon: const Icon(Icons.badge_outlined, size: 18),
                                filled: true,
                                fillColor:
                                    isDark ? const Color(0xFF242C33) : const Color(0xFFF8F9FA),
                                border: OutlineInputBorder(
                                  borderRadius: BorderRadius.circular(12),
                                  borderSide: BorderSide.none,
                                ),
                                contentPadding:
                                    const EdgeInsets.symmetric(horizontal: 12, vertical: 12),
                              ),
                            ),
                          ],
                        ),
                      ),
                      const SizedBox(width: 12),
                      Expanded(
                        child: Column(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            const Text(
                              'สังกัด / หน่วยงาน',
                              style: TextStyle(fontWeight: FontWeight.w600, fontSize: 13),
                            ),
                            const SizedBox(height: 6),
                            TextField(
                              controller: _orgController,
                              decoration: InputDecoration(
                                hintText: 'เช่น HomeServer Academy',
                                prefixIcon: const Icon(Icons.business_outlined, size: 18),
                                filled: true,
                                fillColor:
                                    isDark ? const Color(0xFF242C33) : const Color(0xFFF8F9FA),
                                border: OutlineInputBorder(
                                  borderRadius: BorderRadius.circular(12),
                                  borderSide: BorderSide.none,
                                ),
                                contentPadding:
                                    const EdgeInsets.symmetric(horizontal: 12, vertical: 12),
                              ),
                            ),
                          ],
                        ),
                      ),
                    ],
                  ),
                  const SizedBox(height: 14),

                  // Email
                  const Text(
                    'อีเมล / ช่องทางติดต่อ',
                    style: TextStyle(fontWeight: FontWeight.w600, fontSize: 13),
                  ),
                  const SizedBox(height: 6),
                  TextField(
                    controller: _emailController,
                    keyboardType: TextInputType.emailAddress,
                    decoration: InputDecoration(
                      hintText: 'เช่น chana@example.com',
                      prefixIcon: const Icon(Icons.email_outlined, size: 18),
                      filled: true,
                      fillColor: isDark ? const Color(0xFF242C33) : const Color(0xFFF8F9FA),
                      border: OutlineInputBorder(
                        borderRadius: BorderRadius.circular(12),
                        borderSide: BorderSide.none,
                      ),
                      contentPadding: const EdgeInsets.symmetric(horizontal: 14, vertical: 12),
                    ),
                  ),
                  const SizedBox(height: 18),

                  // Custom Instructions for AI
                  Row(
                    mainAxisAlignment: MainAxisAlignment.spaceBetween,
                    children: [
                      const Text(
                        'บริบทประจำตัวที่ต้องการให้ AI จดจำ (AI Instructions)',
                        style: TextStyle(fontWeight: FontWeight.w600, fontSize: 13),
                      ),
                    ],
                  ),
                  const SizedBox(height: 4),
                  Text(
                    'คำสั่งนี้จะถูกผนวกเข้ากับบทสนทนา เพื่อให้ AI ปรับสไตล์คำตอบให้เข้ากับคุณที่สุด',
                    style: TextStyle(
                      fontSize: 11,
                      color: isDark ? Colors.grey[400] : Colors.grey[600],
                    ),
                  ),
                  const SizedBox(height: 8),

                  // Preset chips
                  Wrap(
                    spacing: 8,
                    runSpacing: 6,
                    children: _personaPresets.map((preset) {
                      return ActionChip(
                        avatar: const Icon(Icons.auto_fix_high, size: 14, color: AppColors.accent),
                        label: Text(preset['label']!, style: const TextStyle(fontSize: 11)),
                        onPressed: () => _applyPreset(preset),
                      );
                    }).toList(),
                  ),
                  const SizedBox(height: 8),

                  TextField(
                    controller: _instructionsController,
                    maxLines: 3,
                    decoration: InputDecoration(
                      hintText: 'ระบุแนวทางคำตอบที่ต้องการ เช่น สุภาพ อธิบายแบบเป็นขั้นตอน เน้นตัวอย่าง...',
                      filled: true,
                      fillColor: isDark ? const Color(0xFF242C33) : const Color(0xFFF8F9FA),
                      border: OutlineInputBorder(
                        borderRadius: BorderRadius.circular(12),
                        borderSide: BorderSide.none,
                      ),
                      contentPadding: const EdgeInsets.symmetric(horizontal: 14, vertical: 12),
                    ),
                  ),
                  const SizedBox(height: 24),
                ],
              ),
            ),
          ),

          // Save Button
          Padding(
            padding: EdgeInsets.only(
              left: 20,
              right: 20,
              top: 8,
              bottom: MediaQuery.of(context).padding.bottom + 12,
            ),
            child: SizedBox(
              width: double.infinity,
              height: 48,
              child: ElevatedButton.icon(
                onPressed: _save,
                icon: const Icon(Icons.check),
                label: const Text('บันทึกข้อมูลโปรไฟล์'),
                style: ElevatedButton.styleFrom(
                  backgroundColor: AppColors.primary,
                  foregroundColor: Colors.white,
                  shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
                ),
              ),
            ),
          ),
        ],
      ),
    );
  }
}
