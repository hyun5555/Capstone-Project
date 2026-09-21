import 'package:capstone_project/screens/create_account.dart';
import 'package:capstone_project/theme/app_theme.dart';
import 'package:flutter/material.dart';

class SignUpPage extends StatelessWidget {
  const SignUpPage({super.key});

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('회원가입')),
      body: SafeArea(
        top: false,
        child: Padding(
          padding: const EdgeInsets.all(28),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              const Spacer(),
              Container(
                width: 72,
                height: 72,
                alignment: Alignment.center,
                decoration: BoxDecoration(
                  color: AppColors.softBlue,
                  borderRadius: BorderRadius.circular(22),
                ),
                child: const Icon(
                  Icons.mark_email_read_outlined,
                  color: AppColors.primary,
                  size: 36,
                ),
              ),
              const SizedBox(height: 24),
              const Text(
                '이메일로 간편하게\n계정을 만들어 보세요',
                style: TextStyle(
                  fontSize: 27,
                  fontWeight: FontWeight.w800,
                  height: 1.3,
                ),
              ),
              const SizedBox(height: 10),
              const Text(
                '분석 내역을 안전하게 저장하고 언제든 다시 확인할 수 있어요.',
                style: TextStyle(color: AppColors.muted, height: 1.5),
              ),
              const Spacer(flex: 2),
              SizedBox(
                height: 54,
                child: ElevatedButton.icon(
                  onPressed: () {
                    Navigator.push(
                      context,
                      MaterialPageRoute(
                        builder: (_) => const CreateAccountPage(),
                      ),
                    );
                  },
                  icon: const Icon(Icons.email_outlined),
                  label: const Text('이메일로 가입하기'),
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}
