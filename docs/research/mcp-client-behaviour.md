# What MCP clients do with annotations, media and long results

Checked on 2026-11-01. It states facts about how MCP clients behave and leaves design decisions open.

Versions: Claude Code 2.1.316, tested. Claude Desktop 4.4212.0, shipped bundle read but not run. Cursor was not installed, so it was neither read nor run. Spec: MCP `2026-07-28`.

## Evidence labels

| Label | Meaning |
| --- | --- |
| **Documented** | The vendor's own docs, changelog or release notes say so. |
| **Observed** | I saw it myself, in a real test or in the shipped code. |
| **Reported** | Someone else saw it: a vendor forum post or a public issue. Not reproduced here. |
| **Unknown** | No source settles it, and no test was run. |

## The answer

All three clients ask before an MCP tool runs by default, but none of them always asks. Every one has a setting or mode where tools run with no person involved.

Annotations do not behave the same way across clients. In Claude Code's default mode, `readOnlyHint` did not change consent, and `destructiveHint` did not stop a tool running under an allow rule or in auto mode. Anthropic's connector docs say the hints set permissions in claude.ai and Desktop, but a public report says that fails for local servers. Cursor's docs do not mention them.

Images reach the model in Claude Code and, per its docs, in Cursor on models that support images. Desktop reports conflict. Audio did not reach the model in Claude Code, which saves it to a file. For Desktop and Cursor, audio is unknown.

Long successful results are mostly moved, not trimmed. Claude Code and Cursor save them to a file and give the model a pointer. Desktop does the same above about 150,000 characters when its code sandbox is active. Claude Code does cut long error text, and it removes the middle.

## Tested against common assumptions

### "The mount publishes annotations, blocks nothing, and trusts the client to ask"

**Holds:** each client documents asking by default, so the mount does not need its own gate for that default.

**Contradicted:** "the client asks" is a default, not a guarantee.

- Claude Code ran a `destructiveHint: true` tool with no prompt under an allow rule and in auto mode (Observed).
- Cursor runs every call in Run Everything mode (Documented).
- Claude's Research feature can call connector tools "automatically without further approval" (Documented).

**Contradicted:** publishing an annotation does not buy a prompt in Claude Code. In the test, `destructiveHint: true` added no prompt, and `readOnlyHint: true` removed none. The documented way to force a prompt there is a non-standard field, `_meta["anthropic/requiresUserInteraction"]`, which is not one of the MCP annotations.

**Contradicted, for one default:** an unset `destructiveHint` means `true` in the spec, but Claude Code's shipped code reads it as `false`, and its SDK docs say an unset value counts as `false` for `always_ask` calls. Leaving it unset does not mean the same thing everywhere.

**Softer than the map states:** the map says the spec requires hosts to get consent before any tool runs. That sentence exists, but it sits in the spec's lowercase Key Principles, followed by "MCP itself cannot enforce these security principles at the protocol level". The tools page says a human **SHOULD** be in the loop. The schema adds that "Clients should never make tool use decisions based on `ToolAnnotations` received from untrusted servers".

### "Nothing cuts a result after the fact, and tools design to a result budget"

**Holds:** Claude Code and Desktop document a size limit, and a Cursor staff post describes the same behaviour. For successful results, none of them normally chooses what to leave out.

**Contradicted:** "clients already cap results" suggests the model still gets the first part. In Claude Code it gets none of it. Over the limit, the whole result is replaced by a pointer, and the model must read a file to see any content. If it has no way to read the file, the pointer tells it to stop retrying and say what it could not read. Cursor staff describe the same pointer pattern.

**Contradicted, for errors:** Claude Code does cut after the fact when a result is marked `isError: true`. Text over about 11,000 characters keeps only its first and last 5,000 (Documented, Observed).

**Not settled:** there is no shared budget number. Claude Code warns at 10,000 tokens, and limits at 25,000 tokens and 50,000 characters. Desktop documents about 150,000 characters. Cursor publishes no number.

