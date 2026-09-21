import 'package:capstone_project/screens/mainpage.dart';
import 'package:capstone_project/screens/sign_up.dart';
import 'package:capstone_project/services/api_service.dart';
import 'package:capstone_project/theme/app_theme.dart';
import 'package:flutter/material.dart';
import 'package:shared_preferences/shared_preferences.dart';

class LoginPage extends StatefulWidget {
  const LoginPage({super.key});

  @override
  State<LoginPage> createState() => _LoginPageState();
}

class _LoginPageState extends State<LoginPage> {
  final TextEditingController _idController = TextEditingController();
  final TextEditingController _passwordController = TextEditingController();
  bool _loading = false;
  bool _hidePassword = true;
  String? _error;

  @override
  void dispose() {
    _idController.dispose();
    _passwordController.dispose();
    super.dispose();
  }

  Future<void> _onLoginPressed() async {
    final email = _idController.text.trim();
    final password = _passwordController.text;
    if (email.isEmpty || password.isEmpty) {
      setState(() => _error = '아이디와 비밀번호를 입력하세요.');
      return;
    }

    setState(() {
      _loading = true;
      _error = null;
    });
    final result = await ApiService.login(email: email, password: password);
    if (!mounted) return;
    setState(() => _loading = false);

    if (result['success'] != true) {
      setState(() => _error = result['message']?.toString() ?? '로그인에 실패했습니다.');
      return;
    }

    final data = result['data'];
    final prefs = await SharedPreferences.getInstance();
    await prefs.setString('userId', data['user']['user_id'].toString());
    await prefs.setString('token', data['access_token']);
    await prefs.setString('email', data['user']['email']);
    if (!mounted) return;
    Navigator.pushReplacement(
      context,
      MaterialPageRoute(builder: (_) => const MainPage()),
    );
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      body: SafeArea(
        child: Center(
          child: SingleChildScrollView(
            padding: const EdgeInsets.symmetric(horizontal: 28, vertical: 36),
            child: ConstrainedBox(
              constraints: const BoxConstraints(maxWidth: 420),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.stretch,
                children: [
                  Align(
                    alignment: Alignment.centerLeft,
                    child: Container(
                      width: 64,
                      height: 64,
                      alignment: Alignment.center,
                      decoration: BoxDecoration(
                        color: AppColors.primary,
                        borderRadius: BorderRadius.circular(20),
                      ),
                      child: const Icon(
                        Icons.home_work_outlined,
                        color: Colors.white,
                        size: 32,
                      ),
                    ),
                  ),
                  const SizedBox(height: 28),
                  const Text(
                    '안전한 전세계약의 시작',
                    style: TextStyle(
                      fontSize: 27,
                      fontWeight: FontWeight.w800,
                      letterSpacing: -0.7,
                    ),
                  ),
                  const SizedBox(height: 8),
                  const Text(
                    '계약 전 확인해야 할 정보를 간편하게 분석해 보세요.',
                    style: TextStyle(color: AppColors.muted, height: 1.45),
                  ),
                  const SizedBox(height: 36),
                  TextField(
                    controller: _idController,
                    textInputAction: TextInputAction.next,
                    decoration: const InputDecoration(
                      labelText: '아이디 또는 이메일',
                      prefixIcon: Icon(Icons.person_outline_rounded),
                    ),
                  ),
                  const SizedBox(height: 12),
                  TextField(
                    controller: _passwordController,
                    obscureText: _hidePassword,
                    textInputAction: TextInputAction.done,
                    onSubmitted: (_) => _onLoginPressed(),
                    decoration: InputDecoration(
                      labelText: '비밀번호',
                      prefixIcon: const Icon(Icons.lock_outline_rounded),
                      suffixIcon: IconButton(
                        tooltip: _hidePassword ? '비밀번호 보기' : '비밀번호 숨기기',
                        onPressed: () {
                          setState(() => _hidePassword = !_hidePassword);
                        },
                        icon: Icon(
                          _hidePassword
                              ? Icons.visibility_off_outlined
                              : Icons.visibility_outlined,
                        ),
                      ),
                    ),
                  ),
                  if (_error != null)
                    Padding(
                      padding: const EdgeInsets.only(top: 10, left: 4),
                      child: Text(
                        _error!,
                        style: const TextStyle(
                          color: Colors.redAccent,
                          fontSize: 13,
                        ),
                      ),
                    ),
                  const SizedBox(height: 22),
                  SizedBox(
                    height: 54,
                    child: ElevatedButton(
                      onPressed: _loading ? null : _onLoginPressed,
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
                              : const Text('로그인'),
                    ),
                  ),
                  const SizedBox(height: 18),
                  Row(
                    mainAxisAlignment: MainAxisAlignment.center,
                    children: [
                      const Text(
                        '처음 이용하시나요?',
                        style: TextStyle(color: AppColors.muted),
                      ),
                      TextButton(
                        onPressed: () {
                          Navigator.push(
                            context,
                            MaterialPageRoute(
                              builder: (_) => const SignUpPage(),
                            ),
                          );
                        },
                        child: const Text(
                          '회원가입',
                          style: TextStyle(fontWeight: FontWeight.w700),
                        ),
                      ),
                    ],
                  ),
                ],
              ),
            ),
          ),
        ),
      ),
    );
  }
}
