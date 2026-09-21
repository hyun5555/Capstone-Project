import 'package:capstone_project/theme/app_theme.dart';
import 'package:capstone_project/widgets/app_bottom_navigation.dart';
import 'package:flutter/material.dart';

class MainPage extends StatelessWidget {
  const MainPage({super.key});

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      body: SafeArea(
        child: SingleChildScrollView(
          padding: const EdgeInsets.fromLTRB(22, 24, 22, 36),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              const Text(
                '안전한 전세계약을\n차근차근 확인해 보세요',
                style: TextStyle(
                  color: AppColors.text,
                  fontSize: 27,
                  fontWeight: FontWeight.w800,
                  height: 1.3,
                  letterSpacing: -0.7,
                ),
              ),
              const SizedBox(height: 9),
              const Text(
                '문서 위험도와 주변 실거래가를 한곳에서 분석합니다.',
                style: TextStyle(color: AppColors.muted, fontSize: 14),
              ),
              const SizedBox(height: 26),
              _FeatureCard(
                title: '전세 사기\n위험도 분석',
                description: '등기부와 건축물 정보를 함께 확인해요',
                color: AppColors.primary,
                onTap: () => Navigator.pushNamed(context, '/risk_analysis'),
                illustration: Stack(
                  alignment: Alignment.center,
                  children: [
                    Image.asset(
                      'assets/main_circlechart.png',
                      width: 92,
                      height: 92,
                    ),
                    Positioned(
                      left: 0,
                      bottom: 0,
                      child: Image.asset(
                        'assets/main_search_icon.png',
                        width: 50,
                        height: 50,
                      ),
                    ),
                  ],
                ),
              ),
              const SizedBox(height: 14),
              _FeatureCard(
                title: '실거래가\n분석',
                description: '동네 시세와 전세가율을 비교해요',
                color: AppColors.accent,
                onTap:
                    () => Navigator.pushNamed(
                      context,
                      '/real_transaction_analysis',
                    ),
                illustration: Image.asset(
                  'assets/map_icon.png',
                  width: 100,
                  height: 100,
                ),
              ),
              const SizedBox(height: 24),
              const Text(
                '계약 도움',
                style: TextStyle(fontSize: 18, fontWeight: FontWeight.w800),
              ),
              const SizedBox(height: 11),
              Material(
                color: AppColors.surface,
                borderRadius: BorderRadius.circular(18),
                child: InkWell(
                  borderRadius: BorderRadius.circular(18),
                  onTap: () => Navigator.pushNamed(context, '/chat'),
                  child: Container(
                    padding: const EdgeInsets.all(16),
                    decoration: BoxDecoration(
                      border: Border.all(color: AppColors.border),
                      borderRadius: BorderRadius.circular(18),
                    ),
                    child: Row(
                      children: [
                        Container(
                          width: 48,
                          height: 48,
                          padding: const EdgeInsets.all(9),
                          decoration: BoxDecoration(
                            color: AppColors.softBlue,
                            borderRadius: BorderRadius.circular(14),
                          ),
                          child: Image.asset('assets/Light_bulb.png'),
                        ),
                        const SizedBox(width: 13),
                        const Expanded(
                          child: Column(
                            crossAxisAlignment: CrossAxisAlignment.start,
                            children: [
                              Text(
                                '전세 안심 상담',
                                style: TextStyle(
                                  fontSize: 16,
                                  fontWeight: FontWeight.w800,
                                ),
                              ),
                              SizedBox(height: 4),
                              Text(
                                '공식 자료를 바탕으로 계약 질문에 답해드려요',
                                style: TextStyle(
                                  fontSize: 12.5,
                                  color: AppColors.muted,
                                ),
                              ),
                            ],
                          ),
                        ),
                        const Icon(
                          Icons.arrow_forward_ios_rounded,
                          size: 16,
                          color: AppColors.muted,
                        ),
                      ],
                    ),
                  ),
                ),
              ),
            ],
          ),
        ),
      ),
      bottomNavigationBar: const AppBottomNavigation(currentIndex: 0),
    );
  }
}

class _FeatureCard extends StatelessWidget {
  const _FeatureCard({
    required this.title,
    required this.description,
    required this.color,
    required this.illustration,
    required this.onTap,
  });

  final String title;
  final String description;
  final Color color;
  final Widget illustration;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    return Material(
      color: color,
      borderRadius: BorderRadius.circular(22),
      clipBehavior: Clip.antiAlias,
      child: InkWell(
        onTap: onTap,
        child: SizedBox(
          height: 162,
          child: Padding(
            padding: const EdgeInsets.fromLTRB(22, 21, 18, 20),
            child: Row(
              children: [
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(
                        title,
                        style: const TextStyle(
                          color: Colors.white,
                          fontSize: 24,
                          fontWeight: FontWeight.w800,
                          height: 1.25,
                        ),
                      ),
                      const Spacer(),
                      Text(
                        description,
                        style: TextStyle(
                          color: Colors.white.withValues(alpha: 0.78),
                          fontSize: 12,
                        ),
                      ),
                    ],
                  ),
                ),
                SizedBox(width: 110, child: Center(child: illustration)),
              ],
            ),
          ),
        ),
      ),
    );
  }
}
