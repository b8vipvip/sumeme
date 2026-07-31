# SuMeMe Android / Windows client

This directory contains the maintained Flutter source for the first-party SuMeMe
client. Generated Android and Windows platform projects are intentionally not
committed. `scripts/materialize-flutter-client.py` creates them from the Flutter
stable template, adds the reviewed application source and packages a pinned
LobeHub web build.

## Current 0.2 scope

- Android and Windows from one source tree;
- bundles the LobeHub `v2.2.11` desktop and authentication SPAs in the APK/EXE;
- starts a loopback-only HTTP server on `127.0.0.1` for those static assets;
- proxies LobeHub API, authentication and data requests to `https://sumeme.mv3.cn`;
- no longer depends on production `/_spa` or `/_spa-auth` files to draw the UI;
- includes the read-only SuMeMe service control panel;
- offers native toolbar shortcuts for LobeHub, the control panel, the direct
  online page and reload;
- embeds no gateway token, service token, relay key or user secret;
- Windows uses the installed Microsoft Edge WebView2 Runtime.

The bundled interface is not an offline AI application. Conversations, login,
memory, object storage and model calls still require the SuMeMe server. Native
local Vault storage, system share targets, offline indexing, hybrid synchronization
and background attachment upload remain separate follow-up milestones.

## Why the client runs a loopback server

LobeHub's production assets use absolute paths such as `/_spa/...` and
`/_spa-auth/...`. Serving the unchanged build from a random local loopback port
preserves those paths. The same local origin also lets the client proxy relative
API calls to the remote SuMeMe server without embedding credentials or modifying
thousands of generated JavaScript files.

The proxy rewrites remote redirects, cookies, Origin and Referer values only for
the loopback session. It listens on IPv4 loopback rather than all interfaces.

## Local generation

A release client requires a prepared LobeHub UI directory. Build it from the pinned
upstream source:

```bash
git clone --branch v2.2.11 --depth 1 https://github.com/lobehub/lobehub.git .generated/lobehub
cd .generated/lobehub
corepack enable
pnpm install --no-frozen-lockfile
pnpm run build:spa
pnpm run build:spa:auth
cd ../..
python scripts/prepare-client-web-ui.py \
  --desktop-dist .generated/lobehub/dist/desktop \
  --auth-dist .generated/lobehub/dist/auth \
  --output .generated/lobehub-ui \
  --upstream-ref v2.2.11
```

Then install a current Flutter stable SDK, Android tooling and Visual Studio 2022
with the Desktop development with C++ workload, and run:

```bash
python scripts/materialize-flutter-client.py \
  --output .generated/sumeme_app \
  --web-ui .generated/lobehub-ui
cd .generated/sumeme_app
flutter analyze
flutter test
```

Build Android:

```bash
flutter build apk --release
```

Build Windows from a Windows host:

```powershell
flutter build windows --release
```

## GitHub artifacts

`.github/workflows/build-clients.yml` builds the pinned web UI once and then builds
both targets from that same artifact. Successful runs publish:

- `sumeme-android-apk`: development-signed release APK and provenance;
- `sumeme-windows-x64`: installer EXE, portable ZIP and provenance;
- `sumeme-lobehub-web-ui`: short-retention intermediate static UI artifact.

Production distribution should replace the Android development signing key with a
protected release keystore and add platform update/signature verification.
