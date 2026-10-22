import 'package:flutter/material.dart';
import 'package:shared_preferences/shared_preferences.dart';
import 'package:capstone_project/services/api_service.dart'; //
import 'package:capstone_project/theme/app_theme.dart';
import 'package:capstone_project/widgets/app_bottom_navigation.dart';

import 'edit_profile.dart';

class MyPage extends StatefulWidget {
  const MyPage({super.key});

  @override
  State<MyPage> createState() => _MyPageState();
}

class _MyPageState extends State<MyPage> {
  String userId = ''; // 🔹 추가됨
  String userName = '';
  String phoneNumber = '';
  String email = '';

  @override
  void initState() {
    super.initState();
    fetchUserInfo();
  }

  Future<void> fetchUserInfo() async {
    final prefs = await SharedPreferences.getInstance();
    final storedEmail = prefs.getString("email") ?? "";
    final token = prefs.getString("token") ?? "";

    if (storedEmail.isEmpty || token.isEmpty) {
      return;
    }

    final result = await ApiService.getCurrentUser(token);
    if (!mounted) return;
    if (result["success"] == true) {
      final data = result["data"];
      setState(() {
        userId = data["user_id"] ?? "";
        userName = data["username"] ?? "";
        phoneNumber = data["phone"] ?? "";
        email = data["email"] ?? "";
      });
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text(
          '마이페이지',
          style: TextStyle(fontWeight: FontWeight.bold, color: AppColors.text),
        ),
        leading: IconButton(
          icon: const Icon(Icons.arrow_back_ios),
          onPressed: () => Navigator.pop(context),
        ),
      ),
      body: Padding(
        padding: const EdgeInsets.symmetric(horizontal: 24, vertical: 20),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            // 프로필 정보
            Row(
              children: [
                const CircleAvatar(
                  radius: 30,
                  backgroundColor: Color(0xFFE0ECFF),
                  child: Icon(Icons.person, color: Colors.white, size: 40),
                ),
                const SizedBox(width: 16),
                Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      '$userName님', // ✅ userId로 표시
                      style: const TextStyle(
                        fontWeight: FontWeight.bold,
                        fontSize: 16,
                      ),
                    ),
                    const SizedBox(height: 4),
                    Text(
                      phoneNumber,
                      style: const TextStyle(color: Colors.grey),
                    ),
                    Text(email, style: const TextStyle(color: Colors.grey)),
                  ],
                ),
              ],
            ),
            const SizedBox(height: 30),

            // 회원 정보 변경
            InkWell(
              onTap: () {
                Navigator.push(
                  context,
                  MaterialPageRoute(builder: (_) => const EditProfilePage()),
                );
              },
              child: Row(
                children: const [
                  Icon(Icons.edit, color: Color(0xFF8CAEF2)),
                  SizedBox(width: 8),
                  Row(
                    children: [
                      Text(
                        '회원 정보 변경',
                        style: TextStyle(fontWeight: FontWeight.bold),
                      ),
                      SizedBox(width: 4),
                      Icon(Icons.chevron_right, color: Colors.grey, size: 18),
                    ],
                  ),
                ],
              ),
            ),
            const SizedBox(height: 30),

            // 최근 조회 내역
            Row(
              children: const [
                Icon(Icons.history, color: Color(0xFF8CAEF2)),
                SizedBox(width: 8),
                Text('최근 조회 내역', style: TextStyle(fontWeight: FontWeight.bold)),
              ],
            ),
            const SizedBox(height: 16),
            Container(
              height: 100,
              width: double.infinity,
              decoration: BoxDecoration(
                color: const Color(0xFFF8F8F8),
                borderRadius: BorderRadius.circular(12),
              ),
              alignment: Alignment.center,
              child: const Text(
                '최근 조회 내역이 없습니다.',
                style: TextStyle(color: Colors.grey),
              ),
            ),
          ],
        ),
      ),

      // 하단 네비게이션 바 (마이페이지 탭 활성화)
      bottomNavigationBar: const AppBottomNavigation(currentIndex: 3),
    );
  }
}
