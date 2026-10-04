# Environment limitations (foundation pass)

Checked on 2026-10-05:

- Python 3.12 and Node.js are available.
- Godot 4 / `godot-headless` is not installed or available on `PATH`.
- No Windows host or Android device is exposed to this workspace.
- No network service, paid LLM/image API, key, or account is required by the
  foundation.
- The default managed sandbox rejects Python TCP socket creation. A separately
  approved localhost run of the LAN smoke test passed; no real Wi-Fi,
  Windows-firewall, router-discovery, or multi-device run was performed.

Therefore this pass can truthfully report:

- Godot project files generated and statically reviewed.
- Browser/Canvas preview runnable through a local Python HTTP server.
- Headless catalogue and core contract tests passing.

It must not report Godot startup, Windows build, Android APK, touch-device,
Godot-ENet, or desktop multi-device interaction as completed until those are
performed on the target machines.
