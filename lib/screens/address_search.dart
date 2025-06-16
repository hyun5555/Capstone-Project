import 'dart:convert';
import 'package:flutter/material.dart';
import 'package:flutter_inappwebview/flutter_inappwebview.dart';

class AddressSearchPage extends StatefulWidget {
  const AddressSearchPage({super.key});

  @override
  State<AddressSearchPage> createState() => _AddressSearchPageState();
}

class _AddressSearchPageState extends State<AddressSearchPage> {
  final InAppLocalhostServer _localhostServer = InAppLocalhostServer();

  @override
  void initState() {
    super.initState();
    startServerAndLoad();
  }

  Future<void> startServerAndLoad() async {
    await _localhostServer.start();
    setState(() {});
  }

  @override
  void dispose() {
    _localhostServer.close();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text("주소 검색")),
      body: _localhostServer.isRunning()
          ? InAppWebView(
        initialUrlRequest: URLRequest(
            url: WebUri("http://localhost:8080/assets/html/postcode.html")),
        onWebViewCreated: (controller) {
          controller.addJavaScriptHandler(
            handlerName: 'onComplete',
            callback: (args) {
              final raw = jsonDecode(args.first);
              final fullAddress = raw['fullAddress'];
              final bcode = raw['bcode'];

              // 본번, 부번 추출
              String mainNo = '0';
              String subNo = '0';
              final lastPart = fullAddress.split(' ').last;
              final numberParts = lastPart.split('-');
              mainNo = numberParts[0].replaceAll(RegExp(r'[^0-9]'), '');
              if (numberParts.length > 1) {
                subNo = numberParts[1].replaceAll(RegExp(r'[^0-9]'), '');
              }

              // 도로명 추출
              final addressParts = fullAddress.split(' ');
              String roadName = '';
              if (addressParts.length >= 4) {
                roadName = '${addressParts[2]} ${addressParts[3]}';
              } else if (addressParts.length >= 3) {
                roadName = addressParts[2];
              }

              final result = {
                'fullAddress': fullAddress,
                'roadName': roadName,
                'bcode': bcode,
                'mainAddressNo': mainNo,
                'subAddressNo': subNo
              };

              Navigator.pop(context, result);
            },
          );
        },
      )
          : const Center(child: CircularProgressIndicator()),
    );
  }
}
