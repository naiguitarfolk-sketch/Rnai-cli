import 'package:shared_preferences/shared_preferences.dart';
import '../models/user_profile.dart';

class ProfileService {
  static const String _keyProfile = 'rnai_user_profile';

  static Future<UserProfile> loadProfile() async {
    final prefs = await SharedPreferences.getInstance();
    final jsonStr = prefs.getString(_keyProfile);
    if (jsonStr != null && jsonStr.isNotEmpty) {
      try {
        return UserProfile.fromJson(jsonStr);
      } catch (_) {}
    }
    return const UserProfile();
  }

  static Future<void> saveProfile(UserProfile profile) async {
    final prefs = await SharedPreferences.getInstance();
    await prefs.setString(_keyProfile, profile.toJson());
  }
}
