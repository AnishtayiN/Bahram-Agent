---
name: deploy
description: "Deployment automation skill. Use when deploying applications, configuring infrastructure, or managing releases. Triggered by deployment requests, CI/CD tasks, or infrastructure changes."
---

# Deployment Skill

Automate deployment processes with safety and reliability.

## Deployment Process

### 1. Pre-Deployment Checks

#### Code Readiness
- [ ] All tests passing
- [ ] Code review completed
- [ ] Documentation updated
- [ ] Changelog updated

#### Environment Ready
- [ ] Infrastructure provisioned
- [ ] Secrets configured
- [ ] Dependencies available
- [ ] Monitoring enabled

#### Safety Measures
- [ ] Rollback plan documented
- [ ] Feature flags configured
- [ ] Alerts set up
- [ ] Communication sent

### 2. Deployment Strategy

Choose appropriate strategy:

#### Blue-Green Deployment
- Zero downtime
- Easy rollback
- Full environment swap

#### Rolling Deployment
- Gradual rollout
- Resource efficient
- Canary testing

#### Feature Flag Deployment
- Progressive delivery
- A/B testing capability
- Instant rollback

### 3. Execution

#### Build
```bash
# Example build commands
npm run build
docker build -t app:latest .
```

#### Test
```bash
# Run deployment tests
npm run test:e2e
docker-compose -f docker-compose.test.yml up
```

#### Deploy
```bash
# Example deployment commands
kubectl apply -f k8s/
docker-compose up -d
aws s3 sync ./dist s3://bucket/
```

### 4. Post-Deployment Verification

#### Health Checks
- Application responds correctly
- Database connections working
- External services accessible
- Logs show no errors

#### Monitoring
- Metrics within normal ranges
- No spike in error rates
- Performance acceptable
- Resource usage normal

#### Smoke Tests
- Critical paths working
- User flows functional
- Integrations operational

### 5. Rollback Procedure

If issues detected:

1. **Immediate Assessment**
   - Determine severity
   - Identify affected users
   - Check monitoring data

2. **Rollback Execution**
   - Revert to previous version
   - Restore database if needed
   - Clear caches
   - Notify stakeholders

3. **Post-Mortem**
   - Document what happened
   - Identify root cause
   - Implement fixes
   - Update procedures

## Deployment Checklist Template

### Pre-Deployment
```markdown
- [ ] Code complete and tested
- [ ] Review approved
- [ ] Documentation updated
- [ ] Changelog prepared
- [ ] Dependencies updated
- [ ] Environment configured
- [ ] Secrets verified
- [ ] Monitoring configured
- [ ] Alerts set up
- [ ] Rollback plan ready
```

### Deployment
```markdown
- [ ] Build successful
- [ ] Tests passing
- [ ] Deployment started
- [ ] Health checks passing
- [ ] Smoke tests passed
- [ ] Metrics normal
- [ ] No errors in logs
- [ ] Users notified
```

### Post-Deployment
```markdown
- [ ] All systems operational
- [ ] Performance acceptable
- [ ] Monitoring stable
- [ ] Documentation updated
- [ ] Team notified
- [ ] Celebrate success
```

## Environment-Specific Considerations

### Development
- Quick iteration
- Debugging enabled
- Mock services allowed

### Staging
- Production mirror
- Full test suite
- Performance testing

### Production
- Maximum safety
- Monitoring required
- Rollback tested

## Integration with Bahram

This skill works with the Bahram main agent for deployment automation. Deployments can be triggered via:
```bash
/opencode deploy <environment>
```

## Safety Rules

1. **Never deploy without tests passing**
2. **Always have a rollback plan**
3. **Deploy during low-traffic periods**
4. **Monitor continuously during deployment**
5. **Communicate proactively with stakeholders**
