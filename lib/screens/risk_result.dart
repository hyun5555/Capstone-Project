import 'package:capstone_project/screens/risk_detail.dart';
import 'package:capstone_project/theme/app_theme.dart';
import 'package:capstone_project/widgets/app_bottom_navigation.dart';
import 'package:flutter/material.dart';

class RiskResultPage extends StatelessWidget {
  const RiskResultPage({
    super.key,
    required this.address,
    required this.deposit,
    this.marketPrice,
    required this.riskScore,
    required this.riskItems,
    this.notices = const [],
    this.documentProcessing = const {},
  });

  final String address;
  final int deposit;
  final int? marketPrice;
  final int riskScore;
  final List<Map<String, dynamic>> riskItems;
  final List<String> notices;
  final Map<String, dynamic> documentProcessing;

  @override
  Widget build(BuildContext context) {
    final riskColor = getRiskColor(riskScore);
    return Scaffold(
      appBar: AppBar(
        title: const Text('전세 위험도 리포트'),
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
              address,
              style: const TextStyle(fontSize: 18, fontWeight: FontWeight.w800),
            ),
            const SizedBox(height: 14),
            _RiskScoreCard(score: riskScore, color: riskColor),
            if (documentProcessing.isNotEmpty) ...[
              const SizedBox(height: 12),
              _DocumentProcessingCard(data: documentProcessing),
            ],
            const SizedBox(height: 12),
            Row(
              children: [
                Expanded(
                  child: _MoneyCard(
                    label: '입력 보증금',
                    value: _formatWon(deposit),
                    icon: Icons.key_outlined,
                  ),
                ),
                const SizedBox(width: 10),
                Expanded(
                  child: _MoneyCard(
                    label: '추정 시세',
                    value:
                        marketPrice == null
                            ? '확인 불가'
                            : _formatWon(marketPrice!),
                    icon: Icons.home_work_outlined,
                  ),
                ),
              ],
            ),
            if (notices.isNotEmpty) ...[
              const SizedBox(height: 12),
              Container(
                width: double.infinity,
                padding: const EdgeInsets.all(14),
                decoration: BoxDecoration(
                  color: AppColors.softBlue,
                  borderRadius: BorderRadius.circular(14),
                ),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children:
                      notices
                          .map(
                            (notice) => Padding(
                              padding: const EdgeInsets.symmetric(vertical: 3),
                              child: Row(
                                crossAxisAlignment: CrossAxisAlignment.start,
                                children: [
                                  const Icon(
                                    Icons.info_outline_rounded,
                                    size: 17,
                                    color: AppColors.primary,
                                  ),
                                  const SizedBox(width: 7),
                                  Expanded(
                                    child: Text(
                                      notice,
                                      style: const TextStyle(
                                        color: AppColors.muted,
                                        fontSize: 12.5,
                                        height: 1.4,
                                      ),
                                    ),
                                  ),
                                ],
                              ),
                            ),
                          )
                          .toList(),
                ),
              ),
            ],
            const SizedBox(height: 24),
            const Text(
              '항목별 분석',
              style: TextStyle(fontSize: 18, fontWeight: FontWeight.w800),
            ),
            const SizedBox(height: 10),
            if (riskItems.isEmpty)
              const _EmptyAnalysis()
            else
              ...riskItems
                  .where(
                    (item) => item['title'] != null && item['score'] != null,
                  )
                  .map(
                    (item) => _RiskItemCard(
                      title: item['title'].toString().trim(),
                      score: (item['score'] as num?)?.round() ?? 0,
                      explanation:
                          item['explanation']?.toString() ?? '설명이 없습니다.',
                      onTap: () {
                        Navigator.push(
                          context,
                          MaterialPageRoute(
                            builder:
                                (_) => RiskDetailPage(
                                  title: item['title']?.toString() ?? '',
                                  score: (item['score'] as num?)?.round() ?? 0,
                                  explanation:
                                      item['explanation']?.toString() ?? '',
                                  evidence:
                                      item['evidence'] is List
                                          ? (item['evidence'] as List)
                                              .whereType<Map>()
                                              .map(
                                                (e) =>
                                                    Map<String, dynamic>.from(
                                                      e,
                                                    ),
                                              )
                                              .toList()
                                          : const [],
                                  themeColor: riskColor,
                                ),
                          ),
                        );
                      },
                    ),
                  ),
          ],
        ),
      ),
      bottomNavigationBar: const AppBottomNavigation(currentIndex: 1),
    );
  }

  static String _formatWon(int value) => '$value원';

  static Color getRiskColor(int score) {
    if (score <= 20) return const Color(0xFF37A66A);
    if (score <= 40) return const Color(0xFFE5A72F);
    if (score <= 60) return const Color(0xFFE77C88);
    return const Color(0xFFD95C66);
  }
}

class _RiskScoreCard extends StatelessWidget {
  const _RiskScoreCard({required this.score, required this.color});

  final int score;
  final Color color;

