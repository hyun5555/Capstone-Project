import 'package:capstone_project/theme/app_theme.dart';
import 'package:capstone_project/widgets/app_bottom_navigation.dart';
import 'package:flutter/material.dart';

class RealTransactionReportPage extends StatefulWidget {
  const RealTransactionReportPage({super.key});

  @override
  State<RealTransactionReportPage> createState() =>
      _RealTransactionReportPageState();
}

class _RealTransactionReportPageState extends State<RealTransactionReportPage> {
  final TextEditingController _areaController = TextEditingController();
  bool _loaded = false;
  String location = '알 수 없음';
  String resultLabel = '분석불가';
  String period = '';
  String avgPrice = '';
  String avgDeposit = '';
  String topType = '';
  double topArea = 0;
  double depositPerM2 = 0;
  double estimatedDeposit = 0;
  double rate = 0;

  @override
  void didChangeDependencies() {
    super.didChangeDependencies();
    if (_loaded) return;
    _loaded = true;
    final args = ModalRoute.of(context)?.settings.arguments;
    if (args is! Map<String, dynamic>) return;
    final result =
        args['result'] is Map
            ? Map<String, dynamic>.from(args['result'] as Map)
            : <String, dynamic>{};
    location = result['region']?.toString() ?? '알 수 없음';
    resultLabel =
        result['status'] == 'ok'
            ? result['risk_level']?.toString() ?? '분석불가'
            : '분석불가';
    period = result['sale_period']?.toString() ?? '';
    final averageSale =
        (result['average_sale_per_m2'] as num?)?.toDouble() ?? 0;
    depositPerM2 = (result['average_deposit_per_m2'] as num?)?.toDouble() ?? 0;
    avgPrice = '${averageSale.toStringAsFixed(0)}만원/㎡';
    avgDeposit = '${depositPerM2.toStringAsFixed(0)}만원/㎡';
    topType = result['most_traded_name']?.toString() ?? '-';
    topArea = (result['most_traded_area'] as num?)?.toDouble() ?? 0;
    rate = (result['jeonse_ratio'] as num?)?.toDouble() ?? 0;
  }

  @override
  void dispose() {
    _areaController.dispose();
    super.dispose();
  }

  void _calculateEstimatedDeposit() {
    setState(() {
      final area = double.tryParse(_areaController.text) ?? 0;
      estimatedDeposit = depositPerM2 * area;
    });
  }

  @override
  Widget build(BuildContext context) {
    final resultColor = _analysisColor(resultLabel);
    return Scaffold(
      appBar: AppBar(
        title: const Text('실거래가 분석 리포트'),
        leading: IconButton(
          tooltip: '뒤로 가기',
          icon: const Icon(Icons.arrow_back_ios_new_rounded, size: 20),
          onPressed: () => Navigator.pop(context),
        ),
      ),
      body: SingleChildScrollView(
        padding: const EdgeInsets.fromLTRB(20, 8, 20, 32),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(
              location,
              style: const TextStyle(fontSize: 20, fontWeight: FontWeight.w800),
            ),
            const SizedBox(height: 14),
            _ScoreCard(
              label: resultLabel,
              value: rate,
              color: resultColor,
              caption: '최근 실거래 기준 전세가율',
            ),
            const SizedBox(height: 18),
            const Text(
              '거래 요약',
              style: TextStyle(fontSize: 18, fontWeight: FontWeight.w800),
            ),
            const SizedBox(height: 10),
            GridView.count(
              crossAxisCount: 2,
              shrinkWrap: true,
              physics: const NeverScrollableScrollPhysics(),
              mainAxisSpacing: 10,
              crossAxisSpacing: 10,
              childAspectRatio: 1.55,
              children: [
                _MetricCard(
                  icon: Icons.calendar_month_outlined,
                  label: '거래 기간',
                  value: period.isEmpty ? '-' : period,
                ),
                _MetricCard(
                  icon: Icons.sell_outlined,
                  label: '평균 매매가',
                  value: avgPrice,
                ),
                _MetricCard(
                  icon: Icons.key_outlined,
                  label: '평균 보증금',
                  value: avgDeposit,
                ),
                _MetricCard(
                  icon: Icons.apartment_rounded,
                  label: '최다 거래',
                  value: topType,
                ),
              ],
            ),
            const SizedBox(height: 18),
            Container(
              padding: const EdgeInsets.all(18),
              decoration: BoxDecoration(
                color: AppColors.surface,
                border: Border.all(color: AppColors.border),
                borderRadius: BorderRadius.circular(18),
              ),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  const Text(
                    '내 집 면적으로 예상 보증금 계산',
                    style: TextStyle(fontSize: 16, fontWeight: FontWeight.w800),
                  ),
                  const SizedBox(height: 6),
                  Text(
                    '최다 거래 면적 ${topArea.toStringAsFixed(1)}㎡ · 지역 평균 보증금 기준',
                    style: const TextStyle(
                      color: AppColors.muted,
                      fontSize: 12.5,
                    ),
                  ),
                  const SizedBox(height: 14),
                  Row(
                    children: [
                      Expanded(
                        child: TextField(
                          controller: _areaController,
                          keyboardType: TextInputType.number,
                          textInputAction: TextInputAction.done,
                          onSubmitted: (_) => _calculateEstimatedDeposit(),
                          decoration: const InputDecoration(
                            hintText: '전용면적',
                            suffixText: '㎡',
                          ),
                        ),
                      ),
                      const SizedBox(width: 9),
                      ElevatedButton(
                        onPressed: _calculateEstimatedDeposit,
                        child: const Text('계산'),
                      ),
                    ],
                  ),
                  if (estimatedDeposit > 0) ...[
                    const SizedBox(height: 14),
                    Container(
                      width: double.infinity,
                      padding: const EdgeInsets.all(14),
                      decoration: BoxDecoration(
                        color: AppColors.softBlue,
                        borderRadius: BorderRadius.circular(14),
                      ),
                      child: Text(
                        '예상 적정 보증금  ${estimatedDeposit.toStringAsFixed(0)}만원',
                        style: const TextStyle(
                          color: AppColors.primary,
                          fontSize: 16,
                          fontWeight: FontWeight.w800,
                        ),
                      ),
                    ),
                  ],
                ],
              ),
            ),
            const SizedBox(height: 12),
            const _InfoNotice(
              text:
                  '최근 신고된 실거래를 기준으로 한 참고값입니다. 같은 지역이라도 층, 면적, 건물 상태에 따라 실제 금액은 달라질 수 있습니다.',
            ),
          ],
        ),
      ),
      bottomNavigationBar: const AppBottomNavigation(currentIndex: 1),
    );
  }

  static Color _analysisColor(String label) {
    if (label == '안전') return const Color(0xFF37A66A);
    if (label == '주의') return const Color(0xFFE5A72F);
    return const Color(0xFFD95C66);
  }
}

