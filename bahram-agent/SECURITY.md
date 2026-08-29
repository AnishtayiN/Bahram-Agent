# Security Policy

## Supported Versions

| Version | Supported          |
| ------- | ------------------ |
| 1.0.x   | :white_check_mark: |
| < 1.0   | :x:                |

## Reporting a Vulnerability

If you discover a security vulnerability within Bahram Agent, please send an email to [security@example.com](mailto:security@example.com). All security vulnerabilities will be promptly addressed.

**Please do not report security vulnerabilities through public GitHub issues.**

### What to include

When reporting a vulnerability, please include:

- Type of issue (e.g., buffer overflow, SQL injection, cross-site scripting, etc.)
- Full paths of source file(s) related to the manifestation of the issue
- The location of the affected source code (tag/branch/commit or direct URL)
- Any special configuration required to reproduce the issue
- Step-by-step instructions to reproduce the issue
- Proof-of-concept or exploit code (if possible)
- Impact of the issue, including how an attacker might exploit it

### What to expect

- Acknowledgment of your report within 48 hours
- An assessment of the vulnerability within 7 days
- A fix or mitigation plan within 30 days
- Credit for the discovery (unless you prefer to remain anonymous)

## Security Best Practices

When using Bahram Agent:

1. **Keep dependencies updated**
   ```bash
   pip install --upgrade bahram-agent
   ```

2. **Use environment variables for secrets**
   ```bash
   export ANTHROPIC_API_KEY="your-key-here"
   ```

3. **Enable security features**
   - DM Pairing for messaging platforms
   - Command approval for bash operations
   - File write safety checks

4. **Review logs regularly**
   - Check for unauthorized access attempts
   - Monitor API usage
   - Review command execution history

## Security Features

Bahram Agent includes several built-in security features:

- **Command Approval**: Requires approval for dangerous bash commands
- **SSRF Protection**: Blocks access to private networks
- **File Write Safety**: Protects critical system files
- **DM Pairing**: Requires authorization for messaging platforms
- **Tirith Scanner**: Pre-execution content scanning
- **Supply Chain Checker**: Monitors for compromised dependencies

## Contact

For security-related inquiries, please contact:
- Email: security@example.com
- GitHub Security Advisories: https://github.com/AnishtayiN/Bahram-Agent/security/advisories
