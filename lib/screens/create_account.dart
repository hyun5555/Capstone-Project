import 'package:capstone_project/services/api_service.dart';
import 'package:capstone_project/theme/app_theme.dart';
import 'package:flutter/material.dart';

class CreateAccountPage extends StatefulWidget {
  const CreateAccountPage({super.key});

  @override
  State<CreateAccountPage> createState() => _CreateAccountPageState();
}

class _CreateAccountPageState extends State<CreateAccountPage> {
  final TextEditingController idController = TextEditingController();
  final TextEditingController pwController = TextEditingController();
  final TextEditingController pwConfirmController = TextEditingController();
  final TextEditingController emailController = TextEditingController();
  final TextEditingController phoneController = TextEditingController();
  bool _loading = false;
  String? _error;

  @override
  void dispose() {
    idController.dispose();
    pwController.dispose();
    pwConfirmController.dispose();
    emailController.dispose();
    phoneController.dispose();
    super.dispose();
  }

  Future<void> _onSignUpPressed() async {
    final id = idController.text.trim();
    final password = pwController.text;
    final email = emailController.text.trim();
    final phone = phoneController.text.trim();

    if (password != pwConfirmController.text) {
      setState(() => _error = '비밀번호가 일치하지 않습니다.');
      return;
    }
    if (id.isEmpty || password.isEmpty || email.isEmpty || phone.isEmpty) {
      setState(() => _error = '모든 항목을 입력해 주세요.');
      return;
    }

    setState(() {
      _loading = true;
      _error = null;
    });
    try {
      final result = await ApiService.signUpEmail(
        email: email,
        username: id,
        password: password,
        phone: phone,
      );
      if (!mounted) return;
      if (result['success'] == true) {
        Navigator.pushReplacementNamed(context, '/login');
      } else {
        setState(() => _error = result['message']?.toString() ?? '가입에 실패했습니다.');
      }
    } catch (_) {
      if (mounted) setState(() => _error = '네트워크 오류가 발생했습니다.');
    } finally {
      if (mounted) setState(() => _loading = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('계정 만들기')),
      body: SafeArea(
        top: false,
        child: SingleChildScrollView(
          padding: const EdgeInsets.fromLTRB(24, 18, 24, 32),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              const Text(
                '기본 정보를 입력해 주세요',
                style: TextStyle(fontSize: 24, fontWeight: FontWeight.w800),
              ),
              const SizedBox(height: 7),
              const Text(
                '입력한 정보는 계정 확인에만 사용됩니다.',
                style: TextStyle(color: AppColors.muted),
              ),
              const SizedBox(height: 26),
              _AccountField(
                label: '아이디',
                controller: idController,
                hint: '사용할 아이디',
                icon: Icons.person_outline_rounded,
              ),
              _AccountField(
                label: '비밀번호',
                controller: pwController,
                hint: '비밀번호 입력',
                icon: Icons.lock_outline_rounded,
                obscureText: true,
              ),
              _AccountField(
                label: '비밀번호 확인',
                controller: pwConfirmController,
                hint: '비밀번호 다시 입력',
                icon: Icons.lock_reset_rounded,
                obscureText: true,
              ),
              _AccountField(
                label: '이메일',
                controller: emailController,
                hint: 'name@example.com',
                icon: Icons.email_outlined,
                keyboardType: TextInputType.emailAddress,
              ),
              _AccountField(
                label: '휴대폰 번호',
                controller: phoneController,
                hint: '010-0000-0000',
                icon: Icons.phone_outlined,
                keyboardType: TextInputType.phone,
              ),
              if (_error != null)
                Padding(
                  padding: const EdgeInsets.only(top: 2, bottom: 10),
                  child: Text(
                    _error!,
                    style: const TextStyle(
                      color: Colors.redAccent,
                      fontSize: 13,
                    ),
                  ),
                ),
              const SizedBox(height: 12),
              SizedBox(
                height: 54,
                child: ElevatedButton(
                  onPressed: _loading ? null : _onSignUpPressed,
                  child:
                      _loading
                          ? const SizedBox(
                            width: 21,
                            height: 21,
                            child: CircularProgressIndicator(
                              strokeWidth: 2,
                              color: Colors.white,
                            ),
                          )
                          : const Text('가입하기'),
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}

class _AccountField extends StatelessWidget {
  const _AccountField({
    required this.label,
    required this.controller,
    required this.hint,
    required this.icon,
    this.obscureText = false,
    this.keyboardType = TextInputType.text,
  });

  final String label;
  final TextEditingController controller;
  final String hint;
  final IconData icon;
  final bool obscureText;
  final TextInputType keyboardType;

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.only(bottom: 16),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Padding(
            padding: const EdgeInsets.only(left: 3, bottom: 7),
            child: Text(
              label,
              style: const TextStyle(fontSize: 13, fontWeight: FontWeight.w700),
            ),
          ),
          TextField(
            controller: controller,
            obscureText: obscureText,
            keyboardType: keyboardType,
            decoration: InputDecoration(hintText: hint, prefixIcon: Icon(icon)),
          ),
        ],
      ),
    );
  }
}
