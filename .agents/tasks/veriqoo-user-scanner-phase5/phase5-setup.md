# Phase 5 Setup Record — user_app Scanner Dependencies & Native Config

Scope: dependency + native config only. No scanner UI implemented in this step.
Write scope limited to `apps/user_app`. `packages/shared_core` was not modified.

## Dependency added

- `camera: ^0.12.1` added to `apps/user_app/pubspec.yaml` via `dart pub add camera`.
- Resolved transitive camera platform packages: `camera_android_camerax 0.7.5+1`,
  `camera_avfoundation 0.10.3+1`, `camera_web 0.3.5+6`, `camera_platform_interface 2.14.0`,
  `stream_transform 2.1.2`.
- `image_picker ^1.2.2` and `google_mlkit_text_recognition ^0.16.0` left unchanged
  (gallery fallback + OCR remain in place).

## Native config edits

### Android — `apps/user_app/android/app/src/main/AndroidManifest.xml`
- Added `<uses-permission android:name="android.permission.CAMERA"/>` (with comment)
  alongside the existing biometric permission.

### Android — `apps/user_app/android/app/build.gradle.kts`
- No change. `minSdk = flutter.minSdkVersion` resolves dynamically to the Flutter SDK's
  default (>= 21 in the current SDK), which already satisfies the camera plugin's
  minSdk 21 requirement. No manual bump needed.

### iOS — `apps/user_app/ios/Runner/Info.plist`
- Added `NSCameraUsageDescription` with string:
  "VERIQOO needs camera access to scan product labels for compliance."

## Verification results

- `dart pub get`: SUCCESS — "Got dependencies!" (exit 0).
- `dart analyze`: SUCCESS — "No issues found!" (0 errors, exit 0).

No commit performed per instructions.
