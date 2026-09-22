import 'package:flutter/material.dart';
import 'package:capstone_project/widgets/app_bottom_navigation.dart';

class RiskDetailPage extends StatelessWidget {
  final String title;
  final int score;
  final String explanation;
  final Color themeColor;

  const RiskDetailPage({
    super.key,
    required this.title,
    required this.score,
    required this.explanation,
    required this.themeColor,
  });

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: Text(
          '$title 상세 리포트',
          style: const TextStyle(
            fontWeight: FontWeight.bold,
            color: Colors.black,
            fontSize: 16,
          ),
        ),
        leading: IconButton(
          icon: const Icon(Icons.arrow_back_ios),
          onPressed: () => Navigator.pop(context),
        ),
      ),
      body: Padding(
        padding: const EdgeInsets.all(20),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.center,
          children: [
            const SizedBox(height: 20),
            Text(
              '$score점',
              style: TextStyle(
                fontSize: 48,
                fontWeight: FontWeight.bold,
                color: themeColor,
              ),
            ),
            const SizedBox(height: 16),
            LinearProgressIndicator(
              value: score / 100,
              minHeight: 12,
              backgroundColor: themeColor.withValues(alpha: 0.2),
              valueColor: AlwaysStoppedAnimation<Color>(themeColor),
              borderRadius: BorderRadius.circular(10),
            ),
            const SizedBox(height: 40),

            /// 여기에 설명 추가
            Align(
              alignment: Alignment.centerLeft,
              child: Text(
                explanation,
                style: const TextStyle(fontSize: 14, height: 1.6),
              ),
            ),
          ],
        ),
      ),
      bottomNavigationBar: const AppBottomNavigation(currentIndex: 1),
    );
  }
}
