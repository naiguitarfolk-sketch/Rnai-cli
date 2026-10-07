class SessionInfo {
  final String id;
  final String title;
  final String model;
  final String intent;
  final String prompt;
  final String context;
  final String folderPath;
  final String memoryPath;
  final int count;
  final double updated;

  SessionInfo({
    required this.id,
    required this.title,
    this.model = '',
    this.intent = '',
    this.prompt = '',
    this.context = '',
    this.folderPath = '',
    this.memoryPath = '',
    this.count = 0,
    this.updated = 0,
  });

  factory SessionInfo.fromJson(Map<String, dynamic> json) {
    return SessionInfo(
      id: json['id'] ?? '',
      title: json['title'] ?? 'การสนทนา',
      model: json['model'] ?? '',
      intent: json['intent'] ?? '',
      prompt: json['prompt'] ?? '',
      context: json['context'] ?? '',
      folderPath: json['folder_path'] ?? '',
      memoryPath: json['memory_path'] ?? '',
      count: json['count'] ?? 0,
      updated: (json['updated'] is num) ? (json['updated'] as num).toDouble() : 0.0,
    );
  }
}
