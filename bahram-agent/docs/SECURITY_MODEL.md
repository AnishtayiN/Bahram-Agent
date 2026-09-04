# Bahram Agent Security Model

Defence in depth: a tool call has to get past the engine, past the tool's own
guard, and past the specific guard for its resource class. Every layer named
here is reachable from running code — the "Proven by" column is a test file,
not a claim.

Regenerate the evidence with:

```bash
cd bahram-agent
python -m pytest tests/test_security_hardening.py tests/redteam -q
```

---

## 0. Secret redaction — `bahram/security/redaction.py`

Installed as a `logging.Filter` on the root logger by `Agent._setup_logging`,
so every record emitted by Bahram *and* by the HTTP and SDK libraries it
drives is scrubbed before a handler sees it. `SecretsManager.redact()` uses
the same patterns plus the exact values it holds.

Removes: `sk-…` / `sk-ant-…` provider keys, `ghp_`/`gho_`/`github_pat_`
tokens, `AKIA…` access keys, `AIza…` Google keys, `xox[baprs]-` Slack tokens,
JWTs, `Bearer`/`Basic` credentials, `Authorization` headers,
`api_key`/`password`/`secret`/`token` assignments, PEM private-key blocks and
`https://user:pass@host` URL credentials — plus any exact value registered with
`register_secret_value()`.

*Proven by*: `tests/test_security_hardening.py::TestRedaction`.

---

## 1. Command approval — `bahram/security/approval.py`

**Wired to**: `ToolExecutor._execute_once` in `bahram/core/engine.py`, so it
covers **every** tool call, not just `bash`. The engine renders each call to a
command string — `arguments["command"]` for `bash`, `arguments["code"]` for
`execute_code`, and `name(<json arguments>)` for everything else — and runs it
through the policy.

* 39 dangerous patterns (recursive delete, chmod 777, mkfs, dd, SQL DROP /
  DELETE without WHERE / TRUNCATE, systemctl, fork bombs, shell exec flags,
  pipe-to-shell, exfiltration via `curl`/`wget`/`nc`, path traversal, reading
  `/etc/shadow`…).
* 6 hardline patterns blocked before anything else (`rm -rf /`, `:(){ :|:& };:`,
  `mkfs.* /dev/*`, `dd if=/dev/zero of=/dev/*`).
* Risk assessment: `critical` / `high` / `medium` / `low`. Any non-`low`
  verdict blocks the call and is recorded by `ToolExecutor._log_event`.
* `approve_once` is session-scoped and matched with `fnmatch` against the
  whole command — approving `rm -rf build/` does not approve `rm -rf src/`,
  and a fresh `ApprovalSystem` does not inherit a previous session's
  approvals.
* `config.deny` patterns are checked **before** the allow-list, so a deny rule
  cannot be overridden by an approval.

*Proven by*: `tests/test_security_hardening.py::TestApprovalSystemHardening`
and `tests/redteam/test_redteam.py::TestApprovalReplay`.

---

## 2. Command scanner (Tirith) — `bahram/security/tirith.py`

**Wired to**: `BashTool.execute`, before the subprocess is created.

Classifies into `blocked` (critical: `rm -rf /`, `mkfs`, `dd … of=/dev/…`;
plus hardcoded secret assignments), `issues` (high: `chmod 777`,
`curl|sh`, `wget|sh`) and `warnings` (medium: `eval(`, `exec(`, `__import__`,
`os.system`, `subprocess.call(shell=True)`). `BashTool` refuses when there is
anything in `blocked` or `issues`.

*Proven by*: `tests/test_security_hardening.py::TestTirithScanner`.

---

## 3. Supply-chain guard — `bahram/security/supply_chain.py`

**Wired to**: `BashTool.execute`, after Tirith. `SupplyChainGuard` refuses

* dependency confusion — `--index-url` / `--extra-index-url` / `-i` /
  `--registry` pointing anywhere other than `pypi.org` or
  `registry.npmjs.org`;
* disabled verification — `--trusted-host`, `--no-verify`, `--disable-gpg`;
* unverified remote install scripts — `curl … | sh`, `wget … | bash`,
  `bash <(curl …)`.

Plain `pip install requests` is deliberately allowed: pinning is policy, not a
security boundary, and refusing it would make the tool unusable.

`SupplyChainChecker` in the same module audits what is already installed
(world-writable files, unpinned requirements, known-vulnerable packages).

*Proven by*: `tests/test_security_hardening.py::TestSupplyChainGuard` and
`::TestSupplyChainChecker`.

---

## 4. SSRF protection — `bahram/security/protection.py`

**Wired to**: `WebFetchTool.execute` and `WebSearchTool.execute`.

