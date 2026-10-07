import 'dart:async';
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_markdown/flutter_markdown.dart';
import '../models/chat_message.dart';
import '../models/session_info.dart';
import '../models/user_profile.dart';
import '../services/api_service.dart';
import '../services/profile_service.dart';
import '../services/speech_service.dart';
import '../theme/app_theme.dart';
import '../widgets/doc_hub_sheet.dart';
import '../widgets/intent_selector_dialog.dart';
import '../widgets/memory_viewer_sheet.dart';
import '../widgets/profile_sheet.dart';
import '../widgets/settings_dialog.dart';

class ChatScreen extends StatefulWidget {
  final ApiService apiService;

  const ChatScreen({super.key, required this.apiService});

  @override
  State<ChatScreen> createState() => _ChatScreenState();
}

class _ChatScreenState extends State<ChatScreen> with SingleTickerProviderStateMixin {
  final List<ChatMessage> _messages = [];
  final TextEditingController _inputController = TextEditingController();
  final ScrollController _scrollController = ScrollController();
  final SpeechService _speechService = SpeechService();

  List<SessionInfo> _sessions = [];
  SessionInfo? _currentSession;
  UserProfile _userProfile = const UserProfile();
  bool _isLoading = false;
  bool _isListening = false;
  String _listeningStatusText = '';

  late AnimationController _micPulseController;
  late Animation<double> _micPulseAnimation;

  final List<Color> _avatarColors = const [
    AppColors.primary,
    AppColors.accent,
    Color(0xFF1E88E5),
    Color(0xFF43A047),
    Color(0xFF8E24AA),
    Color(0xFF00897B),
  ];

  @override
  void initState() {
    super.initState();
    _loadUserProfile();
    _initSpeech();
    _loadSessions();

    _micPulseController = AnimationController(
      vsync: this,
      duration: const Duration(milliseconds: 1000),
    )..repeat(reverse: true);

    _micPulseAnimation = Tween<double>(begin: 1.0, end: 1.25).animate(
      CurvedAnimation(parent: _micPulseController, curve: Curves.easeInOut),
    );
  }

  @override
  void dispose() {
    _inputController.dispose();
    _scrollController.dispose();
    _micPulseController.dispose();
    _speechService.cancelListening();
    super.dispose();
  }

  Future<void> _loadUserProfile() async {
    final profile = await ProfileService.loadProfile();
    if (!mounted) return;
    setState(() {
      _userProfile = profile;
    });
  }

