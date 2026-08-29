---
description: "Comprehensive code review with quality and security checks"
agent: bahram-reviewer
---

# Review Command

Perform comprehensive code review with focus on quality, security, and maintainability.

## Usage

```
/review <target>
```

Where `<target>` can be:
- A file or directory path
- A pull request number
- A commit hash
- A branch name

## Review Process

1. **Context**: Understand the change and its purpose
2. **Analysis**: Examine implementation details
3. **Security**: Check for vulnerabilities
4. **Quality**: Assess readability and maintainability
5. **Feedback**: Provide actionable comments

## Review Checklist

### Correctness
- Logic matches requirements
- Edge cases handled
- Error handling appropriate
- No logic errors

### Security
- No secrets exposed
- Input validation present
- Output encoding proper
- Auth/authz correct

### Maintainability
- Code is readable
- Functions appropriately sized
- Naming descriptive
- Comments explain why

### Performance
- No obvious inefficiencies
- Queries optimized
- Memory usage reasonable
- Caching appropriate

## Output Format

### Summary
Overall assessment and recommendation

### Critical Issues
Issues that must be fixed

### Suggestions
Improvements for quality

### Questions
Clarifications needed

### Praise
Acknowledgment of good work

## Examples

```
/review ./src/auth.ts
/review PR #123
/review abc123
/review main
```

## Severity Levels

- **Critical**: Security vulnerability, data loss risk
- **Major**: Bug, performance issue, architectural concern
- **Minor**: Style issue, minor improvement
- **Info**: Question, suggestion, observation

## Integration

This command uses the Bahram Reviewer subagent. For general analysis, consider using the `/analyze` command instead.
