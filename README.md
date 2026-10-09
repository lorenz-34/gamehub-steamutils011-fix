# GameHub SteamUtils011 fix for macOS

[![100% Free & Open Source](https://img.shields.io/badge/100%25-Free%20%26%20Open%20Source-brightgreen)](https://github.com/lorenz-34/gamehub-steamutils011-fix)
[![No CrossOver Required](https://img.shields.io/badge/No%20CrossOver-Required-blue)](https://github.com/lorenz-34/gamehub-steamutils011-fix)
[![Steam Community Guide](https://img.shields.io/badge/Steam%20Guide-Order%20of%20the%20Sinking%20Star-171a21?logo=steam)](https://steamcommunity.com/sharedfiles/filedetails/?id=3816274709)

A 100% free, reversible workaround to play **Order of the Sinking Star** on macOS via **GameHub for Mac** (Apple Silicon) — **without paying for a CrossOver subscription ($74/yr) or Parallels**.

Fixes the common out-of-the-box launch crash:

```text
Steam initialization failed: VersionMismatch No SteamUtils011
Exiting the game because: Failed to initialize Steam.
```

> 📖 **Steam Community Guide**: For a visual walkthrough, step-by-step instructions, and recommended GameHub / D3DMetal settings, see the [Steam Community Guide](https://steamcommunity.com/sharedfiles/filedetails/?id=3816274709).

**Verified working on an Apple M1 MacBook Air.** The full game launched, ran for approximately 38 minutes, saved progress and shut down normally after this component replacement. This is one tested configuration, not a guarantee for every game or Mac.

## What was wrong?

The game requested a newer local Steam API interface, `SteamUtils011`. The Steam client bundled with the tested GameHub version exposed `SteamUtils010` but lacked `SteamUtils011`. Switching GameHub's Wine/Proton versions did not replace this separate Steam component.

The fix replaces three Windows Steam client DLLs **inside one game's container**, using a matching set downloaded from Valve:

- `steamclient64.dll`
- `tier0_s64.dll`
- `vstdlib_s64.dll`

GameHub's shared files remain intact. Normal Steam authentication is retained. This does not bypass ownership checks, modify the game executable, or upgrade Proton.

## Scope

- **Supported target:** GameHub for macOS, with the exact missing-interface error above.
- **Linux / Steam Deck:** unsupported and untested. Standard Steam/Proton installations have a different runtime layout and integration. Do not copy this procedure into a Linux Proton prefix.
- Graphics failures, missing DirectX features, and other Steam errors need separate diagnosis.
- The tool is unofficial and is not affiliated with Valve, GameSir, or Thekla.

## Other games and limits

This workaround may help other **64-bit Windows games in GameHub for macOS** when their logs specifically report `No SteamUtils011` and the container's Steam client lacks that interface. It supplies a newer matching client component set; it is not tied to one game executable. Successful Steam initialization does not guarantee graphics, anti-cheat, launcher or gameplay compatibility.

**Grim Dawn** has a [documented report of the exact error](https://steamcommunity.com/app/219990/discussions/0/583929583674547618/). Its developer advises using an up-to-date Steam client and offers a separate compatibility launch option for older Windows/Linux setups. This supports the diagnosis of an outdated Steam interface, but **this script has not been tested with Grim Dawn on GameHub**.

A generic “Failed to initialize Steam” message alone is not enough. For example, [Half-Life 2's GameHub dependency-manifest failure](https://github.com/gamesir-labs/gamehub-for-mac/issues/17) and [Spider-Man 2's GameHub launch-option lookup failure](https://github.com/gamesir-labs/gamehub-for-mac/issues/18) have different causes; this DLL replacement does not address them. Linux/Steam Deck, Android launchers and GeForce NOW are outside this tool's scope.

## Folder locations and portability

The default Steam directory is:

```text
~/Library/Application Support/com.gamemac.www/wine-engine/containers/virtual_containers/<ID>/drive_c/Program Files (x86)/Steam
```

`~` is the current user's home directory, resolved automatically by Python. No maintainer username or fixed home directory is embedded in the tool. `<ID>` is assigned locally by GameHub and **will differ between users and games**. The game library's download location is separate from this Wine container directory.

This is the observed layout for the tested GameHub version, corroborated by the GameHub issue reports linked above; it is not a guarantee for every past or future release. The tool checks that all three DLLs exist before modifying anything. Installing GameHub alone does not guarantee that a game's container has already been created. Open the game's C drive in GameHub to identify it.

If you have relocated the container root, specify that actual directory on **every command**, for example:

```sh
python3 fix.py status --containers-root "/Volumes/Games/virtual_containers"
python3 fix.py apply --containers-root "/Volumes/Games/virtual_containers" --container 2
```

Use your actual path and ID. The root must retain the expected `<ID>/drive_c/Program Files (x86)/Steam` layout. Custom roots have separate backup namespaces. Do not point this at a native macOS Steam installation or an unrelated Wine prefix.

Matching paths make the installer portable; they do not prove that a game will work on every Mac. End-to-end gameplay is verified on Apple Silicon in the configuration below; Intel Macs and other GameHub builds have not been verified.

## Requirements

- **100% Free**: No CrossOver subscription ($74/yr), Parallels license, or paid software required.
- Python 3.9 or later ([official Python downloads](https://www.python.org/downloads/macos/)), GameHub for macOS, and a legitimate Steam installation of the game.
- No third-party Python packages or administrator privileges required. Never run this with `sudo`.

Download this repository with GitHub's **Code → Download ZIP**, unzip it, and open Terminal in the extracted folder.

### 1. Inspect (read-only)

```sh
python3 fix.py
```

This lists GameHub container IDs and whether their Steam client contains `SteamUtils011`. Identify the correct game's container using **GameHub → game settings → Container → Open C Drive**: its Finder path contains `virtual_containers/<ID>/drive_c`.

For example, if that ID is `16`:

```sh
python3 fix.py status --container 16
```

**Use your own container ID.** The script deliberately does not guess which game to modify. If the interface is already present, this workaround is probably not the fix you need.

### 2. Apply

Quit GameHub and all Wine games/processes first. Then:

```sh
python3 fix.py apply --container 16
```

The tool downloads the pinned, tested package directly from Valve, checks its SHA-256 and size, backs up the original DLLs and symlink destinations, then replaces only the selected container's three directory entries. It never writes through the original DLL symlinks. Start GameHub again and launch the game.

Backups are kept under:

```text
~/Library/Application Support/gamehub-steamutils011-fix/<ID>/
```

Keep this directory. It contains proprietary DLL backups and local paths; **do not upload it to GitHub**.

### Undo or reapply

With GameHub and Wine closed:

```sh
python3 fix.py restore --container 16
python3 fix.py reapply --container 16
```

Run only the action you want. Restore reinstates original links/files; reapply uses the saved replacement set without downloading again. Both refuse unknown/newer files rather than overwriting a vendor update. If the shared original files changed, restore refuses to reinstate stale symlinks.

GameHub repair/update operations may reset these files. Only reapply if the same missing-interface error returns. Prefer a future official GameHub fix when available. If an operation is interrupted, keep the backup and use `status` before `restore` or `reapply`. Backups are created before modifications; handled replacement failures attempt rollback, but power loss or disk failure can still require recovery.

## Tested configuration

| Component | Verified setup |
|---|---|
| Date | 9 October 2026 |
| Hardware | Apple M1 MacBook Air, 8 GB RAM |
| macOS | 27.0 |
| GameHub | 0.8.613 |
| Game | Order of the Sinking Star, Steam app 499170 |
| Branch / build | main / 25805446 |
| Wine layer | wine-proton_11.0 |
| Graphics | gptk-4.0-2 / D3DMetal |
| Sync | MSync |
| In-game preset | Very Performance |

The successful game log reported `[Steam] Succesfully initialized.` (spelling as logged), successful saves and normal shutdown. A separate earlier session passed Steam initialization but failed a graphics feature check. The DLL fix addresses Steam initialization; it should not be credited with fixing that separate graphics problem.

The prototype replacement was tested in the real game. The reusable installer is additionally tested in temporary simulated containers; it has not been reapplied to the already-working game installation.

### Additional maintainer-reported tests

After applying the Steam component fix, the maintainer reports the game working with **all Wine layers and graphics stacks they tested**, including **wine-proton_10.0** and older **GPTK 3.x** versions as well as the newer configuration above. This does not mean every available layer/stack or every combination was tested; exact older GPTK patch versions and a complete combination matrix were not recorded.

The maintainer reports a substantial performance improvement with the newer tested versions. This is a qualitative observation on their Mac, not a controlled benchmark or a promised speed increase on other systems. The workaround itself updates the Steam client interface; Wine and graphics settings remain separate performance choices.

## Download provenance

No Valve or game binaries are included in this repository.

- [Official Valve win64 manifest](https://client-update.akamai.steamstatic.com/steam_client_win64), retrieved version `1788652215`.
- [Pinned official package](https://client-update.akamai.steamstatic.com/bins_win64.zip.36f5d9202e79ab2aa3e3c5902e84bbd799d31fc0).
- Size: `63700191` bytes.
- SHA-256: `93f5b6bea0267fd85dc8cc823fdab5c5fb55d7f3a1deab0598acefef0e133bce`.

Pinning makes the workaround reproducible. This is not an updater for future Steam releases. If Valve removes this package, the download will fail safely; please report it rather than substituting arbitrary DLL download sites.

References: [Valve Steam API initialization](https://partner.steamgames.com/doc/sdk/api), [ISteamUtils](https://partner.steamgames.com/doc/api/ISteamUtils), [GameHub for Mac issue tracker](https://github.com/gamesir-labs/gamehub-for-mac).

## Development and reports

```sh
python3 -m unittest -v
```

Tests use temporary files, fake DLL bytes and mocked downloads. They cover symlink isolation, restoration, reapplication, integrity failures, rollback and refusal to overwrite changed components. They do not launch Steam or the game.

For an issue, include GameHub/macOS versions, Mac chip, game build, exact error and whether `SteamUtils011` is present. Redact account IDs and personal paths. Do not upload DLLs, full private logs, Steam session data or credentials.

## License

Original code and documentation: MIT, copyright 2026 thereliant. Valve's downloaded components remain Valve's property and are not covered by this license. See [LICENSE](LICENSE).
