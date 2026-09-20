# Operation Pancake — remote MCP verification checkpoint (2026-09-20)

## Scope and provenance

This is a **remote-only review**, not an acceptance sign-off. The authoritative checkout is `C:\Users\Trash Panda\pancakes` on `DESKTOP-M730I21`, branch `product/c3po-clean-room-roster`. No assertion below substitutes the GitHub branch for the local checkout. Do not merge or overwrite local work on the basis of this document.

## Verified during this review

- Remote Desktop Commander `list_devices` returned `DESKTOP-M730I21` with status `offline` and a valid authentication token. That does not establish the cause of the offline state.
- GitHub branch `product/c3po-clean-room-roster` resolved to `ffc827d354d9b4944447299710cb5918be2b9104`, dated 2026-09-10, with message `Align tests with exact card instance rule`. This remote ref predates the reported local MCP commits, so its files and revision cannot be treated as the authoritative September 20 state.
- GitHub `fetch_file` returned 404 for `src/operation_pancake/chatgpt_mcp_server.py` on that remote branch. This is **not** evidence that the file is absent from the Windows checkout.
- GitHub PR #2 is closed and merged (2026-09-06); do not reopen or re-merge it.
- A prior user-visible PowerShell screenshot showed the tunnel client's local readiness endpoint `http://127.0.0.1:8080/readyz` returned `ready`. This is a snapshot, **not** proof of current tunnel availability or of a successful call from ChatGPT.
- GitHub Actions returned one workflow run for the original review commit, `35530185562`, with conclusion `skipped`; its two jobs were skipped. No tests have been claimed green from this run.

## Verified OpenAI documentation and route selection

- OpenAI's current developer-mode Help Center article lists ChatGPT Business and Enterprise/Edu for full MCP, and says Pro supports read/fetch MCP in developer mode. **Plus is not listed as eligible for this developer-mode app-creation route**. This is a documented eligibility constraint, not a diagnosis of any particular user's account or a claim about unseen UI: https://help.openai.com/en/articles/12584461-developer-mode-and-mcp-apps-in-chatgpt
- OpenAI's Secure MCP Tunnel guide explicitly separates Platform tunnel permissions from ChatGPT developer-mode permission. A healthy tunnel does not grant a ChatGPT developer-mode control: https://developers.openai.com/api/docs/guides/secure-mcp-tunnels
- The same tunnel guide documents a **supported alternative**: use the existing `tunnel_id` as the MCP tool's `tunnel_id` field in a Responses API request, rather than putting the hosted endpoint in `server_url`. This route requires a properly authorized API key, a live `tunnel-client`, and a reachable local MCP server; it has **not** been executed or validated for Pancake. No key or secret belongs in this repository or PR.
- The OpenAI Platform connector available in the conversation provides API-key setup only; it does not expose a Responses API invocation or ChatGPT custom-app creation action. GitHub cannot invoke the private Windows MCP endpoint from this connection.

## Reported prior local work — not reverified in this review

- Read-only comparison adapter commit `934dbd0`, MCP server commit `34c47bf`, acceptance documentation commit `022c501`.
- Local MCP address `http://127.0.0.1:18790/mcp`; backend `http://127.0.0.1:8788`.
- Target ChatGPT invocation of the single `compare_roster_card` tool has **not** been demonstrated.

## Safe continuation gate

1. When Windows access is restored, read the local `.operation_pancake/` recovery map and verify `git status`, HEAD, and all pre-existing changes before any integration or merge.
2. Verify backend and MCP tool response locally, then verify the tunnel's live health separately. Never equate `readyz` with ChatGPT acceptance.
3. Do not direct a Plus user through an undocumented ChatGPT developer-mode app-creation path. If an approved ChatGPT app route becomes available, verify actual tool discovery and invocation from ChatGPT. Otherwise, use a separately labeled Responses API test with the existing tunnel, without claiming that it establishes ChatGPT app availability.
4. Preserve the existing read-only boundaries: no purchase, auction import, roster writes, exposed secrets, invented prices or eligibility.

This document intentionally changes **no application code, roster data, pricing data, existing recovery map, or production branch**.
