import 'package:flutter/material.dart';

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
      backgroundColor: Colors.white,
      appBar: AppBar(
        backgroundColor: Colors.white,
        foregroundColor: Colors.black,
        centerTitle: true,
        elevation: 0,
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
              backgroundColor: themeColor.withOpacity(0.2),
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
      bottomNavigationBar: BottomNavigationBar(
        backgroundColor: Colors.white,
        currentIndex: 1,
        type: BottomNavigationBarType.fixed,
        selectedItemColor: const Color(0xFF010186),
        unselectedItemColor: Colors.grey,
        onTap: (index) {
          switch (index) {
            case 0:
              Navigator.pushNamed(context, '/main');
              break;
            case 1:
              break;
            case 2:
              Navigator.pushNamed(context, '/contract_info_step');
              break;
            case 3:
              Navigator.pushNamed(context, '/my');
              break;
          }
        },
        items: const [
          BottomNavigationBarItem(
            icon: ImageIcon(AssetImage('assets/home_icon.png')),
            label: '홈',
          ),
          BottomNavigationBarItem(
            icon: ImageIcon(AssetImage('assets/analysis_solid_icon.png')),
            label: '위험도 분석',
          ),
          BottomNavigationBarItem(
            icon: ImageIcon(AssetImage('assets/chart_underbar.png')),
            label: '계약서 정보',
          ),
          BottomNavigationBarItem(
            icon: ImageIcon(AssetImage('assets/mypage_icon.png')),
            label: '마이페이지',
          ),
        ],
      ),
    );
  }
}
