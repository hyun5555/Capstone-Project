import 'package:capstone_project/screens/address_search.dart';
import 'package:capstone_project/screens/risk_result.dart';
import 'package:capstone_project/services/api_service.dart';
import 'package:capstone_project/theme/app_theme.dart';
import 'package:capstone_project/widgets/app_bottom_navigation.dart';
import 'package:file_picker/file_picker.dart';
import 'package:flutter/material.dart';

class RiskAnalysisPage extends StatefulWidget {
  const RiskAnalysisPage({super.key});

  @override
  State<RiskAnalysisPage> createState() => _RiskAnalysisPageState();
}

class _RiskAnalysisPageState extends State<RiskAnalysisPage> {
  static const _maxPdfBytes = 20 * 1024 * 1024;

  final priceController = TextEditingController();
  final addressController = TextEditingController();
  Map<String, dynamic>? selectedAddressData;
  PlatformFile? registryPdf;
  PlatformFile? buildingPdf;
  bool _isAnalyzing = false;

  @override
  void dispose() {
    priceController.dispose();
    addressController.dispose();
    super.dispose();
  }

  void _message(String text) {
    ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(text)));
  }

  Future<void> _pickPdf({required bool registry}) async {
    final result = await FilePicker.platform.pickFiles(
      type: FileType.custom,
      allowedExtensions: const ['pdf'],
      allowMultiple: false,
    );
    if (result == null || result.files.isEmpty || !mounted) return;
    final file = result.files.single;
    if (file.size > _maxPdfBytes) {
      _message('PDF는 파일당 20MB 이하여야 합니다.');
      return;
    }
    setState(() {
      if (registry) {
        registryPdf = file;
      } else {
        buildingPdf = file;
      }
    });
  }

  Future<void> _selectAddress() async {
    final selected = await Navigator.push(
      context,
      MaterialPageRoute(builder: (_) => const AddressSearchPage()),
    );
    if (selected is Map && mounted) {
      setState(() {
        selectedAddressData = Map<String, dynamic>.from(selected);
        addressController.text = selectedAddressData!['fullAddress'] ?? '';
      });
    }
  }

  Future<void> _analyze() async {
    if (_isAnalyzing) return;
    final deposit = int.tryParse(priceController.text.replaceAll(',', ''));
    if (deposit == null || deposit <= 0) {
      _message('전세 보증금을 입력해 주세요.');
      return;
    }
    if (selectedAddressData == null) {
      _message('주소를 먼저 선택해 주세요.');
      return;
    }
    if (registryPdf == null || buildingPdf == null) {
      _message('등기부등본과 건축물대장 PDF를 모두 선택해 주세요.');
      return;
    }

    setState(() => _isAnalyzing = true);
    final response = await ApiService.analyzeJeonsePdf(
      registryPdf: registryPdf!,
      buildingPdf: buildingPdf!,
      address: selectedAddressData!['fullAddress'].toString(),
      deposit: deposit,
    );
    if (!mounted) return;

    final envelope = response['data'];
    final data = envelope is Map ? envelope['data'] : null;
    if (response['success'] != true || data is! Map) {
      setState(() => _isAnalyzing = false);
      _message('위험도 분석 실패: ${response['message'] ?? '응답 형식 오류'}');
      return;
    }

    await Navigator.push(
      context,
      MaterialPageRoute(
        builder:
            (_) => RiskResultPage(
              address: data['address']?.toString() ?? addressController.text,
              deposit: deposit,
              marketPrice:
                  data['market_price'] is Map &&
                          data['market_price']['value_won'] is num
                      ? (data['market_price']['value_won'] as num).toInt()
                      : null,
              riskScore:
                  data['risk_score'] is num
                      ? (data['risk_score'] as num).round()
                      : 0,
              notices:
                  data['notes'] is List
                      ? (data['notes'] as List)
                          .map((e) => e.toString())
                          .toList()
                      : const [],
              riskItems:
                  data['risk_items'] is List
                      ? (data['risk_items'] as List)
                          .whereType<Map>()
                          .map((item) => Map<String, dynamic>.from(item))
                          .toList()
                      : const [],
              documentProcessing:
                  data['document_processing'] is Map
                      ? Map<String, dynamic>.from(data['document_processing'])
                      : const {},
            ),
      ),
    );
    if (mounted) setState(() => _isAnalyzing = false);
  }

  @override
  Widget build(BuildContext context) {
    if (_isAnalyzing) return const _AnalysisLoadingScreen();
    return Scaffold(
      appBar: AppBar(
        title: const Text(
          '전세 위험도 분석',
          style: TextStyle(fontWeight: FontWeight.bold),
        ),
      ),
      body: SingleChildScrollView(
        padding: const EdgeInsets.fromLTRB(20, 8, 20, 32),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Container(
              padding: const EdgeInsets.all(18),
              decoration: BoxDecoration(
                color: AppColors.primary,
                borderRadius: BorderRadius.circular(20),
              ),
              child: Row(
                children: [
                  const Icon(
                    Icons.picture_as_pdf_outlined,
                    color: Colors.white,
                  ),
                  const SizedBox(width: 14),
                  Expanded(
                    child: Text(
                      '등기부등본과 건축물대장 PDF를 올리면 문서 근거를 바탕으로 위험 요소를 분석합니다.',
                      style: TextStyle(
                        color: Colors.white.withValues(alpha: 0.86),
                        height: 1.4,
                      ),
                    ),
                  ),
                ],
              ),
            ),
            const SizedBox(height: 18),
            _InputCard(
              step: '01',
              icon: Icons.payments_outlined,
              label: '전세 보증금',
              child: Row(
                children: [
                  Expanded(
                    child: TextField(
                      controller: priceController,
                      keyboardType: TextInputType.number,
                      decoration: const InputDecoration(hintText: '보증금 입력'),
                    ),
                  ),
                  const SizedBox(width: 8),
                  const Text('원', style: TextStyle(color: AppColors.muted)),
                ],
              ),
            ),
            const SizedBox(height: 12),
            _InputCard(
              step: '02',
              icon: Icons.location_on_outlined,
              label: '분석할 주소',
              child: TextField(
                controller: addressController,
                readOnly: true,
                onTap: _selectAddress,
                decoration: const InputDecoration(
                  hintText: '주소를 선택해 주세요',
                  suffixIcon: Icon(Icons.chevron_right_rounded),
                ),
              ),
            ),
            const SizedBox(height: 12),
            _FileCard(
              step: '03',
              label: '등기부등본 PDF',
              file: registryPdf,
              onPick: () => _pickPdf(registry: true),
              onRemove: () => setState(() => registryPdf = null),
            ),
            const SizedBox(height: 12),
            _FileCard(
              step: '04',
              label: '건축물대장 PDF',
              file: buildingPdf,
              onPick: () => _pickPdf(registry: false),
              onRemove: () => setState(() => buildingPdf = null),
            ),
            const SizedBox(height: 24),
            SizedBox(
              width: double.infinity,
              height: 54,
              child: ElevatedButton.icon(
                onPressed: _analyze,
                icon: const Icon(Icons.analytics_outlined),
                label: const Text('PDF 위험도 분석하기'),
              ),
            ),
          ],
        ),
      ),
      bottomNavigationBar: const AppBottomNavigation(currentIndex: 1),
    );
  }
}

