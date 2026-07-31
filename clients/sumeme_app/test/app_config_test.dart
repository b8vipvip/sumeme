import 'package:flutter_test/flutter_test.dart';
import 'package:sumeme_app/main.dart';

void main() {
  test('production app URL uses HTTPS', () {
    final Uri uri = Uri.parse(defaultAppUrl);

    expect(uri.scheme, 'https');
    expect(uri.host, 'sumeme.mv3.cn');
    expect(uri.path, isEmpty);
  });
}
