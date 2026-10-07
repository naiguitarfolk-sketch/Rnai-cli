import 'dart:convert';

class UserProfile {
  final String name;
  final String role;
  final String organization;
  final String email;
  final String aiCustomInstructions;
  final int avatarIndex;

  const UserProfile({
    this.name = 'คุณชนา',
    this.role = 'นักพัฒนา & นักวิจัย',
    this.organization = 'HomeServer Academy',
    this.email = 'chana@example.com',
    this.aiCustomInstructions =
        'ตอบด้วยภาษาไทยสุภาพ เป็นกันเอง มีโครงสร้างชัดเจน เน้นการปฏิบัติและอธิบายเหตุผลประกอบ',
    this.avatarIndex = 0,
  });

  UserProfile copyWith({
    String? name,
    String? role,
    String? organization,
    String? email,
    String? aiCustomInstructions,
    int? avatarIndex,
  }) {
    return UserProfile(
      name: name ?? this.name,
      role: role ?? this.role,
      organization: organization ?? this.organization,
      email: email ?? this.email,
      aiCustomInstructions:
          aiCustomInstructions ?? this.aiCustomInstructions,
      avatarIndex: avatarIndex ?? this.avatarIndex,
    );
  }

  Map<String, dynamic> toMap() {
    return {
      'name': name,
      'role': role,
      'organization': organization,
      'email': email,
      'aiCustomInstructions': aiCustomInstructions,
      'avatarIndex': avatarIndex,
    };
  }

  factory UserProfile.fromMap(Map<String, dynamic> map) {
    return UserProfile(
      name: map['name'] ?? 'คุณชนา',
      role: map['role'] ?? 'นักพัฒนา & นักวิจัย',
      organization: map['organization'] ?? 'HomeServer Academy',
      email: map['email'] ?? '',
      aiCustomInstructions: map['aiCustomInstructions'] ??
          'ตอบด้วยภาษาไทยสุภาพ เป็นกันเอง มีโครงสร้างชัดเจน เน้นการปฏิบัติและอธิบายเหตุผลประกอบ',
      avatarIndex: map['avatarIndex'] ?? 0,
    );
  }

  String toJson() => jsonEncode(toMap());

  factory UserProfile.fromJson(String source) =>
      UserProfile.fromMap(jsonDecode(source));
}