  Future<void> _initSpeech() async {
    try {
      await _speechService.init();
      _speechService.onListeningStateChanged = (listening) {
        if (!mounted) return;
        setState(() {
          _isListening = listening;
          if (!listening) {
            _listeningStatusText = '';
          }
        });
      };
      _speechService.onError = (err) {
        if (!mounted) return;
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text('ข้อผิดพลาดการรู้จำเสียง: $err')),
        );
      };
    } catch (e) {
      debugPrint('Speech init error: $e');
    }
  }

  Future<void> _loadSessions() async {
    final list = await widget.apiService.getSessions();
    if (!mounted) return;
    setState(() {
      _sessions = list;
      if (_currentSession == null && list.isNotEmpty) {
        _selectSession(list.first);
      }
    });
  }

  Future<void> _selectSession(SessionInfo session) async {
    setState(() {
      _currentSession = session;
      _messages.clear();
      _isLoading = true;
    });

    final detail = await widget.apiService.getSessionDetail(session.id);
    if (!mounted) return;

    if (detail != null && detail['history'] != null) {
      final List hist = detail['history'];
      final loaded = hist.map((m) => ChatMessage.fromJson(m)).toList();
      setState(() {
        _messages.addAll(loaded);
        _isLoading = false;
      });
    } else {
      setState(() => _isLoading = false);
    }

    _scrollToBottom();
  }

  void _scrollToBottom() {
    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (_scrollController.hasClients) {
        _scrollController.animateTo(
          _scrollController.position.maxScrollExtent,
          duration: const Duration(milliseconds: 300),
          curve: Curves.easeOut,
        );
      }
    });
  }

  void _openNewSessionDialog() {
    showDialog(
      context: context,
      builder: (ctx) => IntentSelectorDialog(
        defaultUserInstructions: _userProfile.aiCustomInstructions,
        onConfirm: (data) async {
          final res = await widget.apiService.createSessionWithIntent(
            title: data['title'],
            intent: data['intent'],
            prompt: data['prompt'],
            context: data['context'],
          );

          if (res['ok'] == true && res['session'] != null) {
            final newSession = SessionInfo.fromJson(res['session']);
            await _loadSessions();
            _selectSession(newSession);

            if (data['prompt'] != null && data['prompt'].toString().isNotEmpty) {
              _sendMessage(data['prompt']);
            }
          }
        },
      ),
    );
  }

  void _openProfileSheet() {
    showModalBottomSheet(
      context: context,
      isScrollControlled: true,
      backgroundColor: Colors.transparent,
      builder: (ctx) => ProfileSheet(
        initialProfile: _userProfile,
        onSaved: (updated) {
          setState(() {
            _userProfile = updated;
          });
        },
      ),
    );
  }

  void _toggleMic() async {
    if (_isListening) {
      await _speechService.stopListening();
    } else {
      setState(() {
        _listeningStatusText = 'กำลังฟังเสียงของคุณ... (พูดภาษาไทยหรืออังกฤษ)';
      });
      final initialText = _inputController.text;
      await _speechService.startListening(
        onWords: (recognized) {
          if (!mounted) return;
          setState(() {
            _inputController.text = initialText.isEmpty
                ? recognized
                : '$initialText $recognized';
            _inputController.selection = TextSelection.fromPosition(
              TextPosition(offset: _inputController.text.length),
            );
          });
        },
      );
    }
  }

  Future<void> _sendMessage([String? textToSend]) async {
    final text = (textToSend ?? _inputController.text).trim();
    if (text.isEmpty || _isLoading) return;

    _inputController.clear();
    final userMsg = ChatMessage(role: 'user', content: text);
    setState(() {
      _messages.add(userMsg);
      _isLoading = true;
    });
    _scrollToBottom();

    final res = await widget.apiService.sendMessage(
      text,
      sessionId: _currentSession?.id,
    );

    if (!mounted) return;

    if (res.containsKey('reply')) {
      final reply = res['reply'] as String;
      setState(() {
        _messages.add(ChatMessage(role: 'assistant', content: reply));
        _isLoading = false;
      });
    } else {
      final error = res['error'] ?? 'เกิดข้อผิดพลาดในการรับคำตอบ';
      setState(() {
        _messages.add(ChatMessage(
          role: 'assistant',
          content: '⚠️ **ข้อผิดพลาด:** $error',
        ));
        _isLoading = false;
      });
    }

    _scrollToBottom();
  }

  void _openMemorySheet() {
    if (_currentSession == null) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('กรุณาเลือกหรือสร้างบทสนทนาก่อน')),
      );
      return;
    }
    showModalBottomSheet(
      context: context,
      isScrollControlled: true,
      backgroundColor: Colors.transparent,
      builder: (ctx) => MemoryViewerSheet(
        sessionId: _currentSession!.id,
        sessionTitle: _currentSession!.title,
        apiService: widget.apiService,
      ),
    );
  }

  void _openDocHubSheet() {
    showModalBottomSheet(
      context: context,
      isScrollControlled: true,
      backgroundColor: Colors.transparent,
      builder: (ctx) => DocHubSheet(
        apiService: widget.apiService,
        onInsertToChat: (docText) {
          final current = _inputController.text;
          _inputController.text = current.isEmpty ? docText : '$current\n$docText';
        },
      ),
    );
  }

  void _openSettings() {
    showDialog(
      context: context,
      builder: (ctx) => SettingsDialog(
        apiService: widget.apiService,
        onConfigChanged: () {
          _loadSessions();
          setState(() {});
        },
      ),
    );
  }

  ({IconData icon, Color color, String label}) _getIntentInfo(String intent) {
    final lower = intent.toLowerCase();
    if (lower.contains('summary') || lower.contains('สรุป') || lower.contains('วิเคราะห์')) {
      return (icon: Icons.auto_awesome, color: const Color(0xFF1E88E5), label: 'สรุป & วิเคราะห์');
    }
    if (lower.contains('lesson') || lower.contains('สอน') || lower.contains('ติวเตอร์') || lower.contains('ศึกษา')) {
      return (icon: Icons.school, color: const Color(0xFF43A047), label: 'การสอน & บทเรียน');
    }
    if (lower.contains('coding') || lower.contains('โค้ด') || lower.contains('โปรแกรม')) {
      return (icon: Icons.code, color: const Color(0xFF8E24AA), label: 'เขียนโค้ด & พัฒนา');
    }
    if (lower.contains('planning') || lower.contains('วางแผน') || lower.contains('กลยุทธ์')) {
      return (icon: Icons.insights, color: const Color(0xFFFB8C00), label: 'วางแผน & กลยุทธ์');
    }
    if (lower.contains('research') || lower.contains('วิจัย') || lower.contains('ค้นคว้า')) {
      return (icon: Icons.manage_search, color: const Color(0xFF00ACC1), label: 'ค้นคว้า & วิจัย');
    }
    return (icon: Icons.chat_bubble_outline, color: AppColors.accent, label: 'สนทนาทั่วไป');
  }

  String _cleanFolderName(String path) {
    if (path.isEmpty) return '';
    final parts = path.split(RegExp(r'[\\/]'));
    return parts.isNotEmpty ? parts.last : path;
  }

  String _cleanMarkdownContent(String text) {
    if (text.isEmpty) return text;
    // ป้องกัน iOS CoreText สลับฟอนต์เป็น AppleColorEmoji บนหัวข้อภาษาไทย
    return text
        .replaceAll(RegExp(r'([#]{1,6}\s*)[\u{1F300}-\u{1F9FF}\u{2600}-\u{26FF}\u{2700}-\u{27BF}]\s*', unicode: true), r'$1')
        .replaceAll(RegExp(r'[\u{1F300}-\u{1F9FF}\u{2600}-\u{26FF}\u{2700}-\u{27BF}]', unicode: true), '');
  }

  @override
  Widget build(BuildContext context) {
    final isDark = Theme.of(context).brightness == Brightness.dark;
    final currentIntent = _getIntentInfo(_currentSession?.intent ?? '');
    final avatarColor = _avatarColors[_userProfile.avatarIndex % _avatarColors.length];

    return Scaffold(
      appBar: AppBar(
        titleSpacing: 0,
        title: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                Flexible(
                  child: Text(
                    _currentSession?.title ?? 'Rnai Mobile Assistant',
                    style: const TextStyle(fontSize: 16, fontWeight: FontWeight.bold),
                    overflow: TextOverflow.ellipsis,
                  ),
                ),
                if (widget.apiService.isStudentMode) ...[
                  const SizedBox(width: 6),
                  Container(
                    padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 2),
                    decoration: BoxDecoration(
                      color: AppColors.accent.withAlpha(30),
                      borderRadius: BorderRadius.circular(6),
                    ),
                    child: const Text(
                      'STUDENT',
                      style: TextStyle(
                        fontSize: 9,
                        fontWeight: FontWeight.bold,
                        color: AppColors.accent,
                      ),
                    ),
                  ),
                ],
              ],
            ),
            if (_currentSession != null)
              Row(
                children: [
                  Icon(currentIntent.icon, size: 12, color: currentIntent.color),
                  const SizedBox(width: 4),
                  Text(
                    currentIntent.label,
                    style: TextStyle(
                      fontSize: 11,
                      fontWeight: FontWeight.w600,
                      color: currentIntent.color,
                    ),
                  ),
                ],
              ),
          ],
        ),
        actions: [
          // Profile Shortcut Avatar
          InkWell(
            onTap: _openProfileSheet,
            borderRadius: BorderRadius.circular(20),
            child: Padding(
              padding: const EdgeInsets.symmetric(horizontal: 4),
              child: CircleAvatar(
                radius: 14,
                backgroundColor: avatarColor,
                child: Text(
                  _userProfile.name.isNotEmpty
                      ? _userProfile.name.characters.first.toUpperCase()
                      : 'U',
                  style: const TextStyle(
                    color: Colors.white,
                    fontSize: 12,
                    fontWeight: FontWeight.bold,
                  ),
                ),
              ),
            ),
          ),
          IconButton(
            icon: const Icon(Icons.history_edu),
            tooltip: 'ดู Memory.md ประจำโปรเจกต์',
            onPressed: _openMemorySheet,
          ),
          IconButton(
            icon: const Icon(Icons.folder_shared_outlined),
            tooltip: 'Document Hub',
            onPressed: _openDocHubSheet,
          ),
          IconButton(
            icon: const Icon(Icons.settings_outlined),
            tooltip: 'ตั้งค่าการเชื่อมต่อ',
            onPressed: _openSettings,
          ),
        ],
      ),

      // Redesigned Drawer with User Profile Header
      drawer: Drawer(
        child: SafeArea(
          child: Column(
            children: [
              // User Profile Header
              InkWell(
                onTap: () {
                  Navigator.of(context).pop();
                  _openProfileSheet();
                },
                child: Container(
                  padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 16),
                  decoration: BoxDecoration(
                    color: isDark ? const Color(0xFF1E262C) : AppColors.primary,
                  ),
                  child: Row(
                    children: [
                      CircleAvatar(
                        radius: 24,
                        backgroundColor: avatarColor,
                        child: Text(
                          _userProfile.name.isNotEmpty
                              ? _userProfile.name.characters.first.toUpperCase()
                              : 'U',
                          style: const TextStyle(
                            fontSize: 20,
                            fontWeight: FontWeight.bold,
                            color: Colors.white,
                          ),
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
                                    _userProfile.name,
                                    style: const TextStyle(
                                      color: Colors.white,
                                      fontWeight: FontWeight.bold,
                                      fontSize: 15,
                                    ),
                                    overflow: TextOverflow.ellipsis,
                                  ),
                                ),
                                const SizedBox(width: 4),
                                const Icon(
                                  Icons.edit_note,
                                  color: Colors.white70,
                                  size: 16,
                                ),
                              ],
                            ),
                            Text(
                              _userProfile.role.isNotEmpty
                                  ? _userProfile.role
                                  : _userProfile.organization,
                              style: const TextStyle(
                                color: Colors.white70,
                                fontSize: 11,
                              ),
                              maxLines: 1,
                              overflow: TextOverflow.ellipsis,
                            ),
                            const SizedBox(height: 2),
                            Text(
                              widget.apiService.baseUrl,
                              style: TextStyle(
                                color: Colors.white.withAlpha(150),
                                fontSize: 9.5,
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
              ),

              // Button: New Chat
              Padding(
                padding: const EdgeInsets.all(12.0),
                child: ElevatedButton.icon(
                  onPressed: () {
                    Navigator.of(context).pop();
                    _openNewSessionDialog();
                  },
                  icon: const Icon(Icons.add, size: 18),
                  label: const Text('+ สนทนาใหม่ (เลือกความจำนง)'),
                  style: ElevatedButton.styleFrom(
                    backgroundColor: AppColors.primary,
                    foregroundColor: Colors.white,
                    minimumSize: const Size.fromHeight(44),
                    shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(10)),
                  ),
                ),
              ),

              const Padding(
                padding: EdgeInsets.symmetric(horizontal: 16, vertical: 4),
                child: Align(
                  alignment: Alignment.centerLeft,
                  child: Text(
                    'ประวัติโครงการ & บทสนทนาล่าสุด (Recents)',
                    style: TextStyle(fontSize: 11, fontWeight: FontWeight.bold, color: Colors.grey),
                  ),
                ),
              ),

              // List of Sessions with clean Vector Icons
              Expanded(
                child: _sessions.isEmpty
                    ? Center(
                        child: Text(
                          'ยังไม่มีประวัติการสนทนา',
                          style: TextStyle(color: Colors.grey[500]),
                        ),
                      )
                    : ListView.builder(
                        itemCount: _sessions.length,
                        itemBuilder: (context, idx) {
                          final sess = _sessions[idx];
                          final isSelected = _currentSession?.id == sess.id;
                          final intentInfo = _getIntentInfo(sess.intent);

                          return ListTile(
                            dense: true,
                            selected: isSelected,
                            selectedTileColor: isDark
                                ? const Color(0xFF242C33)
                                : AppColors.primary.withAlpha(20),
                            leading: Container(
                              width: 32,
                              height: 32,
                              decoration: BoxDecoration(
                                color: intentInfo.color.withAlpha(25),
                                borderRadius: BorderRadius.circular(8),
                              ),
                              child: Icon(intentInfo.icon, size: 16, color: intentInfo.color),
                            ),
                            title: Text(
                              sess.title,
                              maxLines: 1,
                              overflow: TextOverflow.ellipsis,
                              style: TextStyle(
                                fontWeight: isSelected ? FontWeight.bold : FontWeight.normal,
                                fontSize: 13,
                              ),
                            ),
                            subtitle: Text(
                              intentInfo.label,
                              style: TextStyle(
                                fontSize: 11,
                                fontWeight: FontWeight.w500,
                                color: intentInfo.color,
                              ),
                            ),
                            trailing: IconButton(
                              icon: const Icon(Icons.delete_outline, size: 18),
                              color: Colors.grey[400],
                              onPressed: () async {
                                final confirm = await showDialog<bool>(
                                  context: context,
                                  builder: (ctx) => AlertDialog(
                                    title: const Text('ลบการสนทนานี้?'),
                                    content: Text('คุณต้องการลบ "${sess.title}" หรือไม่?'),
                                    actions: [
                                      TextButton(
                                        onPressed: () => Navigator.of(ctx).pop(false),
                                        child: const Text('ยกเลิก'),
                                      ),
                                      TextButton(
                                        onPressed: () => Navigator.of(ctx).pop(true),
                                        child: const Text('ลบ', style: TextStyle(color: Colors.red)),
                                      ),
                                    ],
                                  ),
                                );
                                if (confirm == true) {
                                  await widget.apiService.deleteSession(sess.id);
                                  _loadSessions();
                                }
                              },
                            ),
                            onTap: () {
                              Navigator.of(context).pop();
                              _selectSession(sess);
                            },
                          );
                        },
                      ),
              ),

              const Divider(height: 1),

              // Drawer Footer Links
              ListTile(
                dense: true,
                leading: const Icon(Icons.person_pin_outlined, size: 20),
                title: const Text('โปรไฟล์ผู้ใช้งาน (User Profile)'),
                onTap: () {
                  Navigator.of(context).pop();
                  _openProfileSheet();
                },
              ),
              ListTile(
                dense: true,
                leading: const Icon(Icons.settings_outlined, size: 20),
                title: const Text('ตั้งค่าระบบ (Settings)'),
                onTap: () {
                  Navigator.of(context).pop();
                  _openSettings();
                },
              ),
            ],
          ),
        ),
      ),

      // Main Chat Body
      body: Column(
        children: [
          // Project Context Banner (Clean & Compact)
          if (_currentSession != null)
            Container(
              padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 7),
              decoration: BoxDecoration(
                color: isDark ? const Color(0xFF1E262C) : const Color(0xFFF1F5F9),
                border: const Border(bottom: BorderSide(color: Colors.black12)),
              ),
              child: Row(
                children: [
                  Icon(
                    currentIntent.icon,
                    size: 14,
                    color: currentIntent.color,
                  ),
                  const SizedBox(width: 6),
                  Expanded(
                    child: Text(
                      _currentSession!.folderPath.isNotEmpty
                          ? 'โฟลเดอร์: ${_cleanFolderName(_currentSession!.folderPath)}'
                          : 'โครงการ: ${_currentSession!.title}',
                      style: TextStyle(
                        fontSize: 11.5,
                        fontWeight: FontWeight.w500,
                        color: isDark ? Colors.grey[300] : Colors.grey[800],
                      ),
                      maxLines: 1,
                      overflow: TextOverflow.ellipsis,
                    ),
                  ),
                  InkWell(
                    onTap: _openMemorySheet,
                    borderRadius: BorderRadius.circular(6),
                    child: Container(
                      padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 2),
                      decoration: BoxDecoration(
                        color: AppColors.accent.withAlpha(20),
                        borderRadius: BorderRadius.circular(6),
                      ),
                      child: Row(
                        mainAxisSize: MainAxisSize.min,
                        children: [
                          const Icon(Icons.history_edu, size: 13, color: AppColors.accent),
                          const SizedBox(width: 4),
                          Text(
                            'Memory.md',
                            style: TextStyle(
                              fontSize: 10.5,
                              fontWeight: FontWeight.bold,
                              color: isDark ? Colors.orange[200] : AppColors.accent,
                            ),
                          ),
                        ],
                      ),
                    ),
                  ),
                ],
              ),
            ),

          // Message List
          Expanded(
            child: _messages.isEmpty
                ? _buildEmptyState()
                : ListView.builder(
                    controller: _scrollController,
                    padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 14),
                    itemCount: _messages.length,
                    itemBuilder: (context, idx) {
                      final msg = _messages[idx];
                      return _buildMessageBubble(msg);
                    },
                  ),
          ),

          // Thinking / Loading indicator
          if (_isLoading)
            Container(
              padding: const EdgeInsets.symmetric(horizontal: 20, vertical: 10),
              alignment: Alignment.centerLeft,
              child: Row(
                mainAxisSize: MainAxisSize.min,
                children: [
                  const SizedBox(
                    width: 14,
                    height: 14,
                    child: CircularProgressIndicator(strokeWidth: 2, color: AppColors.accent),
                  ),
                  const SizedBox(width: 10),
                  Text(
                    'Rnai AI กำลังคิดและประมวลผลคำตอบ...',
                    style: TextStyle(
                      fontSize: 12,
                      fontStyle: FontStyle.italic,
                      color: isDark ? Colors.grey[400] : Colors.grey[600],
                    ),
                  ),
                ],
              ),
            ),

          // Listening status notification
          if (_isListening)
            Container(
              width: double.infinity,
              padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
              color: Colors.red.withAlpha(30),
              child: Row(
                children: [
                  ScaleTransition(
                    scale: _micPulseAnimation,
                    child: const Icon(Icons.mic, color: Colors.red, size: 20),
                  ),
                  const SizedBox(width: 8),
                  Expanded(
                    child: Text(
                      _listeningStatusText,
                      style: const TextStyle(fontSize: 12, color: Colors.red, fontWeight: FontWeight.w600),
                    ),
                  ),
                  TextButton(
                    onPressed: _toggleMic,
                    child: const Text('หยุดฟัง', style: TextStyle(color: Colors.red)),
                  ),
                ],
              ),
            ),

          // Bottom Input Bar
          _buildInputBar(isDark),
        ],
      ),
    );
  }

  Widget _buildEmptyState() {
    final avatarColor = _avatarColors[_userProfile.avatarIndex % _avatarColors.length];

    return Center(
      child: SingleChildScrollView(
        padding: const EdgeInsets.all(24),
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            Container(
              width: 68,
              height: 68,
              decoration: BoxDecoration(
                shape: BoxShape.circle,
                color: avatarColor.withAlpha(30),
              ),
              child: Icon(Icons.forum_outlined, size: 34, color: avatarColor),
            ),
            const SizedBox(height: 14),
            Text(
              _userProfile.name.startsWith('คุณ')
                  ? 'สวัสดีครับ ${_userProfile.name}'
                  : 'สวัสดีครับคุณ ${_userProfile.name}',
              style: const TextStyle(fontSize: 18, fontWeight: FontWeight.bold),
              textAlign: TextAlign.center,
            ),
            const SizedBox(height: 4),
            if (_userProfile.role.isNotEmpty || _userProfile.organization.isNotEmpty)
              Text(
                '${_userProfile.role} • ${_userProfile.organization}',
                style: TextStyle(fontSize: 12, color: Colors.grey[600], fontWeight: FontWeight.w500),
                textAlign: TextAlign.center,
              ),
            const SizedBox(height: 8),
            Text(
              'พิมพ์คำถาม หรือกดไมค์เพื่อสั่งการด้วยเสียง\nบันทึกและซิงค์ Memory.md ประจำโครงการอัตโนมัติ',
              style: TextStyle(fontSize: 11.5, color: Colors.grey[500]),
              textAlign: TextAlign.center,
            ),
            const SizedBox(height: 20),
            Wrap(
              spacing: 8,
              runSpacing: 8,
              alignment: WrapAlignment.center,
              children: [
                ActionChip(
                  avatar: const Icon(Icons.auto_awesome, size: 15, color: Color(0xFF1E88E5)),
                  label: const Text('สรุปเนื้อหาหลักวันนี้', style: TextStyle(fontSize: 12)),
                  onPressed: () => _sendMessage('ช่วยสรุปภาพรวมและประเด็นสำคัญสำหรับวันนี้ให้หน่อย'),
                ),
                ActionChip(
                  avatar: const Icon(Icons.lightbulb_outline, size: 15, color: Color(0xFFFB8C00)),
                  label: const Text('เสนอแนวทางแก้ปัญหา', style: TextStyle(fontSize: 12)),
                  onPressed: () => _sendMessage('ช่วยระดมสมองและเสนอไอเดียแก้ปัญหาให้ที'),
                ),
                ActionChip(
                  avatar: const Icon(Icons.code, size: 15, color: Color(0xFF8E24AA)),
                  label: const Text('ช่วยตรวจสอบโค้ด', style: TextStyle(fontSize: 12)),
                  onPressed: () => _sendMessage('ช่วยเขียนโค้ดและแนะนำแนวทาง Best Practice ให้หน่อย'),
                ),
              ],
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildMessageBubble(ChatMessage msg) {
    final isUser = msg.isUser;
    final isDark = Theme.of(context).brightness == Brightness.dark;
    final userAvatarColor = _avatarColors[_userProfile.avatarIndex % _avatarColors.length];

    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 6),
      child: Row(
        mainAxisAlignment: isUser ? MainAxisAlignment.end : MainAxisAlignment.start,
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          if (!isUser) ...[
            CircleAvatar(
              radius: 15,
              backgroundColor: AppColors.primary,
              child: const Text('R', style: TextStyle(color: Colors.white, fontSize: 12, fontWeight: FontWeight.bold)),
            ),
            const SizedBox(width: 8),
          ],
          Flexible(
            child: Container(
              constraints: BoxConstraints(
                maxWidth: MediaQuery.of(context).size.width * 0.82,
              ),
              padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 10),
              decoration: BoxDecoration(
                color: isUser
                    ? AppColors.primary
                    : (isDark ? const Color(0xFF242C33) : const Color(0xFFF1F5F9)),
                borderRadius: BorderRadius.only(
                  topLeft: const Radius.circular(16),
                  topRight: const Radius.circular(16),
                  bottomLeft: Radius.circular(isUser ? 16 : 4),
                  bottomRight: Radius.circular(isUser ? 4 : 16),
                ),
              ),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  if (isUser)
                    Text(
                      msg.content,
                      style: const TextStyle(color: Colors.white, fontSize: 13.5),
                    )
                  else
                    MarkdownBody(
                      data: _cleanMarkdownContent(msg.content),
                      selectable: true,
                      styleSheet: MarkdownStyleSheet.fromTheme(Theme.of(context)).copyWith(
                        p: TextStyle(
                          fontSize: 13.5,
                          color: isDark ? Colors.white70 : Colors.black87,
                          fontFamilyFallback: AppTheme.thaiFontFallbacks,
                        ),
                        h1: const TextStyle(
                          fontWeight: FontWeight.bold,
                          fontFamilyFallback: AppTheme.thaiFontFallbacks,
                        ),
                        h2: const TextStyle(
                          fontWeight: FontWeight.bold,
                          fontFamilyFallback: AppTheme.thaiFontFallbacks,
                        ),
                        h3: const TextStyle(
                          fontWeight: FontWeight.bold,
                          fontFamilyFallback: AppTheme.thaiFontFallbacks,
                        ),
                        listBullet: const TextStyle(
                          fontFamilyFallback: AppTheme.thaiFontFallbacks,
                        ),
                        code: TextStyle(
                          backgroundColor: isDark ? Colors.black38 : const Color(0xFFE2E8F0),
                          fontFamily: 'monospace',
                          fontSize: 12,
                        ),
                        codeblockDecoration: BoxDecoration(
                          color: isDark ? const Color(0xFF15191C) : const Color(0xFFE2E8F0),
                          borderRadius: BorderRadius.circular(8),
                        ),
                      ),
                    ),
                  if (!isUser) ...[
                    const SizedBox(height: 6),
                    Row(
                      mainAxisAlignment: MainAxisAlignment.end,
                      children: [
                        InkWell(
                          onTap: () {
                            Clipboard.setData(ClipboardData(text: msg.content));
                            ScaffoldMessenger.of(context).showSnackBar(
                              const SnackBar(content: Text('คัดลอกข้อความแล้ว'), duration: Duration(seconds: 1)),
                            );
                          },
                          child: Icon(
                            Icons.copy_rounded,
                            size: 14,
                            color: isDark ? Colors.grey[500] : Colors.grey[600],
                          ),
                        ),
                      ],
                    ),
                  ],
                ],
              ),
            ),
          ),
          if (isUser) ...[
            const SizedBox(width: 8),
            CircleAvatar(
              radius: 15,
              backgroundColor: userAvatarColor,
              child: Text(
                _userProfile.name.isNotEmpty
                    ? _userProfile.name.characters.first.toUpperCase()
                    : 'U',
                style: const TextStyle(color: Colors.white, fontSize: 12, fontWeight: FontWeight.bold),
              ),
            ),
          ],
        ],
      ),
    );
  }

  Widget _buildInputBar(bool isDark) {
    return Container(
      padding: EdgeInsets.only(
        left: 10,
        right: 10,
        top: 8,
        bottom: MediaQuery.of(context).padding.bottom + 8,
      ),
      decoration: BoxDecoration(
        color: Theme.of(context).cardColor,
        border: const Border(top: BorderSide(color: Colors.black12)),
      ),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.end,
        children: [
          IconButton(
            icon: const Icon(Icons.attach_file_rounded),
            tooltip: 'แนบเอกสาร',
            color: AppColors.primary,
            onPressed: _openDocHubSheet,
          ),
          AnimatedBuilder(
            animation: _micPulseAnimation,
            builder: (context, child) {
              return Transform.scale(
                scale: _isListening ? _micPulseAnimation.value : 1.0,
                child: IconButton(
                  icon: Icon(
                    _isListening ? Icons.mic : Icons.mic_none,
                    color: _isListening ? Colors.red : (isDark ? Colors.white70 : Colors.black87),
                  ),
                  tooltip: _isListening ? 'แตะเพื่อหยุดบันทึกเสียง' : 'แตะเพื่อพูดด้วยเสียง',
                  onPressed: _toggleMic,
                ),
              );
            },
          ),
          Expanded(
            child: TextField(
              controller: _inputController,
              minLines: 1,
              maxLines: 4,
              textInputAction: TextInputAction.send,
              onSubmitted: (_) => _sendMessage(),
              decoration: InputDecoration(
                hintText: 'พิมพ์ข้อความ หรือกดไมค์...',
                filled: true,
                fillColor: isDark ? const Color(0xFF242C33) : const Color(0xFFF1F5F9),
                contentPadding: const EdgeInsets.symmetric(horizontal: 14, vertical: 10),
                border: OutlineInputBorder(
                  borderRadius: BorderRadius.circular(20),
                  borderSide: BorderSide.none,
                ),
              ),
            ),
          ),
          const SizedBox(width: 6),
          CircleAvatar(
            backgroundColor: AppColors.accent,
            radius: 20,
            child: IconButton(
              icon: const Icon(Icons.send_rounded, color: Colors.white, size: 18),
              onPressed: () => _sendMessage(),
            ),
          ),
        ],
      ),
    );
  }
}