class _ScoreCard extends StatelessWidget {
  const _ScoreCard({
    required this.label,
    required this.value,
    required this.color,
    required this.caption,
  });

  final String label;
  final double value;
  final Color color;
  final String caption;

  @override
  Widget build(BuildContext context) {
    return Container(
      width: double.infinity,
      padding: const EdgeInsets.all(22),
      decoration: BoxDecoration(
        color: AppColors.surface,
        border: Border.all(color: AppColors.border),
        borderRadius: BorderRadius.circular(22),
      ),
      child: Row(
        children: [
          SizedBox(
            width: 116,
            height: 116,
            child: Stack(
              alignment: Alignment.center,
              children: [
                SizedBox.expand(
                  child: CircularProgressIndicator(
                    value: (value / 100).clamp(0.0, 1.0).toDouble(),
                    strokeWidth: 10,
                    strokeCap: StrokeCap.round,
                    backgroundColor: color.withValues(alpha: 0.14),
                    valueColor: AlwaysStoppedAnimation<Color>(color),
                  ),
                ),
                Text(
                  '${value.toStringAsFixed(1)}%',
                  style: TextStyle(
                    color: color,
                    fontSize: 21,
                    fontWeight: FontWeight.w800,
                  ),
                ),
              ],
            ),
          ),
          const SizedBox(width: 20),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Container(
                  padding: const EdgeInsets.symmetric(
                    horizontal: 10,
                    vertical: 6,
                  ),
                  decoration: BoxDecoration(
                    color: color.withValues(alpha: 0.12),
                    borderRadius: BorderRadius.circular(20),
                  ),
                  child: Text(
                    label,
                    style: TextStyle(color: color, fontWeight: FontWeight.w800),
                  ),
                ),
                const SizedBox(height: 10),
                Text(
                  caption,
                  style: const TextStyle(color: AppColors.muted, height: 1.4),
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }
}

class _MetricCard extends StatelessWidget {
  const _MetricCard({
    required this.icon,
    required this.label,
    required this.value,
  });

  final IconData icon;
  final String label;
  final String value;

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.all(14),
      decoration: BoxDecoration(
        color: AppColors.surface,
        border: Border.all(color: AppColors.border),
        borderRadius: BorderRadius.circular(16),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        mainAxisAlignment: MainAxisAlignment.center,
        children: [
          Icon(icon, color: AppColors.accent, size: 20),
          const SizedBox(height: 7),
          Text(
            label,
            style: const TextStyle(color: AppColors.muted, fontSize: 11.5),
          ),
          const SizedBox(height: 3),
          Text(
            value,
            maxLines: 2,
            overflow: TextOverflow.ellipsis,
            style: const TextStyle(fontSize: 13.5, fontWeight: FontWeight.w800),
          ),
        ],
      ),
    );
  }
}

class _InfoNotice extends StatelessWidget {
  const _InfoNotice({required this.text});

  final String text;

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.all(14),
      decoration: BoxDecoration(
        color: AppColors.softBlue,
        borderRadius: BorderRadius.circular(14),
      ),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const Icon(
            Icons.info_outline_rounded,
            color: AppColors.primary,
            size: 19,
          ),
          const SizedBox(width: 9),
          Expanded(
            child: Text(
              text,
              style: const TextStyle(
                color: AppColors.muted,
                fontSize: 12.5,
                height: 1.45,
              ),
            ),
          ),
        ],
      ),
    );
  }
}
