# SuMeMe Android / Windows client

This directory contains the maintained Flutter source for the first-party SuMeMe
client. Generated Android and Windows platform projects are intentionally not
committed. `scripts/materialize-flutter-client.py` creates them from the Flutter
stable template and overlays the reviewed application source.

## Current first-version scope

- Android and Windows from one source tree;
- loads the production SuMeMe web application at `https://sumeme.mv3.cn`;
- JavaScript and normal HTTPS navigation are enabled for LobeHub;
- Android back, home and reload controls;
- Windows home and reload controls;
- no gateway token, service token, relay key or user secret is embedded;
- Windows uses the installed Microsoft Edge WebView2 Runtime.

This is the first distributable client shell. Native local Vault storage, system
share targets, offline indexing, hybrid synchronization and background attachment
upload remain separate follow-up milestones.

## Local generation

Install a current Flutter stable SDK, Android tooling and Visual Studio 2022 with
the Desktop development with C++ workload. Then run:

```bash
python scripts/materialize-flutter-client.py --output .generated/sumeme_app
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

`.github/workflows/build-clients.yml` builds both targets. Successful runs publish:

- `sumeme-android-apk`: development-signed release APK and provenance;
- `sumeme-windows-x64`: installer EXE, portable ZIP and provenance.

Production distribution should replace the Android development signing key with a
protected release keystore and add platform update/signature verification.
