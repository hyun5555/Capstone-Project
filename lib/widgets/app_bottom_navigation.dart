import 'package:capstone_project/theme/app_theme.dart';
import 'package:flutter/material.dart';

class AppBottomNavigation extends StatelessWidget {
  const AppBottomNavigation({super.key, required this.currentIndex});

  final int currentIndex;

  static const _routes = [
    '/main',
    '/risk_analysis',
    '/contract_info_step',
    '/my',
  ];

  @override
  Widget build(BuildContext context) {
    return NavigationBar(
      selectedIndex: currentIndex,
      height: 72,
      backgroundColor: AppColors.surface,
      indicatorColor: AppColors.softBlue,
      labelBehavior: NavigationDestinationLabelBehavior.alwaysShow,
      onDestinationSelected: (index) {
        if (index == currentIndex) return;
        Navigator.pushReplacementNamed(context, _routes[index]);
      },
      destinations: const [
        NavigationDestination(
          icon: Icon(Icons.home_outlined),
          selectedIcon: Icon(Icons.home_rounded),
          label: '홈',
        ),
        NavigationDestination(
          icon: Icon(Icons.manage_search_outlined),
          selectedIcon: Icon(Icons.manage_search_rounded),
          label: '위험 분석',
        ),
        NavigationDestination(
          icon: Icon(Icons.fact_check_outlined),
          selectedIcon: Icon(Icons.fact_check_rounded),
          label: '계약 단계',
        ),
        NavigationDestination(
          icon: Icon(Icons.person_outline_rounded),
          selectedIcon: Icon(Icons.person_rounded),
          label: '마이',
        ),
      ],
    );
  }
}
