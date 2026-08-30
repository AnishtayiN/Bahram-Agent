# Bahram Agent Security Model

## Overview

Bahram implements a defense-in-depth security architecture with multiple layers of protection.

## Security Layers

### 1. Command Approval (ApprovalSystem)

**Location**: `bahram/security/approval.py`

**Wired to**: ToolExecutor (all tool calls)

**Protection**:
- 30+ dangerous patterns (rm -rf, fork bombs, etc.)
- Hardline blocklist (hardcoded critical commands)
- Risk assessment (critical/high/medium/low)
- Audit logging of all blocked attempts

**Test Coverage**: 8 red team tests

### 2. File Write Safety (FileWriteSafety)

**Location**: `bahram/security/file_safety.py`

**Wired to**: WriteTool, EditTool

**Protection**:
- Protected paths: /etc/passwd, /etc/shadow, /etc/sudoers, /boot, /sys, /proc, /root/.ssh
- Safe root restriction (optional)
- File size limits

**Test Coverage**: 4 red team tests

### 3. Website Policy (WebsitePolicy)

**Location**: `bahram/security/website_policy.py`

**Wired to**: WebFetchTool

**Protection**:
- Domain-based rules (malware.com, phishing.com blocked)
- Default allow with logging
- Custom rule support

### 4. SSRF Protection (SSRFProtector)

**Location**: `bahram/security/protection.py`

**Wired to**: WebFetchTool

**Protection**:
- Private IP ranges (10.x, 172.16-31.x, 192.168.x)
- Cloud metadata endpoints (169.254.169.254)
- Reserved IPv6 prefixes
- Internal network blocking

**Test Coverage**: 3 red team tests

### 5. Supply Chain Guard (SupplyChainGuard)

**Location**: `bahram/security/supply_chain.py`

**Wired to**: BashTool

**Protection**:
- Command validation
- Dependency checking
- Installation monitoring

### 6. Tirith Scanner (TirithScanner)

**Location**: `bahram/security/tirith.py`

**Wired to**: BashTool

**Protection**:
- Script scanning
- Injection detection
- Code analysis

## Tool Execution Pipeline

```
ToolCall received
    │
    ▼
ToolExecutor.execute()
    │
    ├─→ Tool exists? ──No──→ Error
    │
    ├─→ ApprovalSystem.check_command()
    │   └─→ Is dangerous? ──Yes──→ Risk critical/high? ──Yes──→ BLOCKED
    │
    ├─→ TirithScanner.scan_command()
    │   └─→ Violations? ──Yes──→ BLOCKED
    │
    ├─→ SupplyChainGuard.validate_command()
    │   └─→ Unsafe? ──Yes──→ BLOCKED
    │
    ├─→ tool.execute()
    │   └─→ Timeout? ──Yes──→ Error
    │   └─→ Exception? ──Yes──→ Error
    │
    └─→ ToolResult(success=True)
```

## Configuration

### Security Config (`config.yaml`)

```yaml
security:
  approval:
    enabled: true
    risk_threshold: high  # block critical + high
  file_safety:
    enabled: true
    protected_paths:
      - /etc/passwd
      - /etc/shadow
  ssrf:
    enabled: true
    block_private: true
  website_policy:
    enabled: true
```

## Test Summary

| Category | Tests | Result |
|----------|-------|--------|
| Command Injection | 8 | ✅ Pass |
| File Safety | 4 | ✅ Pass |
| SSRF Protection | 3 | ✅ Pass |
| Tool Executor Security | 4 | ✅ Pass |
| **Total** | **19** | **✅ Pass** |

## Recommendations

1. **Enable all security modules** in production
2. **Review audit logs** regularly
3. **Customize protected paths** for your environment
4. **Add domain rules** to WebsitePolicy as needed
5. **Run red team tests** before deployment
