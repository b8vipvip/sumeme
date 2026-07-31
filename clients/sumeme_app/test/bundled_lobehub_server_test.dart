import 'dart:convert';
import 'dart:io';

import 'package:flutter_test/flutter_test.dart';
import 'package:sumeme_app/bundled_lobehub_server.dart';

void main() {
  late HttpServer upstream;
  late Uri upstreamOrigin;
  late BundledLobeHubServer proxy;
  late Uri proxyOrigin;
  String? receivedCookie;
  String? receivedOrigin;

  setUp(() async {
    upstream = await HttpServer.bind(InternetAddress.loopbackIPv4, 0);
    upstreamOrigin = Uri.parse('http://127.0.0.1:${upstream.port}/');
    upstream.listen((HttpRequest request) async {
      switch (request.uri.path) {
        case '/api/session':
          request.response.cookies.add(
            Cookie('__Secure-session', 'abc123')
              ..httpOnly = true
              ..path = '/'
              ..sameSite = SameSite.none
              ..secure = true,
          );
          request.response.headers.contentType = ContentType.json;
          request.response.write(jsonEncode(<String, Object>{'ok': true}));
          await request.response.close();
        case '/api/check':
          receivedCookie = request.headers.value(HttpHeaders.cookieHeader);
          receivedOrigin = request.headers.value('origin');
          request.response.headers.contentType = ContentType.json;
          request.response.write(jsonEncode(<String, Object>{'ok': true}));
          await request.response.close();
        case '/api/redirect':
          request.response.statusCode = HttpStatus.found;
          request.response.headers.set(
            HttpHeaders.locationHeader,
            upstreamOrigin.resolve('signin').toString(),
          );
          await request.response.close();
        default:
          request.response.statusCode = HttpStatus.notFound;
          await request.response.close();
      }
    });

    proxy = BundledLobeHubServer(remoteOrigin: upstreamOrigin);
    proxyOrigin = await proxy.start();
  });

  tearDown(() async {
    await proxy.close();
    await upstream.close(force: true);
  });

  test('binds only to IPv4 loopback and exposes client metadata', () async {
    expect(proxyOrigin.host, '127.0.0.1');

    final HttpClient client = HttpClient();
    addTearDown(() => client.close(force: true));
    final HttpClientResponse response = await (await client.getUrl(
      proxyOrigin.resolve('__sumeme/client-info'),
    )).close();
    final String body = await utf8.decoder.bind(response).join();

    expect(response.statusCode, HttpStatus.ok);
    expect(jsonDecode(body), containsPair('mode', 'bundled-client'));
  });

  test('maps secure production cookies through the local HTTP origin', () async {
    final HttpClient client = HttpClient();
    addTearDown(() => client.close(force: true));

    final HttpClientResponse session = await (await client.getUrl(
      proxyOrigin.resolve('api/session'),
    )).close();
    await session.drain<void>();

    expect(session.statusCode, HttpStatus.ok);
    expect(session.cookies, hasLength(1));
    final Cookie localCookie = session.cookies.single;
    expect(localCookie.name, 'SuMeMeSecure-session');
    expect(localCookie.secure, isFalse);
    expect(localCookie.sameSite, SameSite.lax);

    final HttpClientRequest check = await client.getUrl(
      proxyOrigin.resolve('api/check'),
    );
    check.cookies.add(Cookie(localCookie.name, localCookie.value));
    check.headers.set('origin', proxyOrigin.origin);
    final HttpClientResponse checked = await check.close();
    await checked.drain<void>();

    expect(receivedCookie, contains('__Secure-session=abc123'));
    expect(receivedOrigin, upstreamOrigin.origin);
  });

  test('rewrites remote redirects back to the loopback origin', () async {
    final HttpClient client = HttpClient();
    addTearDown(() => client.close(force: true));
    final HttpClientRequest request = await client.getUrl(
      proxyOrigin.resolve('api/redirect'),
    );
    request.followRedirects = false;
    final HttpClientResponse response = await request.close();
    await response.drain<void>();

    expect(response.statusCode, HttpStatus.found);
    expect(
      response.headers.value(HttpHeaders.locationHeader),
      proxyOrigin.resolve('signin').toString(),
    );
  });
}
