import 'package:flutter/material.dart';
import 'package:capstone_project/theme/app_theme.dart';
import 'package:capstone_project/widgets/app_bottom_navigation.dart';

class ContractInfoStepPage extends StatelessWidget {
  const ContractInfoStepPage({super.key});

  @override
  Widget build(BuildContext context) {
    final List<String> steps = [
      '매물 탐색 중이에요',
      '계약하고 싶은 집이 있어요',
      '계약서를 검토하고 있어요',
      '계약을 체결했어요',
      '잔금을 치렀어요 / 입주 준비 중이에요',
    ];

    return Scaffold(
      appBar: AppBar(
        title: const Text(
          '계약 정보 제공',
          style: TextStyle(
            fontWeight: FontWeight.bold,
            fontSize: 20,
            color: AppColors.text,
          ),
        ),
        centerTitle: true,
        leading: IconButton(
          icon: const Icon(Icons.arrow_back_ios),
          onPressed: () => Navigator.pop(context),
        ),
      ),
      body: SingleChildScrollView(
        padding: const EdgeInsets.all(24),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                Image.asset('assets/Document.png', width: 40, height: 40),
                const SizedBox(width: 10),
                const Text(
                  '현재 어떤 단계이신가요?',
                  style: TextStyle(fontSize: 20, fontWeight: FontWeight.bold),
                ),
              ],
            ),
            const SizedBox(height: 24),

            ...steps.map(
              (step) => Padding(
                padding: const EdgeInsets.symmetric(vertical: 6),
                child: SizedBox(
                  width: double.infinity,
                  child: ElevatedButton(
                    onPressed: () {
                      // TODO: 단계 선택 시 동작 추가
                    },
                    style: ElevatedButton.styleFrom(
                      backgroundColor: Colors.white,
                      foregroundColor: Colors.black,
                      side: const BorderSide(color: Color(0xFFE0E0E0)),
                      padding: const EdgeInsets.symmetric(vertical: 16),
                      shape: RoundedRectangleBorder(
                        borderRadius: BorderRadius.circular(30),
                      ),
                      elevation: 0,
                    ),
                    child: Text(
                      step,
                      textAlign: TextAlign.center,
                      style: const TextStyle(
                        fontSize: 16,
                        fontWeight: FontWeight.bold,
                      ),
                    ),
                  ),
                ),
              ),
            ),

            const SizedBox(height: 32),

            Center(
              child: ElevatedButton(
                onPressed: () {
                  // TODO: 계약 정보 도움 페이지 이동
                },
                style: ElevatedButton.styleFrom(
                  backgroundColor: AppColors.primary,
                  padding: const EdgeInsets.symmetric(
                    horizontal: 24,
                    vertical: 14,
                  ),
                  shape: RoundedRectangleBorder(
                    borderRadius: BorderRadius.circular(12),
                  ),
                ),
                child: const Text(
                  '계약 정보 도움 받으러 가기',
                  style: TextStyle(
                    fontSize: 16,
                    fontWeight: FontWeight.bold,
                    color: Colors.white,
                  ),
                ),
              ),
            ),
          ],
        ),
      ),

      bottomNavigationBar: const AppBottomNavigation(currentIndex: 2),
    );
  }
}
