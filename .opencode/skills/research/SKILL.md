---
name: research
description: "Deep research and analysis skill. Use when gathering information, analyzing systems, or exploring codebases. Triggered by research requests, investigation tasks, or exploration needs."
---

# Research Skill

Perform deep research and analysis on any topic, codebase, or system.

## Research Process

### 1. Define Scope
- Clarify the research question
- Identify boundaries and constraints
- Determine required depth

### 2. Gather Information

#### Codebase Research
- Use glob to find relevant files
- Use grep to locate patterns
- Read key files to understand structure
- Map dependencies and relationships

#### Web Research
- Search for current best practices
- Find documentation and examples
- Compare different approaches
- Gather evidence and data

#### System Research
- Analyze existing configurations
- Review logs and metrics
- Test behaviors and edge cases
- Document findings

### 3. Analysis

#### Pattern Recognition
- Identify common patterns
- Note anti-patterns
- Compare with best practices
- Look for opportunities

#### Risk Assessment
- Identify potential issues
- Evaluate impact and likelihood
- Consider mitigation strategies
- Document concerns

#### Comparison
- List pros and cons
- Consider trade-offs
- Evaluate alternatives
- Make recommendations

### 4. Synthesis

Create actionable output:

#### Executive Summary
Brief overview of key findings

#### Detailed Findings
- Point 1 with evidence
- Point 2 with evidence
- Point 3 with evidence

#### Recommendations
Based on findings, what should be done

#### Sources
References and citations

## Research Templates

### Codebase Exploration
```
## Codebase Analysis: [Project Name]

### Structure
[Directory layout and organization]

### Key Components
[Main modules and their purposes]

### Patterns
[Design patterns and conventions]

### Issues
[Problems or concerns identified]

### Recommendations
[Suggested improvements]
```

### Technology Evaluation
```
## Technology Evaluation: [Technology Name]

### Overview
[What it is and what it does]

### Pros
[Advantages and benefits]

### Cons
[Disadvantages and drawbacks]

### Use Cases
[When to use this technology]

### Alternatives
[Comparable options]

### Recommendation
[Your assessment]
```

### Problem Investigation
```
## Problem Investigation: [Issue Description]

### Symptoms
[What was observed]

### Root Cause
[Why it happened]

### Impact
[What was affected]

### Solution
[How it was or should be fixed]

### Prevention
[How to avoid in future]
```

## Integration with Bahram

This skill works with the Bahram Researcher subagent for comprehensive research. The researcher can be invoked via:
```bash
/opencode run bahram-researcher --research <topic>
```

## Quality Standards

- Verify information from multiple sources
- Distinguish facts from opinions
- Acknowledge uncertainties
- Cite sources appropriately
- Update findings as new information emerges
