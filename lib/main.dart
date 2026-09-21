import 'package:capstone_project/screens/chat.dart';
import 'package:capstone_project/screens/contract_info_step.dart';
import 'package:capstone_project/screens/create_account.dart';
import 'package:capstone_project/screens/edit_profile.dart';
import 'package:capstone_project/screens/login.dart';
import 'package:capstone_project/screens/mainpage.dart';
import 'package:capstone_project/screens/mypage.dart';
import 'package:capstone_project/screens/real_transaction_analysis.dart';
import 'package:capstone_project/screens/real_transaction_report.dart';
import 'package:capstone_project/screens/risk_analysis.dart';
import 'package:capstone_project/screens/risk_detail.dart';
import 'package:capstone_project/screens/risk_result.dart';
import 'package:capstone_project/screens/sign_up.dart';
import 'package:capstone_project/screens/splash.dart';
import 'package:capstone_project/theme/app_theme.dart';
import 'package:flutter/material.dart';

void main() => runApp(const MyApp());

class MyApp extends StatelessWidget {
  const MyApp({super.key});

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: '전세 안전 도우미',
      debugShowCheckedModeBanner: false,
      theme: AppTheme.light,
      initialRoute: '/splash',
      routes: {
        '/splash': (context) => const SplashPage(),
        '/login': (context) => const LoginPage(),
        '/sign_up': (context) => const SignUpPage(),
        '/create_account': (context) => const CreateAccountPage(),
        '/main': (context) => const MainPage(),
        '/chat': (context) => const Chat(),
        '/contract_info_step': (context) => const ContractInfoStepPage(),
        '/edit_profile': (context) => const EditProfilePage(),
        '/my': (context) => const MyPage(),
        '/real_transaction_analysis':
            (context) => const RealTransactionAnalysisPage(),
        '/real_transaction_report':
            (context) => const RealTransactionReportPage(),
        '/risk_analysis': (context) => const RiskAnalysisPage(),
        '/risk_detail':
            (context) => const RiskDetailPage(
              title: '위험도 분석',
              score: 85,
              themeColor: Colors.white,
              explanation: '리포트 설명 예시입니다.',
            ),
        '/risk_result':
            (context) => const RiskResultPage(
              address: '서울 강남구 역삼동 123-45',
              deposit: 100000000,
              marketPrice: 200000000,
              riskScore: 85,
              riskItems: [],
            ),
      },
    );
  }
}
