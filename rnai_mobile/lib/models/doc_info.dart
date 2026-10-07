class DocInfo {
  final String name;
  final String relativePath;
  final String sizeFormatted;
  final int sizeBytes;
  final String extension;
  final String modified;

  DocInfo({
    required this.name,
    required this.relativePath,
    required this.sizeFormatted,
    required this.sizeBytes,
    required this.extension,
    this.modified = '',
  });

  String get path => relativePath;

  factory DocInfo.fromJson(Map<String, dynamic> json) {
    return DocInfo(
      name: json['name'] ?? '',
      relativePath: json['relative_path'] ?? json['path'] ?? '',
      sizeFormatted: json['size_formatted'] ?? '',
      sizeBytes: json['size_bytes'] ?? 0,
      extension: json['extension'] ?? '',
      modified: json['modified'] ?? '',
    );
  }
}