class _InputCard extends StatelessWidget {
  const _InputCard({
    required this.step,
    required this.icon,
    required this.label,
    required this.child,
  });

  final String step;
  final IconData icon;
  final String label;
  final Widget child;

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: AppColors.surface,
        border: Border.all(color: AppColors.border),
        borderRadius: BorderRadius.circular(18),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              _StepBadge(step),
              const SizedBox(width: 9),
              Icon(icon, color: AppColors.primary, size: 20),
              const SizedBox(width: 7),
              Text(
                label,
                style: const TextStyle(
                  fontSize: 16,
                  fontWeight: FontWeight.w800,
                ),
              ),
            ],
          ),
          const SizedBox(height: 14),
          child,
        ],
      ),
    );
  }
}

class _FileCard extends StatelessWidget {
  const _FileCard({
    required this.step,
    required this.label,
    required this.file,
    required this.onPick,
    required this.onRemove,
  });

  final String step;
  final String label;
  final PlatformFile? file;
  final VoidCallback onPick;
  final VoidCallback onRemove;

  @override
  Widget build(BuildContext context) {
    return _InputCard(
      step: step,
      icon: Icons.description_outlined,
      label: label,
      child: Row(
        children: [
          Expanded(
            child: Text(
              file?.name ?? '선택된 파일이 없습니다.',
              maxLines: 1,
              overflow: TextOverflow.ellipsis,
              style: TextStyle(
                color: file == null ? AppColors.muted : Colors.black87,
              ),
            ),
          ),
          if (file != null)
            IconButton(
              tooltip: '파일 제거',
              onPressed: onRemove,
              icon: const Icon(Icons.close_rounded),
            ),
          OutlinedButton(
            onPressed: onPick,
            child: Text(file == null ? 'PDF 선택' : '다시 선택'),
          ),
        ],
      ),
    );
  }
}

class _StepBadge extends StatelessWidget {
  const _StepBadge(this.step);

  final String step;

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 5),
      decoration: BoxDecoration(
        color: AppColors.softBlue,
        borderRadius: BorderRadius.circular(8),
      ),
      child: Text(
        step,
        style: const TextStyle(
          color: AppColors.primary,
          fontSize: 11,
          fontWeight: FontWeight.w800,
        ),
      ),
    );
  }
}

class _AnalysisLoadingScreen extends StatelessWidget {
  const _AnalysisLoadingScreen();

  @override
  Widget build(BuildContext context) {
    return const Scaffold(
      body: Center(
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            CircularProgressIndicator(),
            SizedBox(height: 18),
            Text('PDF를 읽고 위험 요소를 분석하고 있습니다.'),
          ],
        ),
      ),
    );
  }
}
