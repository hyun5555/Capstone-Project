import 'package:capstone_project/services/api_service.dart';
import 'package:capstone_project/theme/app_theme.dart';
import 'package:flutter/material.dart';

class Chat extends StatefulWidget {
  const Chat({super.key});

  @override
  State<Chat> createState() => _ChatPageState();
}

class _ChatPageState extends State<Chat> {
  final List<Map<String, dynamic>> chatList = [
    {
      'message':
          '안녕하세요. 지금 전세계약의 어느 단계에 계신가요?\n계약 전, 계약 중, 계약 후 중 하나를 선택해 주세요.',
      'isUser': false,
    },
  ];
  final TextEditingController _controller = TextEditingController();
  final ScrollController _scrollController = ScrollController();
  bool _isSending = false;
  String? selectedCategory;

  final Map<String, List<String>> queryMap = {
    '계약 전': [
      '등기부등본에서 무엇을 확인해야 하나요?',
      '임대인과 소유자가 같은지 어떻게 확인하나요?',
      '전세보증보험 가입 가능 여부는 언제 확인하나요?',
      '안전한 공인중개사무소인지 확인하는 방법을 알려주세요.',
    ],
    '계약 중': [
      '계약서에서 반드시 확인할 항목을 알려주세요.',
      '전세사기 예방 특약에는 무엇을 넣어야 하나요?',
      '계약금을 누구 계좌로 보내야 하나요?',
      '잔금 전에 등기부를 다시 확인해야 하나요?',
    ],
    '계약 후': [
      '전입신고와 확정일자는 언제 받아야 하나요?',
      '임대차계약 신고 방법을 알려주세요.',
      '전세보증금 반환보증 가입 절차를 알려주세요.',
      '보증금을 돌려받지 못할 때 무엇부터 해야 하나요?',
    ],
  };

  @override
  void dispose() {
    _controller.dispose();
    _scrollController.dispose();
    super.dispose();
  }

  Future<void> _sendMessage(String text) async {
    final question = text.trim();
    if (question.isEmpty || _isSending) return;

    setState(() {
      _isSending = true;
      chatList.insert(0, {'message': question, 'isUser': true});
    });
    _controller.clear();
    _scrollToBottom();

    final response = await ApiService.fetchChatbotAnswer(
      question,
      stage: selectedCategory,
    );
    if (!mounted) return;
    setState(() {
      chatList.insert(0, {
        'message': response['answer'],
        'sources': response['sources'],
        'mode': response['mode'],
        'isUser': false,
      });
      _isSending = false;
    });
    _scrollToBottom();
  }

  void _scrollToBottom() {
    Future<void>.delayed(const Duration(milliseconds: 100), () {
      if (_scrollController.hasClients) {
        _scrollController.animateTo(
          0,
          duration: const Duration(milliseconds: 250),
          curve: Curves.easeOut,
        );
      }
    });
  }

  @override
  Widget build(BuildContext context) {
    final subKeywords =
        selectedCategory == null
            ? const <String>[]
            : queryMap[selectedCategory!] ?? const <String>[];

    return Scaffold(
      appBar: AppBar(
        title: const Text('전세 안심 상담'),
        leading: IconButton(
          tooltip: '뒤로 가기',
          icon: const Icon(Icons.arrow_back_ios_new_rounded, size: 20),
          onPressed: () => Navigator.pop(context),
        ),
      ),
      body: SafeArea(
        top: false,
        child: GestureDetector(
          onTap: () => FocusScope.of(context).unfocus(),
          child: Column(
            children: [
              const _ChatNotice(),
              Expanded(
                child: ListView.separated(
                  controller: _scrollController,
                  reverse: true,
                  padding: const EdgeInsets.fromLTRB(16, 10, 16, 16),
                  itemCount: chatList.length + (_isSending ? 1 : 0),
                  separatorBuilder: (_, __) => const SizedBox(height: 14),
                  itemBuilder: (context, index) {
                    if (_isSending && index == 0) return const _TypingBubble();
                    final chatIndex = index - (_isSending ? 1 : 0);
                    return _ChatBubble(chat: chatList[chatIndex]);
                  },
                ),
              ),
              _QuestionPicker(
                categories: queryMap.keys.toList(),
                keywords: subKeywords,
                selectedCategory: selectedCategory,
                enabled: !_isSending,
                onCategorySelected: (category) {
                  setState(() => selectedCategory = category);
                  _sendMessage('$category 단계에서 확인해야 할 사항을 순서대로 알려주세요.');
                },
                onQuestionSelected: _sendMessage,
              ),
              _MessageComposer(
                controller: _controller,
                isSending: _isSending,
                onSend: () => _sendMessage(_controller.text),
              ),
            ],
          ),
        ),
      ),
    );
  }
}

class _ChatNotice extends StatelessWidget {
  const _ChatNotice();

