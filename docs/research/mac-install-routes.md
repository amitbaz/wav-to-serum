# How a producer with no Python can install this on a Mac

Checked on 2026-11-01. This reports facts and unknowns for [#27](https://github.com/amitbaz/wav-to-serum/issues/27). It makes no decisions.

Versions: macOS 27.0.1 on arm64 with System Integrity Protection (SIP) off. Claude Desktop 4.4212.0, shipped bundle read but not run. ChatGPT desktop 26.1007.30912, signature and bundle listing only. Cursor and VS Code were not run. DawDreamer 0.9.0, Serum 2 from a June 2025 build, `mcp` 1.30.0 and 2.3.0, `@anthropic-ai/mcpb` 2.1.2.

## Evidence labels

| Label | Meaning |
| --- | --- |
| **Documented** | The owner's docs, spec, licence text or source says so. |
| **Observed** | I saw it in a test here, or in shipped code. |
| **Unknown** | No source settles it, and no test was run. |

Anything about what a licence means in law is marked **Legal interpretation**. It is not advice.

## The answer

Two routes can work with no terminal and no Python: a `.mcpb` file opened in Claude Desktop, and a signed, notarized Mac app. Neither has been proven end to end.

The `.mcpb` route rests on a feature Claude's own docs do not mention. Claude Desktop's shipped code has a `uv` runtime that downloads uv, Python and every dependency at install. A clean run of those same steps here rendered Serum 2. I did not install anything into Desktop, so the real install is untested.

The app route needs $99 a year and a Developer ID. It has one unsettled point: Apple documents the entitlement a host needs to load Serum 2, but this Mac has SIP off, so it could not show library validation working or failing.

Bundling changes the GPL position. A `uv` bundle holds no DawDreamer. An app or a self-contained bundle holds a copy, so source duties under section 6 apply to the maintainer.

Testing also turned the main-thread report into something exact. In these tests DawDreamer had to stay on one thread for the life of the process, and preset loading worked only on the main thread.

## Routes at a glance

| Route | The producer needs | Cost | Language model | GPL effect | State |
| --- | --- | --- | --- | --- | --- |
| `.mcpb`, `uv` type, in Claude Desktop | Claude Desktop, Serum 2, internet at install | Producer $0 on Free. Maintainer $0 | Claude account. Free is allowed | Bundle holds no DawDreamer | Steps pass outside Desktop. Real install untested |
| `.mcpb`, `binary` type, frozen server | Claude Desktop, Serum 2 | Same, plus about 67 MB or more per download | Claude account | Maintainer conveys DawDreamer | Frozen server rendered here. Bundle not installed |
| `.mcpb`, `python` type | The above plus a matching system Python | Same | Claude account | Maintainer conveys DawDreamer | Fails the aim: it needs Python installed |
| Claude plugin in the directory | Paid Claude plan, Serum 2, and uv unless a bundle supplies it | $20 a month or more | Claude account | Depends on what the plugin carries | Local servers skip Chat. Review needed |
| Signed, notarized Mac app | The app, Serum 2 | Maintainer $99 a year plus upkeep | Must be built in. See [below](#3-who-brings-the-language-model) | Maintainer conveys DawDreamer | Frozen build works. Notarization untested |
| Cursor or VS Code install link | An editor, a working `uv`, an AI plan | Varies | Editor's model | Depends on the command | Developer route |
| ChatGPT desktop | A hand-typed command, a working `uv` | ChatGPT plan | ChatGPT | Depends on the command | Directory closed to most. Developer route |
| LM Studio | A hand-edited `mcp.json` or a link, a working `uv` | No AI subscription | Local model | Depends on the command | Developer route |

## 1. How MCP reaches a non-technical user

### The MCPB format

| Question | Finding | Evidence |
| --- | --- | --- |
| Current spec? | The spec lists four server types: `node`, `python`, `binary` and `uv`. Its header still says version `0.3`, dated 2025-12-02, though it describes `uv` as v0.4+. The `latest` schema is also pinned to `0.3`. | Documented ([MANIFEST](https://github.com/modelcontextprotocol/mcpb/blob/main/MANIFEST.md)), Observed ([schemas](https://github.com/modelcontextprotocol/mcpb/tree/main/schemas)) |
| Is it maintained? | The last GitHub release is from December 2025. The last commit I saw is from April 2026. | Observed ([releases](https://github.com/modelcontextprotocol/mcpb/releases)) |
| Python with compiled dependencies, `python` type? | All dependencies must be bundled in `server/lib` or `server/venv`. DawDreamer's Mac wheels are built per Python minor version, so a bundle fits one Python version. | Documented ([MANIFEST](https://github.com/modelcontextprotocol/mcpb/blob/main/MANIFEST.md)), Observed |
| Does `python` need a bundled runtime? | Desktop ships no Python. Its code picks a system Python for this type. Docs say only Node is built in. | Observed (shipped code), Documented ([help page](https://support.claude.com/en/articles/10949351-getting-started-with-local-mcp-servers-on-claude-desktop)) |
| Compiled dependencies, `uv` type? | The host installs dependencies from `pyproject.toml`. The spec's benefits list says "Handles compiled dependencies" and "No user Python installation required". | Documented ([MANIFEST](https://github.com/modelcontextprotocol/mcpb/blob/main/MANIFEST.md)) |
| `binary` type? | Self-contained, with no runtime requirement. A frozen Python server fits here. | Documented ([MANIFEST](https://github.com/modelcontextprotocol/mcpb/blob/main/MANIFEST.md)) |
| Signing? | `mcpb sign` appends a PKCS#7 signature, and self-signed is allowed. Desktop installs unsigned bundles and refuses them only under an enterprise `signatureRequired` policy. It is unrelated to Apple signing. | Documented ([CLI](https://github.com/modelcontextprotocol/mcpb/blob/main/CLI.md)), Observed (shipped code) |
| Picking files? | `user_config` offers `file` and `directory` pickers. | Documented ([MANIFEST](https://github.com/modelcontextprotocol/mcpb/blob/main/MANIFEST.md)) |
| Which clients install it? | Claude Desktop, by double-click or drag. Claude Code, as a path or URL in a plugin. The MCP blog also names MCP for Windows. Docs for Cursor, VS Code, LM Studio and goose never mention it. OpenAI's portal "doesn't accept `.mcpb` files". | Documented ([build guide](https://claude.com/docs/connectors/building/mcpb), [plugin reference](https://code.claude.com/docs/en/plugins-reference), [MCP blog](https://blog.modelcontextprotocol.io/posts/2025-11-20-adopting-mcpb/), [OpenAI](https://developers.openai.com/plugins/guides/submit-claude-plugin)) |

### Claude Desktop's `uv` runtime

This is the only way I found for a local Python server with native dependencies to reach someone with no Python. Claude's [build guide](https://claude.com/docs/connectors/building/mcpb) does not mention it and says Node is "strongly recommended". The [help page](https://support.claude.com/en/articles/10949351-getting-started-with-local-mcp-servers-on-claude-desktop) lists Node, Python and binary only. The evidence is the spec, a [spec example](https://github.com/modelcontextprotocol/mcpb/tree/main/examples/hello-world-uv) and the shipped code.

From the shipped 4.4212.0 code (Observed):

- It downloads uv 0.9.7 from GitHub and checks a pinned SHA-256.
- It runs `uv sync --quiet` in the extension folder.
- It adds `--no-python-downloads` only if `isUvSystemPythonEnabled` is set, which defaults to false, so uv fetches Python.
- The install dialog says "we need to fetch a few dependencies. This may take a few minutes."
- I found no `uv`-specific gate on the install or launch path. One separate import flow does refuse `uv` extensions.

The same steps, run outside Desktop with that uv 0.9.7 and managed Python only (Observed):

| Measure | Result |
| --- | --- |
| Pinned uv checksum | Matches the value in Desktop's code |
| First install | 95 seconds, with cold caches |
| On disk | Environment 448 MB, Python 3.14 49 MB, uv cache 488 MB |
| `.mcpb` size | 103 KB including `uv.lock` |
| Render through an MCP stdio client | Worked, preset loaded, audio not silent |

Two traps showed up (Observed):

- `mcpb` 2.1.2 rejects a `uv` manifest with no `mcp_config`, although the spec calls it optional. The spec example includes one, and with it the bundle packs.
- Unpinned dependencies resolve at install. `mcp` resolved to 2.3.0, where `from mcp.server.fastmcp import FastMCP` raises an error. Desktop passes no `--locked` or `--frozen`.

### Claude's directory and plugins

| Question | Finding | Evidence |
| --- | --- | --- |
| Can a `.mcpb` be listed? | No. Listings are deprecated and "the directory no longer accepts MCPB submissions". Direct sharing still works: the user opens the file. The older help page still links a submission form, which conflicts. | Documented ([build guide](https://claude.com/docs/connectors/building/mcpb), [publish](https://claude.com/docs/directory/publish), [help page](https://support.claude.com/en/articles/10949351-getting-started-with-local-mcp-servers-on-claude-desktop)) |
| How can a local server be listed? | Inside a plugin, from a public GitHub repository, with automated checks and human review. Free accounts cannot submit. | Documented ([publish](https://claude.com/docs/directory/publish), [submit](https://claude.com/docs/plugins/submit)) |
| Where does a plugin's local server run? | Claude Code, and Cowork sessions on the user's computer. Chat ignores it. A local `.mcpb` extension installed directly is the separate path above. | Documented ([platform support](https://claude.com/docs/plugins/platform-support)) |
| Which plans? | The plugin directory shows on Pro and up. Claude Code and Cowork are paid only. Desktop extensions are on every plan, including Free. Pro is $20 a month. | Documented ([pricing](https://claude.com/pricing), [Cowork](https://support.claude.com/en/articles/13345190-get-started-with-claude-cowork)) |
| What fits review? | Compiled executables and `.mcpb` bundles are held for a reviewer. A pinned `uvx` or `uv run --locked` is also held, because its dependencies resolve at install. Limit: 200 MB per plugin. Top-level `bin/` cannot be installed in Cowork. | Documented ([checklist](https://claude.com/docs/plugins/pre-submission-checklist), [platform support](https://claude.com/docs/plugins/platform-support)) |
| Claude Code without a terminal? | The desktop app's Code tab runs it. A plugin server that calls `uvx` still needs uv on the machine. | Documented ([platform support](https://claude.com/docs/plugins/platform-support)), Unknown whether Cowork or Code supply uv |

### Other clients

| Client | Local server support | Install path | Evidence |
| --- | --- | --- | --- |
| Cursor | Yes, stdio. The command must be on the system path or given as a full path. | `cursor://` install link, or the reviewed Marketplace | Documented ([MCP](https://cursor.com/docs/mcp), [links](https://cursor.com/docs/mcp/install-links), [plugins](https://cursor.com/docs/plugins)) |
| VS Code | Yes, through Copilot's agent features. | `vscode:mcp/install` link, or the `@mcp` gallery in preview | Documented ([users](https://code.visualstudio.com/docs/agent-customization/mcp-servers), [authors](https://code.visualstudio.com/api/extension-guides/ai/mcp)) |
| ChatGPT desktop | Yes. Settings > MCP servers takes a STDIO command, shared with Codex. | Directory listing is "limited to approved partners". | Documented ([MCP](https://learn.chatgpt.com/docs/extend/mcp), [desktop-only](https://developers.openai.com/plugins/deploy/desktop-only)) |
| ChatGPT web | No local process. Remote HTTPS, or Secure MCP Tunnel, which needs a Platform org, an API key and a `tunnel-client`. | Not a consumer path | Documented ([tunnel](https://developers.openai.com/api/docs/guides/secure-mcp-tunnels)) |
| LM Studio | Yes, from 0.3.17, with local models. | `mcp.json`, or an `lmstudio://` link | Documented ([MCP](https://lmstudio.ai/docs/app/mcp), [link](https://lmstudio.ai/docs/app/mcp/deeplink)) |
| goose | Yes. | `goose://` link limited to set commands including `uvx` | Documented ([extensions](https://goose-docs.ai/docs/getting-started/using-extensions)) |

Every link above stores a command. None brings uv or Python, so a Python server needs uv, or a frozen binary at a known path, on the machine first.

### The official MCP Registry

It is a preview, with possible "breaking changes or data resets". It lists metadata for clients. It accepts PyPI packages and `.mcpb` files hosted on GitHub or GitLab releases, with a SHA-256 that clients check. It does not install anything by itself and is not a shop for end users (Documented: [README](https://github.com/modelcontextprotocol/registry), [package types](https://github.com/modelcontextprotocol/registry/blob/main/docs/modelcontextprotocol-io/package-types.mdx)). VS Code's gallery is one consumer route. Which registry it reads, and whether any Mac client installs `mcpb` entries from it, I did not establish (Unknown).

## 2. A small Mac app

### What it could be

| Option | Finding | Evidence |
| --- | --- | --- |
| PyInstaller | Freezes Python and dependencies, signs them, and turns on hardened runtime when given an identity. Takes an entitlements file. A `--onedir` build of the server took 14 seconds and rendered with a preset through MCP stdio. 172 MB, 67 MB zipped, with no librosa. | Documented ([notes](https://pyinstaller.org/en/stable/feature-notes.html), [usage](https://pyinstaller.org/en/stable/usage.html)), Observed |
| Briefcase | Builds, signs and packages Mac apps from Python. Not tried with DawDreamer. | Documented ([docs](https://briefcase.beeware.org/en/stable/how-to/code-signing/macOS/)) |
| py2app | Exists. Not tried. | Documented ([docs](https://py2app.readthedocs.io/en/latest/)) |
| Tauri | Native shell with a "sidecar" binary, and its docs name PyInstaller as a common source. Handles signing and notarization. | Documented ([sidecar](https://v2.tauri.app/develop/sidecar/), [signing](https://v2.tauri.app/distribute/sign/macos/)) |
| Swift shell | Same pattern: a native window with a helper process. Not tried. | Unknown |
| Full Python plus environment, zipped | 149 MB with librosa. | Observed |

### Signing, notarization and upkeep

| Item | Finding | Evidence |
| --- | --- | --- |
| Cost | $99 a year. A free account cannot notarize. | Documented ([Apple](https://developer.apple.com/programs/), [Tauri](https://v2.tauri.app/distribute/sign/macos/)) |
| Requirements | Developer ID signature, hardened runtime, secure timestamp. Notarization is an automated scan, not App Review. | Documented ([notarizing](https://developer.apple.com/documentation/security/notarizing-macos-software-before-distribution), [issues](https://developer.apple.com/documentation/security/resolving-common-notarization-issues)) |
| Wheel signatures | `dawdreamer.so` is ad hoc signed, so it must be re-signed. All 232 native libraries in Python and the environment re-signed cleanly with an Apple Development identity and still rendered. | Observed |
| Certificate expiry | Apps already released keep running. A new certificate is needed for updates. | Documented ([Developer ID](https://developer.apple.com/help/account/certificates/create-developer-id-certificates)) |
| Without notarization | Since macOS Sequoia, Control-click no longer bypasses Gatekeeper. The user must go to System Settings > Privacy & Security. | Documented ([Apple](https://developer.apple.com/news/?id=saqachfa)) |
| Mac App Store | Requires the sandbox and bars downloading code. Whether a sandboxed app can host Serum 2 was not tested. | Documented ([guidelines 2.4.5, 2.5.2](https://developer.apple.com/app-store/review/guidelines/)), Unknown |
| Ongoing work | Releases need signing and notarizing in CI, an update mechanism, and new builds for macOS, DawDreamer and Serum changes. No source measures the hours. | Unknown |

### Can a notarized hardened app load Serum 2?

Serum 2 is signed with Developer ID by Steve Duda, team `42K3SNWUP7` (Observed). An app from another team is therefore a foreign host.

- Hardened runtime enables library validation, which blocks code unless it is signed by Apple or by the same team. Apple says to use `com.apple.security.cs.disable-library-validation` "if your program loads plug-ins that are signed by other third-party developers", and warns that Gatekeeper runs extra checks on such apps (Documented: [entitlement](https://developer.apple.com/documentation/bundleresources/entitlements/com.apple.security.cs.disable-library-validation)).
- Apple's notarization guide discourages this only for "executables that don't host plug-ins" (Documented: [issues](https://developer.apple.com/documentation/security/resolving-common-notarization-issues)).
- A public precedent exists. Tracktion's [pluginval](https://github.com/Tracktion/pluginval/blob/develop/CMakeLists.txt) sets hardened runtime with that entitlement and `allow-unsigned-executable-memory`, and its [release workflow](https://github.com/Tracktion/pluginval/blob/develop/.github/workflows/build.yaml) notarizes with Developer ID (Documented).

Local test results (Observed), with a real team ID and hardened runtime:

| Entitlements | `import dawdreamer` | Serum 2 render |
| --- | --- | --- |
| None | Worked | Worked |
| Disable library validation | Worked | Worked |
| Plus `allow-jit` | Worked | Worked |
| Plus `allow-unsigned-executable-memory` | Worked | Worked |

**The first row proves nothing about a normal Mac.** SIP is off here. In the two cases where I read the flags, with and without the entitlement, the process had the runtime flag but no library-validation flag. So this test cannot show the block or that the entitlement lifts it. The render also needed no JIT entitlement here, but SIP off may relax that check too. A Mac with SIP on is needed.

### Threading, which shapes any app or server

The report that DawDreamer must stay on the main thread is partly true (Observed):

| Scenario | Result |
| --- | --- |
| Main thread only, repeated, with presets | Works |
| Worker thread only, default patch | Works |
| Worker thread only, `load_state` | Fails with `SystemError` from nanobind |
| Main thread, then a worker, or the reverse | Hangs. Killed after 25 seconds |
| `mcp` 1.30.0 tool, sync or async | Runs on main. Presets work |
| `mcp` 2.3.0 async tool | Runs on main. Presets work |
| `mcp` 2.3.0 sync tool | Runs on an AnyIO worker. Preset load fails |
| Frozen PyInstaller server, `mcp` 1.30.0 | Runs on main. Presets work |

A render with a preset took 0.13 to 0.16 seconds after a first call of about 0.27. An app's interface normally owns its main thread, so an in-process render would compete for it. A separate helper process has its own main thread, and that pattern worked here through stdio.

## 3. Who brings the language model

| Route | Model source | With none |
| --- | --- | --- |
| `.mcpb` in Desktop | The user's Claude account, signed in. Free is allowed but has limited usage. Whether Free's limits cover a design session is Unknown. | No Desktop, no route |
| Claude plugin | Paid Claude plan | No route |
| Editors, ChatGPT | Their own plan | No route |
| LM Studio, goose | A local or chosen model. Whether a local model can fill the designer role well is Unknown. | No subscription, but a model must be downloaded |
| Mac app, own API key | Anthropic or OpenAI key pasted by the user. Priced per use. | Unusable for designer work |
| Mac app, ChatGPT plan | Sign in with ChatGPT lets open-source and locally hosted apps use a Plus or Pro plan. It is a preview with limits. | Falls back to another source |
| Mac app, Claude plan | "Anthropic does not permit third-party developers to offer Claude.ai login into their own applications". See the note below. | Falls back to another source |
| Mac app, local or Apple model | A bundled or LM Studio model, or Apple's Foundation Models. Apple's model depends on device and region support. Fit for this work is Unknown. | Nothing to bring, if it works |

Sources: [Sign in with ChatGPT](https://learn.chatgpt.com/docs/sign-in-with-chatgpt), [plan usage](https://developers.openai.com/siwc/token-sharing-open-source), [preview limits](https://developers.openai.com/siwc/token-sharing-open-source/preview-limitations), [Claude Code legal](https://code.claude.com/docs/en/legal-and-compliance), [Agent SDK](https://code.claude.com/docs/en/agent-sdk/overview), [Foundation Models](https://developer.apple.com/documentation/foundationmodels). All Documented.

Three more facts:

- **Sampling is not a way out.** MCP sampling, where a server borrows the client's model, is deprecated as of `2026-07-28`: "New implementations SHOULD NOT adopt it" (Documented: [spec](https://modelcontextprotocol.io/specification/2026-07-28/client/sampling)).
- **Claude Code in a product.** The same legal page lets a product run unmodified Claude Code under the Commercial Terms if each user signs in with their own credentials, including a subscription. That sits beside the ban on offering Claude.ai login. How the two fit for a Mac app is Unknown.
- **ChatGPT plan limits.** The preview omits audio input and hosted tools. Function tools are supported (Documented: [limits](https://developers.openai.com/siwc/token-sharing-open-source/preview-limitations)).

### What is left with no model

The core runs with no language model, per the project brief. The [glossary](../../GLOSSARY.md) gives the designer choices, shaping and explanation, and gives the tuner knob values from numbers and a score. With no model, the tuner can still run if something else picks the choices. Candidates could be shown to the producer, or a rule could pick them. None of this exists yet, so the quality of a result with no designer is Unknown. An MCP-only route offers nothing here, because the client is the only interface. Only a route with its own interface, or the CLI, can run that way.

## 4. What each route changes about GPLv3 DawDreamer

### What the sources say

| Point | Text | Source |
| --- | --- | --- |
| DawDreamer's licence | `LICENSE` is byte-identical to the GPLv3 text. The PyPI classifier is GPLv3. | Observed ([LICENSE](https://github.com/DBraun/DawDreamer/blob/main/LICENSE)) |
| Convey | "any kind of propagation that enables other parties to make or receive copies" | [GPLv3 §0](https://www.gnu.org/licenses/gpl-3.0.txt) |
| Unconveyed use | "You may make, run and propagate covered works that you do not convey, without conditions" | [GPLv3 §2](https://www.gnu.org/licenses/gpl-3.0.txt) |
| Binaries | Object code must come with Corresponding Source. Source on another server is allowed with "clear directions", and "you remain obligated" to keep it available. | [GPLv3 §6(d)](https://www.gnu.org/licenses/gpl-3.0.txt) |
| Whole work | A work based on the program is licensed "as a whole" under the GPL. | [GPLv3 §5(c)](https://www.gnu.org/licenses/gpl-3.0.txt) |
| Aggregate | Separate works "not combined with it such as to form a larger program" stay outside the GPL. | [GPLv3 §5](https://www.gnu.org/licenses/gpl-3.0.txt) |
| One program or two | Same executable: "definitely combined". Designed to run in a shared address space: "almost surely" one program. Pipes and sockets "normally" separate, unless the exchange is intimate. FSF: "This is a legal question, which ultimately judges will decide." | [FAQ, MereAggregation](https://www.gnu.org/licenses/gpl-faq.html#MereAggregation) |
| Python bindings | An interpreted program using GPL facilities through bindings is "effectively linked" to them. | [FAQ, IfInterpreterIsGPL](https://www.gnu.org/licenses/gpl-faq.html#IfInterpreterIsGPL) |
| Linking | Static or dynamic makes no difference. | [FAQ, GPLStaticVsDynamic](https://www.gnu.org/licenses/gpl-faq.html#GPLStaticVsDynamic) |
| Passing on a binary | "you must distribute the complete corresponding source code too" | [FAQ, UnchangedJustBinary](https://www.gnu.org/licenses/gpl-faq.html#UnchangedJustBinary) |
| Installers | An installer and the files it installs are separate works. | [FAQ, GPLCompatInstaller](https://www.gnu.org/licenses/gpl-faq.html#GPLCompatInstaller) |
| Signing keys | Release is needed only if a User Product's hardware checks signatures. | [FAQ, GiveUpKeys](https://www.gnu.org/licenses/gpl-faq.html#GiveUpKeys) |

### Effect by route

| Route | What the maintainer ships | What changes |
| --- | --- | --- |
| Depends on the package: `pip`, `uvx`, `.mcpb` `uv` type | wav-to-serum source and a dependency name. PyPI serves DawDreamer. | The maintainer passes on no DawDreamer copy (Observed: the 103 KB bundle has none). **Legal interpretation:** whether naming a dependency "enables" others to receive copies is not answered by the text. |
| `.mcpb` `python` or `binary` type | A DawDreamer binary | The maintainer conveys it. §6 applies. |
| Mac app | A DawDreamer binary | The maintainer conveys it. §6 applies. §5(d) adds legal notices in the interface if the whole is under the GPL. |
| Claude directory plugin | Either of the above | Follows what the plugin carries. |

Further points, each **Legal interpretation** except where marked:

- **The FAQ view is the same in every route.** wav-to-serum imports DawDreamer through bindings and shares its address space, so on the FSF's reading they combine however they travel. Route changes who conveys what, not whether they combine. Whether MIT survives is the separate ticket.
- **A helper process does not settle it.** Rendering in a subprocess over a pipe moves toward "separate programs", but the FAQ also weighs how intimate the exchange is, and the helper is itself a Python program importing DawDreamer.
- **A notarized app is probably not a User Product case.** §6's Installation Information rule concerns transfer of a tangible consumer product. A download to a Mac the user already owns involves no such transfer, and Macs run modified unsigned code, so the FAQ's signing-key case looks inapplicable.
- **Re-signing.** Whether re-signing `dawdreamer.so` makes a modified version under §5 is not addressed by the sources I read.
- **Serum 2 is not conveyed by any route.** The producer supplies it. Whether a GPL host may load it belongs to the ticket on rendering through a GPL host.

### Source facts for a bundling route

- PyPI has wheels only, with no sdist. Source is the [`v0.9.0` tag](https://github.com/DBraun/DawDreamer/tree/v0.9.0) plus submodules for JUCE, Faust, Rubber Band, libsamplerate, nanobind, faustlibraries and Sampler (Observed).
- PyPI also carries macOS x86_64 wheels, beyond the arm64 ones (Observed).
- The wheel includes licence files for JUCE 5, JUCE 7, Faust, libsamplerate, pybind11 and Rubber Band (Observed). Rubber Band is GPL version 2 or later (Documented: [README](https://github.com/breakfastquay/rubberband)).
- Current JUCE is AGPLv3 or commercial (Documented: [LICENSE](https://github.com/juce-framework/JUCE/blob/master/LICENSE.md)).
- **Which JUCE is in the wheel is unclear.** The `v0.9.0` submodule pin resolves to a June 2018 commit that reports version 5.3.2. The changelog says the Sampler "was updated for JUCE 8". The wheel's licence files name JUCE 5 and 7. The binary carries no version string I could find. This affects which licence reaches a bundler (Unknown).
- The VST3 SDK is now MIT (Documented: [LICENSE](https://github.com/steinbergmedia/vst3sdk/blob/master/LICENSE.txt)). Which SDK version the wheel built with is Unknown.

## How the tests ran

Everything lived in scratch folders outside the repo. Nothing was installed into a client, and no client config was touched.

- **Install:** uv 0.9.7 with `UV_PYTHON_PREFERENCE=only-managed` and an empty cache, on a `pyproject.toml` listing `dawdreamer==0.9.0`, `serum2-preset-loader`, `mcp`, `numpy` and `librosa`.
- **Render:** one 1.5-second note, on the default patch and on a user `.SerumPreset` loaded through `serum2-preset-loader`.
- **MCP:** a stdio client calling a server with one sync and one async tool. Each thread scenario ran in its own process under a watchdog.
- **Signing:** a scratch copy of Python and the environment, signed ad hoc and then with an Apple Development identity. No Developer ID was available, so nothing was notarized.
- **Bundle:** `mcpb validate` and `mcpb pack`, never opened.

Limits of these tests:

- This Mac has SIP off, so library validation was not enforced.
- uv ran from a shell, not from Desktop, so its environment may differ.
- Claims about Desktop come from reading minified JavaScript for one version, and it can change.
- Only one machine with Serum 2 already licensed was used.

## Could not be verified

Most important first.

1. **The real Desktop install.** Whether a `uv` `.mcpb` installs DawDreamer and renders from inside Claude Desktop on a clean Mac. Apple ties library validation to hardened runtime, and uv's Python here is ad hoc signed and not hardened, so Serum 2 should load. That is an inference, not a test on a Mac with SIP on.
2. **Library validation on a normal Mac.** Whether Serum 2 is blocked without the entitlement, and loads with it, on a Mac with SIP on and a Developer ID build.
3. **Notarization of this stack.** Whether Apple's service accepts Python, the `dawdreamer.so` binary and the entitlements, and whether Gatekeeper's extra checks pass.
4. **Whether Anthropic keeps `uv`.** It ships in the app but is missing from Claude's docs.
5. **Gatekeeper and a `binary` `.mcpb`.** Whether an unnotarized binary unpacked by Desktop runs on a clean Mac.
6. **WAV and preset access.** Whether a file dropped into a Desktop chat reaches a local server as a path. Whether macOS file-access prompts appear for a server Desktop starts, and who they name. The Serum 2 preset folder was writable here, but it may not be everywhere.
7. **Which JUCE and which licence** the DawDreamer wheel contains.
8. **Whether naming a GPL dependency counts as conveying.** A lawyer's question.
9. **Long runs.** Claude documents a 240-second tool limit ([earlier report](mcp-client-behaviour.md)). How a tuner run fits is untested.
10. **Serum 2 without a licence.** Whether a demo or inactive install renders.
11. **Free-plan limits** against a full design session.
