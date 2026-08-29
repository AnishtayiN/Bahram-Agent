---
name: code-review
description: "Comprehensive code review skill. Use when reviewing code for quality, security, and maintainability issues. Triggered by code review requests, PR reviews, or quality audits."
---

# Code Review Skill

Perform thorough code reviews with focus on quality, security, and maintainability.

## Review Process

### 1. Initial Assessment
- Understand the purpose of the change
- Identify the scope and impact
- Note any related issues or PRs

### 2. Code Analysis

#### Correctness
- Verify logic matches requirements
- Check for off-by-one errors
- Validate error handling
- Test edge cases mentally

#### Security
- Scan for secrets/credentials
- Check input validation
- Verify output encoding
- Review auth/authz

#### Performance
- Identify unnecessary operations
- Check algorithm complexity
- Review database queries
- Look for memory issues

#### Maintainability
- Assess code readability
- Check function/method sizes
- Review naming conventions
- Evaluate documentation

### 3. Feedback Generation

#### Critical Issues
```markdown
**[CRITICAL]**: Description of critical issue
- Location: file:line
- Impact: What could go wrong
- Fix: How to resolve
```

#### Suggestions
```markdown
**[SUGGESTION]**: Description of improvement
- Location: file:line
- Benefit: Why this is better
- Implementation: How to do it
```

#### Questions
```markdown
**[QUESTION]**: Clarification needed
- Context: What prompted this
- Impact: Why it matters
```

### 4. Summary

Provide overall assessment:
- **Approval**: Code is ready to merge
- **Approval with comments**: Minor issues noted
- **Request changes**: Significant issues found

## Common Issues to Check

### JavaScript/TypeScript
- Unused imports/variables
- Missing error boundaries
- Inconsistent async/await usage
- Potential memory leaks

### Python
- Missing type hints
- Broad exception catching
- Mutable default arguments
- Global state usage

### Go
- Ignored errors
- Goroutine leaks
- Race conditions
- Missing context cancellation

### Rust
- Unnecessary clones
- Missing error handling
- Unsafe code usage
- Lifetime issues

## Review Comments Style

Be constructive and specific:
- Explain why something is an issue
- Provide concrete examples
- Suggest alternatives
- Acknowledge good patterns

## Integration with Bahram

This skill works with the Bahram Reviewer subagent for comprehensive reviews. The reviewer can be invoked via:
```bash
/opencode run bahram-reviewer --review <target>
```