  @override
  Widget build(BuildContext context) {
    final label =
        score <= 20
            ? '안전'
            : score <= 40
            ? '주의'
            : '위험';
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
                    value: (score / 100).clamp(0.0, 1.0).toDouble(),
                    strokeWidth: 10,
                    strokeCap: StrokeCap.round,
                    backgroundColor: color.withValues(alpha: 0.14),
                    valueColor: AlwaysStoppedAnimation<Color>(color),
                  ),
                ),
                Text(
                  '$score점',
                  style: TextStyle(
                    color: color,
                    fontSize: 24,
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
                const Text(
                  '점수가 높을수록 확인이 필요한 위험 요소가 많습니다.',
                  style: TextStyle(color: AppColors.muted, height: 1.4),
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }
}

class _MoneyCard extends StatelessWidget {
  const _MoneyCard({
    required this.label,
    required this.value,
    required this.icon,
  });

  final String label;
  final String value;
  final IconData icon;

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.all(15),
      decoration: BoxDecoration(
        color: AppColors.surface,
        border: Border.all(color: AppColors.border),
        borderRadius: BorderRadius.circular(16),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Icon(icon, color: AppColors.accent, size: 20),
          const SizedBox(height: 8),
          Text(
            label,
            style: const TextStyle(color: AppColors.muted, fontSize: 11.5),
          ),
          const SizedBox(height: 3),
          Text(
            value,
            maxLines: 1,
            overflow: TextOverflow.ellipsis,
            style: const TextStyle(fontSize: 14, fontWeight: FontWeight.w800),
          ),
        ],
      ),
    );
  }
}

class _DocumentProcessingCard extends StatelessWidget {
  const _DocumentProcessingCard({required this.data});

  final Map<String, dynamic> data;

  String _summary(String key, String label) {
    final item = data[key];
    if (item is! Map) return '$label 확인 불가';
    final pages = item['pages'] ?? 0;
    final ocr = item['ocr_pages'];
    final ocrCount = ocr is List ? ocr.length : 0;
    return '$label $pages쪽${ocrCount > 0 ? ' · OCR $ocrCount쪽' : ''}';
  }

  @override
  Widget build(BuildContext context) {
    return Container(
      width: double.infinity,
      padding: const EdgeInsets.all(15),
      decoration: BoxDecoration(
        color: AppColors.softBlue,
        borderRadius: BorderRadius.circular(16),
      ),
      child: Row(
        children: [
          const Icon(Icons.description_outlined, color: AppColors.primary),
          const SizedBox(width: 10),
          Expanded(
            child: Text(
              '${_summary('registry', '등기부')}\n${_summary('building', '건축물대장')}',
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

class _RiskItemCard extends StatelessWidget {
  const _RiskItemCard({
    required this.title,
    required this.score,
    required this.explanation,
    required this.onTap,
  });

  final String title;
  final int score;
  final String explanation;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    final color = RiskResultPage.getRiskColor(score);
    return Padding(
      padding: const EdgeInsets.only(bottom: 10),
      child: Material(
        color: AppColors.surface,
        borderRadius: BorderRadius.circular(17),
        child: InkWell(
          borderRadius: BorderRadius.circular(17),
          onTap: onTap,
          child: Container(
            padding: const EdgeInsets.all(16),
            decoration: BoxDecoration(
              border: Border.all(color: AppColors.border),
              borderRadius: BorderRadius.circular(17),
            ),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Row(
                  children: [
                    Expanded(
                      child: Text(
                        title,
                        style: const TextStyle(
                          fontSize: 15,
                          fontWeight: FontWeight.w800,
                        ),
                      ),
                    ),
                    Text(
                      '$score점',
                      style: TextStyle(
                        color: color,
                        fontWeight: FontWeight.w800,
                      ),
                    ),
                    const SizedBox(width: 4),
                    const Icon(
                      Icons.chevron_right_rounded,
                      color: AppColors.muted,
                    ),
                  ],
                ),
                const SizedBox(height: 10),
                ClipRRect(
                  borderRadius: BorderRadius.circular(5),
                  child: LinearProgressIndicator(
                    value: (score / 100).clamp(0.0, 1.0).toDouble(),
                    minHeight: 7,
                    backgroundColor: color.withValues(alpha: 0.14),
                    valueColor: AlwaysStoppedAnimation<Color>(color),
                  ),
                ),
                const SizedBox(height: 10),
                Text(
                  explanation,
                  maxLines: 2,
                  overflow: TextOverflow.ellipsis,
                  style: const TextStyle(
                    color: AppColors.muted,
                    fontSize: 12.5,
                    height: 1.4,
                  ),
                ),
              ],
            ),
          ),
        ),
      ),
    );
  }
}

class _EmptyAnalysis extends StatelessWidget {
  const _EmptyAnalysis();

  @override
  Widget build(BuildContext context) {
    return Container(
      width: double.infinity,
      padding: const EdgeInsets.all(20),
      decoration: BoxDecoration(
        color: AppColors.surface,
        border: Border.all(color: AppColors.border),
        borderRadius: BorderRadius.circular(16),
      ),
      child: const Text(
        '표시할 세부 분석 항목이 없습니다.',
        textAlign: TextAlign.center,
        style: TextStyle(color: AppColors.muted),
      ),
    );
  }
}