  @override
  Widget build(BuildContext context) {
    return Container(
      margin: const EdgeInsets.fromLTRB(16, 8, 16, 4),
      padding: const EdgeInsets.all(14),
      decoration: BoxDecoration(
        color: AppColors.softBlue,
        borderRadius: BorderRadius.circular(16),
      ),
      child: const Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Icon(
            Icons.verified_user_outlined,
            color: AppColors.primary,
            size: 21,
          ),
          SizedBox(width: 10),
          Expanded(
            child: Text(
              '공식 자료를 찾아 답변하고 출처를 함께 보여드려요.\n중요한 계약 판단은 전문가와 한 번 더 확인해 주세요.',
              style: TextStyle(
                fontSize: 12.5,
                color: AppColors.muted,
                height: 1.45,
              ),
            ),
          ),
        ],
      ),
    );
  }
}

class _ChatBubble extends StatelessWidget {
  const _ChatBubble({required this.chat});

  final Map<String, dynamic> chat;

  @override
  Widget build(BuildContext context) {
    final isUser = chat['isUser'] as bool;
    final sources =
        chat['sources'] is List ? chat['sources'] as List : const [];
    final mode = chat['mode'];

    return Row(
      mainAxisAlignment:
          isUser ? MainAxisAlignment.end : MainAxisAlignment.start,
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        if (!isUser) ...[
          Container(
            width: 34,
            height: 34,
            padding: const EdgeInsets.all(5),
            decoration: const BoxDecoration(
              color: AppColors.softBlue,
              shape: BoxShape.circle,
            ),
            child: const Icon(
              Icons.support_agent_rounded,
              color: AppColors.primary,
              size: 22,
            ),
          ),
          const SizedBox(width: 9),
        ],
        Flexible(
          child: Container(
            constraints: const BoxConstraints(maxWidth: 330),
            padding: const EdgeInsets.all(14),
            decoration: BoxDecoration(
              color: isUser ? AppColors.primary : AppColors.surface,
              border: isUser ? null : Border.all(color: AppColors.border),
              borderRadius: BorderRadius.only(
                topLeft: const Radius.circular(18),
                topRight: const Radius.circular(18),
                bottomLeft: Radius.circular(isUser ? 18 : 5),
                bottomRight: Radius.circular(isUser ? 5 : 18),
              ),
              boxShadow:
                  isUser
                      ? null
                      : const [
                        BoxShadow(
                          color: Color(0x0A000000),
                          blurRadius: 12,
                          offset: Offset(0, 4),
                        ),
                      ],
            ),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  chat['message'].toString(),
                  style: TextStyle(
                    color: isUser ? Colors.white : AppColors.text,
                    fontSize: 15,
                    height: 1.55,
                  ),
                ),
                if (!isUser && mode != null) ...[
                  const SizedBox(height: 10),
                  Container(
                    padding: const EdgeInsets.symmetric(
                      horizontal: 9,
                      vertical: 5,
                    ),
                    decoration: BoxDecoration(
                      color:
                          mode == 'rag'
                              ? const Color(0xFFEAF8F1)
                              : AppColors.softBlue,
                      borderRadius: BorderRadius.circular(20),
                    ),
                    child: Text(
                      mode == 'rag' ? '공식 자료 기반 RAG' : '근거 검색 불가',
                      style: const TextStyle(
                        fontSize: 11,
                        fontWeight: FontWeight.w700,
                        color: AppColors.primary,
                      ),
                    ),
                  ),
                ],
                if (!isUser && sources.isNotEmpty) ...[
                  const Padding(
                    padding: EdgeInsets.only(top: 14, bottom: 4),
                    child: Text(
                      '참고한 공식 자료',
                      style: TextStyle(
                        fontSize: 12,
                        fontWeight: FontWeight.w700,
                      ),
                    ),
                  ),
                  ...sources.map((source) => _SourceItem(source: source)),
                ],
              ],
            ),
          ),
        ),
      ],
    );
  }
}

class _SourceItem extends StatelessWidget {
  const _SourceItem({required this.source});

  final dynamic source;

  @override
  Widget build(BuildContext context) {
    final title = source['title']?.toString() ?? '공식 자료';
    final host = Uri.tryParse(source['url']?.toString() ?? '')?.host ?? '';
    return Container(
      margin: const EdgeInsets.only(top: 6),
      padding: const EdgeInsets.all(10),
      decoration: BoxDecoration(
        color: AppColors.background,
        borderRadius: BorderRadius.circular(12),
      ),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const Icon(
            Icons.description_outlined,
            size: 17,
            color: AppColors.accent,
          ),
          const SizedBox(width: 8),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  title,
                  maxLines: 2,
                  overflow: TextOverflow.ellipsis,
                  style: const TextStyle(
                    fontSize: 12,
                    fontWeight: FontWeight.w600,
                  ),
                ),
                if (host.isNotEmpty)
                  Text(
                    host,
                    style: const TextStyle(
                      fontSize: 10.5,
                      color: AppColors.muted,
                    ),
                  ),
              ],
            ),
          ),
        ],
      ),
    );
  }
}

