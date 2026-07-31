import 'package:flutter_test/flutter_test.dart';
import 'package:sumeme_app/app_state.dart';

void main() {
  test('default SuMeMe server URL uses HTTPS', () {
    final Uri uri = Uri.parse(SuMeMeAppState.defaultServerUrl);

    expect(uri.scheme, 'https');
    expect(uri.host, 'sumeme.mv3.cn');
    expect(uri.path, isEmpty);
  });
}