Any host is resolved with `socket.getaddrinfo` and **every** returned address
is classified with the `ipaddress` module; anything that is not globally
routable unicast is refused. Refused classes: loopback, link-local
(`169.254.169.254`), RFC1918, CGNAT (`100.64/10`), reserved, multicast,
unspecified. Also refused: `localhost` and `*.localhost` by name, and the
cloud metadata host names.

Numeric spellings of an address are decoded before classification, so
`http://2130706433/`, `http://0x7f000001/` and `http://017700000001/` are all
recognised as `127.0.0.1`. IPv6 literals are handled including the
IPv4-mapped form `[::ffff:127.0.0.1]`.

**Known limitation — DNS rebinding.** The name is resolved once, at check
time. A name that resolves to a public address then and to a private one when
`httpx` connects is not caught. Closing it means pinning the resolved address
on the socket, which is a change to how `httpx` is used in
`bahram/tools/web.py`; it is recorded in the source docstring rather than
papered over here.

*Proven by*: `tests/test_security_hardening.py::TestSSRFProtector`.

---

## 5. Website policy — `bahram/security/website_policy.py`

**Wired to**: the same two web tools, before the SSRF check. An ordered rule
list (`deny` / `allow` / `log`) matching on substrings and `*.domain` patterns,
with `*.malware.com` and `*.phishing.com` denied out of the box and
`github.com`, `stackoverflow.com`, `docs.python.org` allowed.

*Proven by*: `tests/test_security_hardening.py::TestWebsitePolicy`.

---

## 6. Prompt-injection detection — `bahram/security/protection.py`

`PromptInjectionDetector.scan_file` flags instruction overrides
(`ignore previous instructions`, `disregard the previous …`, `forget
everything`), role hijacks (`you are now`, `act as if`), HTML injection and
hidden comments, credential access (`.env`, `credentials`, `.netrc`),
exfiltration (`curl -d`, `wget --post-data`) and invisible Unicode
(zero-width space, bidi overrides U+202A–U+202E, BOM).

Used to *vet* content — `SecurityManager.scan_context_file` — so a poisoned
file or memory entry is detected and reported. It is not a substitute for
treating retrieved content as data: see the memory-poisoning tests.

*Proven by*: `tests/test_security_hardening.py::TestPromptInjectionDetector`
and `tests/redteam/test_redteam.py::TestPromptInjectionViaMemory`.

---

## 7. File write safety — `bahram/security/file_safety.py`

**Wired to**: `ReadTool`, `WriteTool`, `EditTool` in `bahram/tools/file.py`.

* Protected **directories**, not individual files: `/etc`, `/boot`, `/sys`,
  `/proc`, `/dev`, `/bin`, `/sbin`, `/usr/bin`, `/usr/sbin`, `/root`.
  (Listing files one at a time could not keep up — `/etc/cron.d/payload` was
  writable under the old list.)
* Path traversal: a target containing `..` must still resolve inside the
  current working directory.
* **Symlink escape**: whenever the resolved path differs from the literal one,
  the real target must be inside the working directory. A symlink can contain
  no `..` at all and still point somewhere else entirely, so resolving is not
  optional.
* Optional `set_safe_root()` sandbox; optional maximum file size.

*Proven by*: `tests/test_security_hardening.py::TestFileWriteSafety`
(including a real symlink that escapes the workspace) and
`tests/redteam/test_redteam.py::TestPathTraversal`.

---

## 8. Secret store — `bahram/core/secrets.py`

Values are XOR-encrypted with a 32-byte per-installation key stored in
`data/secrets/.key` (mode `0600`), and `secrets.enc` is written `0600`. A
corrupt store logs a warning and starts empty rather than crashing.
`SecretsManager.redact()` removes every stored value from arbitrary text.

Note: this is obfuscation at rest against casual disclosure, not a
substitute for OS-level encryption or a proper secret manager.

*Proven by*: `tests/test_core_services.py::TestSecretsManager` — including an
assertion that the plaintext value does not appear in `secrets.enc`.

---

## 9. Capability kernel — `bahram/security/kernel.py` — **not wired**

`SecurityKernel` implements capability grant/revoke, risk ceilings, expiry,
one-time capabilities and parent/child scope attenuation. Nothing in
`bahram/` constructs it; it is exercised by unit tests only. Listed here so
the gap is on the record rather than implied.

*Proven by*: `tests/test_security_hardening.py::TestSecurityKernel`.

---

## Deliberate non-actions

* **`bash` uses `create_subprocess_shell`.** It is a shell tool; that is the
  point. The protection is the approval system plus Tirith plus the
  supply-chain guard, all of which run first.
* **Unresolvable hosts are allowed by the SSRF check.** Refusing would break
  every offline deployment, and the request itself fails anyway.
* **DNS rebinding is not mitigated** (see §4).
* **`read` is not blocked from reading `/etc/passwd` by `FileWriteSafety`** —
  that guard is about *writes*. The `cat /etc/shadow` pattern in the approval
  system covers the common exfiltration phrasing in a `bash` command.