## MCP spec baseline

| Point | Text | Source |
| --- | --- | --- |
| Consent | "Hosts must obtain explicit user consent before invoking any tool", under Key Principles, then "MCP itself cannot enforce these security principles" | [Specification](https://modelcontextprotocol.io/specification/2026-07-28) |
| Human in the loop | "there **SHOULD** always be a human in the loop with the ability to deny tool invocations" | [Tools](https://modelcontextprotocol.io/specification/2026-07-28/server/tools) |
| Trust in annotations | Clients "**MUST** consider tool annotations to be untrusted unless they come from trusted servers" | [Tools](https://modelcontextprotocol.io/specification/2026-07-28/server/tools) |
| Hint defaults | `readOnlyHint` false, `destructiveHint` true, `idempotentHint` false, `openWorldHint` true | [Schema](https://modelcontextprotocol.io/specification/2026-07-28/schema) |
| Content types | Text, image, audio, resource links and embedded resources | [Tools](https://modelcontextprotocol.io/specification/2026-07-28/server/tools) |

## Claude Code

| Question | Finding | Evidence |
| --- | --- | --- |
| Does it ask by default? | Yes. `default` mode prompts on first use of each tool. In `claude -p`, where no prompt can appear, all three probes were refused with "you haven't granted it yet". | Documented ([permissions](https://code.claude.com/docs/en/permissions)), Observed |
| When does nobody get asked? | An allow rule ran `destr_probe` with reason `rule`. Auto mode ran all three probes with reason `classifier`. `bypassPermissions` also skips prompts. | Observed (first two), Documented ([permissions](https://code.claude.com/docs/en/permissions)) |
| Does `readOnlyHint` change consent? | Not in default mode: the tool was refused exactly like the unannotated one. Its documented uses are parallel calls and safe retries. | Observed, Documented ([MCP](https://code.claude.com/docs/en/mcp)) |
| Does `destructiveHint` change consent? | It did not stop an allow rule or auto mode in the test. The documented effect is narrow: in auto mode it sends an `always_ask` SDK tool to the callback instead of the classifier. | Observed, Documented ([SDK reference](https://code.claude.com/docs/en/agent-sdk/typescript)) |
| How does it read an unset `destructiveHint`? | As `false`, in `isDestructive()`. The SDK docs give the same reading for `always_ask` calls, while their field table lists the default as `true`. | Observed (shipped code), Documented ([custom tools](https://code.claude.com/docs/en/agent-sdk/custom-tools)) |
| Can a server force a prompt? | Yes, with `_meta["anthropic/requiresUserInteraction"]: true`. It prompts even in `auto` and `bypassPermissions`, and `dontAsk` denies the call. Not tested here. | Documented ([MCP](https://code.claude.com/docs/en/mcp)) |
| Do images reach the model? | Yes. PNG, JPEG, GIF and WebP appear inline and are also saved to a file. The test model named the colour of a red PNG. | Documented ([MCP](https://code.claude.com/docs/en/mcp)), Observed |
| Does audio reach the model? | No. The model got the sibling text block plus "Binary content (audio/wav, 1.6KB) saved to" a path. The MCP docs page does not cover audio. The changelog does, at 2.1.69. | Observed, Documented ([changelog](https://github.com/anthropics/claude-code/blob/main/CHANGELOG.md)) |
| How is long text treated? | Warns above 10,000 tokens. Above 25,000 tokens, or 50,000 characters, a successful result without images goes to a file. A 40,016-character result arrived whole. A 60,016-character result became a 1,585-character pointer starting "Error: result", with the tail absent and `is_error` unset. | Documented ([MCP](https://code.claude.com/docs/en/mcp)), Observed |
| Can a tool raise the limit? | Yes, with `_meta["anthropic/maxResultSizeChars"]`, up to 500,000 characters. `MAX_MCP_OUTPUT_TOKENS` raises the token limit for the user. Neither was tested. | Documented ([MCP](https://code.claude.com/docs/en/mcp)) |
| How is long error text treated? | Above about 11,000 characters, it keeps the first and last 5,000 with a marker between. A 20,016-character error arrived as 10,040 characters. | Documented ([MCP](https://code.claude.com/docs/en/mcp)), Observed |

## Claude Desktop

Desktop has three surfaces: Chat, Cowork and the Code tab. This table covers Chat and Cowork. The Code tab runs Claude Code. Nothing here was run in Desktop.

| Question | Finding | Evidence |
| --- | --- | --- |
| Does it ask by default? | The connector docs describe approval requests and each tool's Always allow, Needs approval or Blocked setting. The local MCP help page says nothing about approval. Public reports show prompts for local servers. | Documented ([custom connectors](https://support.claude.com/en/articles/11175166-get-started-with-custom-connectors-using-remote-mcp), [connectors](https://support.claude.com/en/articles/11176164-use-connectors-to-extend-claude-s-capabilities)), Reported |
| When does nobody get asked? | "Allow always". Research, which can call connector tools "automatically without further approval". Cowork's Skip mode, which approves Needs approval tools. | Documented ([custom connectors](https://support.claude.com/en/articles/11175166-get-started-with-custom-connectors-using-remote-mcp), [Cowork](https://support.claude.com/en/articles/13345190-get-started-with-claude-cowork)) |
| Do annotations change consent? | Documented yes: "These determine auto-permissions in Claude. Read-only tools can run without per-call confirmation, and destructive tools always prompt." Cowork's Auto mode approves read-only tools. The "always" conflicts with Cowork's Skip mode on Anthropic's own pages. | Documented ([review criteria](https://claude.com/docs/connectors/building/review-criteria), [Cowork](https://support.claude.com/en/articles/13345190-get-started-with-claude-cowork)) |
| Does that work for local servers? | An open report says Chat's Auto mode still prompts on every read-only call from a local server, while the Connectors page groups the tools correctly. A commenter reproduced it on Windows. | Reported ([claude-ai-mcp 1090](https://github.com/anthropics/claude-ai-mcp/issues/1090)) |
| Does the app read annotations? | Yes. It sends `anthropic/readOnlyHint` with local tool definitions. I did not find the Chat approval decision in the bundle. | Observed (shipped code) |
| Are annotations required? | For the Connectors Directory, yes: a `title` and the applicable hint on every tool. I found no such requirement for local servers. | Documented ([submission](https://claude.com/docs/connectors/building/submission)) |
| Do images reach the model? | Docs say text and image results are supported. Reports conflict: yes for a local stdio server, but empty image slots through a remote connector, with the same server working in Claude Code. | Documented ([build guide](https://claude.com/docs/connectors/building)), Reported ([1173](https://github.com/anthropics/claude-ai-mcp/issues/1173), [238 comment](https://github.com/anthropics/claude-ai-mcp/issues/238)) |
| Does audio reach the model? | Not established. The docs list text and image results. Audio is on neither the supported list nor the "doesn't yet support" list. | Unknown |
| How is long text treated? | Maximum about 150,000 characters. Above that, with the code sandbox active, the result goes to the sandbox filesystem and an MCP App gets a pointer instead of its data. Tool calls time out at 240 seconds. | Documented ([build guide](https://claude.com/docs/connectors/building), [troubleshooting](https://claude.com/docs/connectors/building/mcp-apps/troubleshooting)) |
| What if the sandbox is off? | Not stated. | Unknown |
| How is long error text treated? | Not stated. | Unknown |

## Cursor

Cursor is closed source and was not installed here, so nothing in this table was tested.

| Question | Finding | Evidence |
| --- | --- | --- |
| Does it ask by default? | "Cursor asks for approval before using MCP tools by default." | Documented ([MCP](https://cursor.com/docs/mcp)) |
| When does nobody get asked? | Allowlisted tools run at once. In Auto-review, other calls go to a classifier on Cursor's backend, which "is not a security boundary". Run Everything runs every call. The CLI's `--approve-mcps` auto-approves MCP servers, and the docs do not say whether that covers each tool call. | Documented ([Run Modes](https://cursor.com/docs/agent/security/run-modes), [CLI](https://cursor.com/docs/cli/mcp)) |
| Do annotations change consent? | The MCP, Run Modes, CLI and help pages never mention them. Release 3.23 says Auto-review now shows the approval card for calls "the server marks as requiring confirmation", but not which field marks them. | Unknown, Documented ([release notes](https://cursor.com/docs/release-notes)) |
| Are annotations used anywhere? | In Cursor's separate Agent SDK, which retries read-only and some idempotent tools. Hints on its custom tools are "descriptive hints only". This says nothing about the editor. | Documented ([SDK tools](https://cursor.com/docs/agent-sdk/reference/tools), [release notes](https://cursor.com/docs/release-notes)) |
| Do images reach the model? | Yes, with a limit: "Cursor attaches returned images to the chat. If the model supports images, it analyzes them." | Documented ([MCP](https://cursor.com/docs/mcp)) |
| Does audio reach the model? | Not established. The docs are silent and I found no report. | Unknown |
| How is long text treated? | The docs are silent. Staff say the full response is saved to a workspace file and the model gets a pointer. Inline cutting happens only if that write fails, and the model is told. No threshold is given. | Reported, by staff ([August 2026](https://forum.cursor.com/t/cursor-truncates-mcp-tool-responses/168384)) |
| Can the model read a long result back? | In February 2026 staff called output over 100,000 characters a dead end, because Read File stops there, and suggested filtering inside the tool. A user said in August that little had changed. Current state not confirmed. | Reported, by staff ([February 2026](https://forum.cursor.com/t/mcp-file-read-tool-endlessly-chains-temp-files-for-large-outputs-making-real-content-inaccessible-v2/153165)) |
| How is long error text treated? | Not stated. | Unknown |
| What about `structuredContent` alone? | With an empty `content` array, the model gets an empty result. Staff say it is unintended and tracked, and suggest also returning the data as text. | Reported, by staff ([August 2026](https://forum.cursor.com/t/mcp-tool-results-containing-only-structuredcontent-are-silently-dropped/167346)) |

## How the Claude Code test ran

A throwaway stdio server, stdlib only, exposed eight tools with fixed canary text. It ran through `claude -p` with `--strict-mcp-config`, empty `--setting-sources` and the `haiku` model, so no user rules applied.

| Run | Mode | Result |
| --- | --- | --- |
| A | `default`, no allow rule | `ro_probe`, `destr_probe` and `plain_probe` all refused the same way |
| B | `default`, allow rule `mcp__probe__*` | All six tools called ran, including `destr_probe`, with reason `rule` |
| C | `auto` | All three probes ran, with reason `classifier` |

Limits of this test:

- Print mode shows no prompts, so run A shows a refusal in place of a prompt. The interactive dialog was not exercised.
- The 10,000-token warning is a screen message, so it was not seen.
- Run C used harmless tools with no arguments. It shows a classifier can pass a destructive-annotated tool, not that it always will.
- Claims about shipped code come from reading minified JavaScript.

## Could not be verified

- **Desktop, live:** nothing was run. A real test means editing a live `claude_desktop_config.json` and driving the app, which I left alone. The same probe would settle audio, image delivery and long results for local servers.
- **Desktop, consent logic:** where Chat decides on annotations. The app forwards the read-only hint, so the decision may sit outside the bundle.
- **Desktop, unset hints:** what happens to a tool with no annotations.
- **Cursor, everything live:** whether the editor reads `readOnlyHint` or `destructiveHint`, what marks a tool as requiring confirmation, whether audio reaches the model, and the long-result threshold.
- **Claude Code, oversized images:** the docs say image results stay under the token limit, but they describe the save-to-file path only for results with no image content.
- **Claude Code, `requiresUserInteraction` and `maxResultSizeChars`:** documented but not tested.
