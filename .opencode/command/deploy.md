---
description: "Deployment automation with safety checks"
agent: bahram
---

# Deploy Command

Automate deployment processes with built-in safety checks and rollback capabilities.

## Usage

```
/deploy <environment> [--strategy <strategy>]
```

Where:
- `<environment>`: target environment (dev, staging, production)
- `--strategy`: deployment strategy (blue-green, rolling, feature-flag)

## Deployment Process

1. **Pre-flight**: Verify readiness
2. **Build**: Create deployment artifacts
3. **Test**: Run deployment tests
4. **Deploy**: Execute deployment
5. **Verify**: Confirm success
6. **Monitor**: Watch for issues

## Pre-Deployment Checks

### Code Readiness
- [ ] All tests passing
- [ ] Code review completed
- [ ] Documentation updated
- [ ] Changelog updated

### Environment Ready
- [ ] Infrastructure provisioned
- [ ] Secrets configured
- [ ] Dependencies available
- [ ] Monitoring enabled

### Safety Measures
- [ ] Rollback plan documented
- [ ] Feature flags configured
- [ ] Alerts set up
- [ ] Communication sent

## Deployment Strategies

### Blue-Green
- Zero downtime
- Easy rollback
- Full environment swap

### Rolling
- Gradual rollout
- Resource efficient
- Canary testing

### Feature Flag
- Progressive delivery
- A/B testing
- Instant rollback

## Post-Deployment Verification

### Health Checks
- Application responds correctly
- Database connections working
- External services accessible
- Logs show no errors

### Monitoring
- Metrics within normal ranges
- No spike in error rates
- Performance acceptable
- Resource usage normal

### Smoke Tests
- Critical paths working
- User flows functional
- Integrations operational

## Rollback Procedure

If issues detected:

1. **Assess**: Determine severity
2. **Rollback**: Revert to previous version
3. **Restore**: Fix data if needed
4. **Notify**: Inform stakeholders
5. **Document**: Post-mortem analysis

## Examples

```
/deploy production
/deploy staging --strategy blue-green
/deploy dev
```

## Safety Rules

1. Never deploy without tests passing
2. Always have a rollback plan
3. Deploy during low-traffic periods
4. Monitor continuously during deployment
5. Communicate proactively with stakeholders

## Integration

This command uses the Bahram main agent with the deploy skill. For code review before deployment, use the `/review` command first.
