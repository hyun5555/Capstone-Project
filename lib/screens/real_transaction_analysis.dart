import 'package:flutter/material.dart';
import 'dart:convert';
import 'package:http/http.dart' as http; // 상단에 추가
import 'package:capstone_project/services/api_service.dart';


class RealTransactionAnalysisPage extends StatefulWidget {
  const RealTransactionAnalysisPage({super.key});

  @override
  State<RealTransactionAnalysisPage> createState() => _RealTransactionAnalysisPageState();
}

class _RealTransactionAnalysisPageState extends State<RealTransactionAnalysisPage> {
  String selectedPropertyType = '아파트';
  final List<String> _propertyTypes = ['아파트', '연립다세대'];

  final TextEditingController locationController = TextEditingController();
  final TextEditingController priceController = TextEditingController();

  bool isPriceUnknown = false;

  @override
  void dispose() {
    locationController.dispose();
    priceController.dispose();
    super.dispose();
  }

  void _onAnalyzePressed() async{
    final location = locationController.text;
    final price = isPriceUnknown ? '모름' : priceController.text;
    Map<String, dynamic>? jeonseRates;

    print('입력한 동네: $location');
    print('입력한 전세 금액: $price');
    print('선택된 건물 유형: $selectedPropertyType');

    try {
      final analysis_response = await http.post(
        ApiService.endpoint('/transaction/summary'),
        headers: {'Content-Type': 'application/json'},
        body: jsonEncode({
          'address': location,
          'house_type': selectedPropertyType,
        }),
      );

      if (analysis_response.statusCode == 200) {
        final result = jsonDecode(utf8.decode(analysis_response.bodyBytes));
        // 결과 확인
        print('실거래가 분석 결과: $result');

      final rentRateResponse = await http.post(
        ApiService.endpoint('/rent-rate'),
        headers: {'Content-Type': 'application/json'},
        body: jsonEncode({
          'address': location,
        }),
      );

        if (rentRateResponse.statusCode == 200) {
          final rentRateJson = jsonDecode(utf8.decode(rentRateResponse.bodyBytes));
          print('전세가율 응답: $rentRateJson');
          //print('rentRateResponse statusCode: ${rentRateResponse.statusCode}');
          //print('rentRateResponse body: ${utf8.decode(rentRateResponse.bodyBytes)}');
          if (rentRateJson['status'] != null && rentRateJson['status']['rate'] == 'ok') {
            jeonseRates = Map.from(rentRateJson)
              ..remove('status');
          }
        }else{
          _showErrorDialog('서버 응답 오류: ${rentRateResponse.statusCode}');
        }

        // 결과 페이지로 이동하며 결과 데이터 전달
        Navigator.pushNamed(
          context,
          '/real_transaction_report',
          arguments: {
            'result': result,
            'entered_price': price,
            'selectedPropertyType': selectedPropertyType,
            'jeonseRates': jeonseRates,
          },
        );

      } else {
        print('API 요청 실패: ${analysis_response.body}');
        _showErrorDialog('서버 응답 오류: ${analysis_response.statusCode}');
      }
    } catch (e) {
      print('요청 중 오류 발생: $e');
      _showErrorDialog('서버 요청 중 오류가 발생했습니다.');
    }

  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: Colors.white,
      appBar: AppBar(
        backgroundColor: Colors.white,
        foregroundColor: Colors.black,
        centerTitle: true,
        elevation: 0,
        title: const Text(
          '실거래가 분석',
          style: TextStyle(fontWeight: FontWeight.bold),
        ),
        leading: IconButton(
          icon: const Icon(Icons.arrow_back_ios),
          onPressed: () => Navigator.pop(context),
        ),
      ),
      body: SingleChildScrollView(
        padding: const EdgeInsets.all(20),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            _buildInputSection(
              imagePath: 'assets/Home.png',
              label: '이사 가고 싶은\n동네를 입력하세요',
              controller: locationController,
              hint: 'ex) 서울특별시 송파구 잠실동',
            ),
            SizedBox(height: 24),
            _buildDropdownSection(
              imagePath: 'assets/Building.png',
              label: '전세 건물 유형을 선택하세요',
              dropdown: DropdownButtonFormField<String>(
                value: selectedPropertyType,
                items: _propertyTypes.map((type) {
                  return DropdownMenuItem(
                    value: type,
                    child: Text(type),
                  );
                }).toList(),
                onChanged: (value) {
                  setState(() {
                    selectedPropertyType = value!;
                  });
                },
                decoration: InputDecoration(
                  filled: true,
                  fillColor: Colors.white,
                  contentPadding: const EdgeInsets.symmetric(horizontal: 12, vertical: 14),
                  border: OutlineInputBorder(
                    borderRadius: BorderRadius.circular(12),
                    borderSide: const BorderSide(color: Color(0xFFE0E0E0)),
                  ),
                  enabledBorder: OutlineInputBorder(
                    borderRadius: BorderRadius.circular(12),
                    borderSide: const BorderSide(color: Color(0xFFE0E0E0)),
                  ),
                  focusedBorder: OutlineInputBorder(
                    borderRadius: BorderRadius.circular(12),
                    borderSide: const BorderSide(color: Color(0xFF010186)),
                  ),
                ),
              ),
            ),
            const SizedBox(height: 24),
            _buildInputSection(
              imagePath: 'assets/Money.png',
              label: '전세 금액을 입력해주세요',
              controller: priceController,
              hint: '',
              unit: '원',
              showCheckbox: true,
              checkboxValue: isPriceUnknown,
              onCheckboxChanged: (val) {
                setState(() {
                  isPriceUnknown = val ?? false;
                });
              },
              enabled: !isPriceUnknown,
            ),
            const SizedBox(height: 40),
            Center(
              child: IntrinsicWidth(
                child: ElevatedButton(
                  onPressed: _onAnalyzePressed,
                  style: ElevatedButton.styleFrom(
                    backgroundColor: const Color(0xFF010186),
                    padding: const EdgeInsets.symmetric(vertical: 14, horizontal: 20),
                    shape: RoundedRectangleBorder(
                      borderRadius: BorderRadius.circular(12),
                    ),
                  ),
                  child: const Text(
                    '실거래가 분석하기',
                    style: TextStyle(
                      fontSize: 16,
                      fontWeight: FontWeight.bold,
                      color: Colors.white,
                    ),
                  ),
                ),
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

  Widget _buildInputSection({
    required String imagePath,
    required String label,
    required TextEditingController controller,
    required String hint,
    String? unit,
    bool showCheckbox = false,
    bool checkboxValue = false,
    ValueChanged<bool?>? onCheckboxChanged,
    bool enabled = true,
  }) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Row(
          crossAxisAlignment: CrossAxisAlignment.center,
          children: [
            Padding(
              padding: const EdgeInsets.symmetric(horizontal: 10),
              child: Image.asset(imagePath, width: 40, height: 40),
            ),
            const SizedBox(width: 8),
            Text(
              label,
              style: const TextStyle(fontSize: 20, fontWeight: FontWeight.bold),
            ),
          ],
        ),
        const SizedBox(height: 10),
        Row(
          children: [
            Expanded(
              child: _buildInputField(
                controller: controller,
                hint: hint,
                enabled: enabled,
              ),
            ),
            if (unit != null) ...[
              const SizedBox(width: 8),
              Text(unit, style: const TextStyle(fontSize: 16)),
            ],
          ],
        ),
        if (showCheckbox)
          Row(
            children: [
              Checkbox(
                value: checkboxValue,
                onChanged: onCheckboxChanged,
              ),
              const Text('잘 모르겠어요'),
            ],
          ),
      ],
    );
  }
  Widget _buildDropdownSection({
    required String imagePath,
    required String label,
    required Widget dropdown,
  }) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Row(
          crossAxisAlignment: CrossAxisAlignment.center,
          children: [
            Padding(
              padding: const EdgeInsets.symmetric(horizontal: 10),
              child: Image.asset(imagePath, width: 40, height: 40),
            ),
            const SizedBox(width: 8),
            Text(
              label,
              style: const TextStyle(fontSize: 20, fontWeight: FontWeight.bold),
            ),
          ],
        ),
        const SizedBox(height: 10),
        dropdown,
      ],
    );
  }

  Widget _buildInputField({
    required TextEditingController controller,
    required String hint,
    bool enabled = true,
  }) {
    return TextField(
      controller: controller,
      enabled: enabled,
      decoration: InputDecoration(
        hintText: hint,
        filled: true,
        fillColor: Colors.white,
        contentPadding: const EdgeInsets.symmetric(horizontal: 12, vertical: 14),
        border: OutlineInputBorder(
          borderRadius: BorderRadius.circular(12),
          borderSide: const BorderSide(color: Color(0xFFE0E0E0)),
        ),
        enabledBorder: OutlineInputBorder(
          borderRadius: BorderRadius.circular(12),
          borderSide: const BorderSide(color: Color(0xFFE0E0E0)),
        ),
        focusedBorder: OutlineInputBorder(
          borderRadius: BorderRadius.circular(12),
          borderSide: const BorderSide(color: Color(0xFF010186)),
        ),
      ),
    );
  }
  void _showErrorDialog(String message) {
    showDialog(
      context: context,
      builder: (context) {
        return AlertDialog(
          title: Text('오류'),
          content: Text(message),
          actions: [
            TextButton(
              child: Text('확인'),
              onPressed: () => Navigator.pop(context),
            ),
          ],
        );
      },
    );
  }

}