class _TypingBubble extends StatelessWidget {
  const _TypingBubble();

  @override
  Widget build(BuildContext context) {
    return const Align(
      alignment: Alignment.centerLeft,
      child: Padding(
        padding: EdgeInsets.only(left: 43),
        child: SizedBox(
          width: 22,
          height: 22,
          child: CircularProgressIndicator(strokeWidth: 2.2),
        ),
      ),
    );
  }
}

class _QuestionPicker extends StatelessWidget {
  const _QuestionPicker({
    required this.categories,
    required this.keywords,
    required this.selectedCategory,
    required this.enabled,
    required this.onCategorySelected,
    required this.onQuestionSelected,
  });

  final List<String> categories;
  final List<String> keywords;
  final String? selectedCategory;
  final bool enabled;
  final ValueChanged<String> onCategorySelected;
  final ValueChanged<String> onQuestionSelected;

  @override
  Widget build(BuildContext context) {
    return Container(
      width: double.infinity,
      color: AppColors.surface,
      padding: const EdgeInsets.fromLTRB(12, 10, 12, 6),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const Padding(
            padding: EdgeInsets.only(left: 4, bottom: 7),
            child: Text(
              '계약 단계',
              style: TextStyle(fontSize: 12, color: AppColors.muted),
            ),
          ),
          SingleChildScrollView(
            scrollDirection: Axis.horizontal,
            child: Row(
              children:
                  categories.map((category) {
                    final isSelected = selectedCategory == category;
                    return Padding(
                      padding: const EdgeInsets.only(right: 7),
                      child: ChoiceChip(
                        label: Text(category),
                        selected: isSelected,
                        onSelected:
                            enabled
                                ? (_) => onCategorySelected(category)
                                : null,
                        showCheckmark: false,
                        backgroundColor: AppColors.surface,
                        selectedColor: AppColors.softBlue,
                        side: BorderSide(
                          color:
                              isSelected ? AppColors.accent : AppColors.border,
                        ),
                        labelStyle: TextStyle(
                          color:
                              isSelected ? AppColors.primary : AppColors.muted,
                          fontSize: 12,
                          fontWeight: FontWeight.w600,
                        ),
                      ),
                    );
                  }).toList(),
            ),
          ),
          if (keywords.isNotEmpty) ...[
            const SizedBox(height: 6),
            SizedBox(
              height: 35,
              child: ListView.separated(
                scrollDirection: Axis.horizontal,
                itemCount: keywords.length,
                separatorBuilder: (_, __) => const SizedBox(width: 7),
                itemBuilder: (context, index) {
                  return ActionChip(
                    label: Text(keywords[index]),
                    onPressed:
                        enabled
                            ? () => onQuestionSelected(keywords[index])
                            : null,
                    backgroundColor: AppColors.background,
                    side: BorderSide.none,
                    labelStyle: const TextStyle(
                      fontSize: 12,
                      color: AppColors.text,
                    ),
                  );
                },
              ),
            ),
          ],
        ],
      ),
    );
  }
}

class _MessageComposer extends StatelessWidget {
  const _MessageComposer({
    required this.controller,
    required this.isSending,
    required this.onSend,
  });

  final TextEditingController controller;
  final bool isSending;
  final VoidCallback onSend;

  @override
  Widget build(BuildContext context) {
    return Container(
      color: AppColors.surface,
      padding: const EdgeInsets.fromLTRB(12, 5, 12, 10),
      child: Row(
        children: [
          Expanded(
            child: TextField(
              controller: controller,
              enabled: !isSending,
              textInputAction: TextInputAction.send,
              minLines: 1,
              maxLines: 4,
              onSubmitted: (_) => onSend(),
              decoration: const InputDecoration(
                hintText: '궁금한 내용을 입력하세요',
                border: OutlineInputBorder(
                  borderRadius: BorderRadius.all(Radius.circular(22)),
                  borderSide: BorderSide(color: AppColors.border),
                ),
                enabledBorder: OutlineInputBorder(
                  borderRadius: BorderRadius.all(Radius.circular(22)),
                  borderSide: BorderSide(color: AppColors.border),
                ),
                focusedBorder: OutlineInputBorder(
                  borderRadius: BorderRadius.all(Radius.circular(22)),
                  borderSide: BorderSide(color: AppColors.primary),
                ),
                contentPadding: EdgeInsets.symmetric(
                  horizontal: 16,
                  vertical: 11,
                ),
              ),
            ),
          ),
          const SizedBox(width: 8),
          IconButton.filled(
            tooltip: '메시지 보내기',
            onPressed: isSending ? null : onSend,
            style: IconButton.styleFrom(
              backgroundColor: AppColors.primary,
              foregroundColor: Colors.white,
              disabledBackgroundColor: AppColors.border,
            ),
            icon: const Icon(Icons.arrow_upward_rounded),
          ),
        ],
      ),
    );
  }
}
