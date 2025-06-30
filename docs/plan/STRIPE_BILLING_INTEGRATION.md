# Stripe Billing Integration Plan

## Overview

This document outlines the comprehensive plan for integrating Stripe billing into the SimLane Django application. The integration will introduce subscription-based pricing tiers that gate access to premium features, particularly race planning functionality, while maintaining the existing club management structure.

## Subscription Tier Structure

### Free Tier
- **Price**: $0/month
- **Member Limit**: 5 members per club
- **Features**:
  - Basic club management
  - Event browsing and participation
  - Basic member management
  - iRacing integration
- **Restrictions**:
  - No race planning features
  - No team formation for events
  - No strategy planning tools

### Basic Tier
- **Price**: $9.99/month
- **Member Limit**: 25 members per club
- **Features**:
  - All Free tier features
  - Race planning and strategy tools
  - Team formation for events
  - Stint planning
  - Basic analytics
- **Target Audience**: Small to medium racing clubs

### Pro Tier
- **Price**: $29.99/month
- **Member Limit**: Unlimited members
- **Features**:
  - All Basic tier features
  - Advanced analytics and reporting
  - Priority support
  - Custom integrations (future)
  - Advanced team management tools
- **Target Audience**: Large racing organizations and professional teams

## Feature Gating Strategy

### Race Planning Features
The following features will be gated behind paid subscriptions (Basic and Pro tiers):

1. **EventParticipation Team Formation**
   - Creating and managing teams for events
   - Assigning drivers to specific roles
   - Team strategy coordination

2. **RaceStrategy Management**
   - Creating race strategies
   - Editing strategy parameters
   - Sharing strategies with team members

3. **StintPlan Operations**
   - Creating stint plans
   - Driver rotation planning
   - Fuel and tire strategy planning

### Member Limit Enforcement
- Free tier clubs cannot exceed 5 active members
- Basic tier clubs cannot exceed 25 active members
- Pro tier clubs have unlimited members
- Existing members are grandfathered during plan downgrades
- New member invitations are blocked when limits are reached

## Technical Architecture

### Core Models

#### SubscriptionPlan
```python
class SubscriptionPlan(models.Model):
    name = models.CharField(max_length=50)  # Free, Basic, Pro
    stripe_price_id = models.CharField(max_length=100, unique=True)
    max_members = models.IntegerField(null=True, blank=True)  # None for unlimited
    monthly_price = models.DecimalField(max_digits=10, decimal_places=2)
    features_json = models.JSONField(default=dict)  # Feature flags
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
```

#### ClubSubscription
```python
class ClubSubscription(models.Model):
    club = models.OneToOneField('teams.Club', on_delete=models.CASCADE)
    plan = models.ForeignKey(SubscriptionPlan, on_delete=models.PROTECT)
    stripe_customer_id = models.CharField(max_length=100, unique=True)
    stripe_subscription_id = models.CharField(max_length=100, null=True, blank=True)
    status = models.CharField(max_length=20, choices=SUBSCRIPTION_STATUS_CHOICES)
    current_period_start = models.DateTimeField(null=True, blank=True)
    current_period_end = models.DateTimeField(null=True, blank=True)
    seats_used = models.IntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
```

#### BillingEventLog
```python
class BillingEventLog(models.Model):
    stripe_event_id = models.CharField(max_length=100, unique=True)
    event_type = models.CharField(max_length=50)
    club_subscription = models.ForeignKey(ClubSubscription, on_delete=models.CASCADE, null=True)
    processed_at = models.DateTimeField(auto_now_add=True)
    data_json = models.JSONField()
    processing_status = models.CharField(max_length=20, default='pending')
```

### Service Layer Architecture

#### StripeService
Handles all Stripe API interactions:
- Customer creation and management
- Checkout session creation
- Subscription lifecycle management
- Webhook event processing
- Payment method management

#### SubscriptionService
Manages subscription business logic:
- Subscription status validation
- Feature access checking
- Member limit enforcement
- Plan upgrade/downgrade logic
- Usage calculation and reporting

### Webhook Handling

#### Supported Webhook Events
- `customer.subscription.created`
- `customer.subscription.updated`
- `customer.subscription.deleted`
- `invoice.payment_succeeded`
- `invoice.payment_failed`
- `customer.subscription.trial_will_end`

#### Webhook Security
- Stripe signature verification using webhook secret
- Idempotency handling using event IDs
- Comprehensive logging of all webhook events
- Retry mechanism for failed webhook processing

#### Webhook Processing Flow
1. Verify Stripe signature
2. Check for duplicate event processing
3. Parse webhook payload
4. Update local subscription status
5. Trigger relevant Django signals
6. Log processing results

## API Design

### Subscription Management Endpoints

#### GET /api/clubs/{club_slug}/subscription/
Returns current subscription details:
```json
{
  "plan": {
    "name": "Basic",
    "max_members": 25,
    "monthly_price": "9.99",
    "features": ["race_planning", "team_formation"]
  },
  "status": "active",
  "current_period_end": "2024-02-01T00:00:00Z",
  "seats_used": 12,
  "seats_available": 13
}
```

#### POST /api/clubs/{club_slug}/subscription/checkout/
Creates Stripe checkout session:
```json
{
  "price_id": "price_1234567890",
  "success_url": "https://app.simlane.com/billing/success",
  "cancel_url": "https://app.simlane.com/billing/cancel"
}
```

#### POST /api/clubs/{club_slug}/subscription/portal/
Creates Stripe customer portal session for subscription management.

### Enhanced Club API Responses
All club API endpoints will include subscription context:
```json
{
  "id": 123,
  "name": "Racing Club",
  "subscription": {
    "plan_name": "Basic",
    "status": "active",
    "features_enabled": ["race_planning"],
    "member_limit_reached": false
  }
}
```

### Error Handling
- HTTP 402 Payment Required for subscription-gated features
- HTTP 403 Forbidden for member limit violations
- Detailed error messages with upgrade prompts
- Consistent error response format across all endpoints

## Security Considerations

### Stripe Integration Security
- Webhook endpoint protection with signature verification
- Secure storage of Stripe keys in environment variables
- PCI compliance through Stripe's hosted checkout
- No storage of payment card data on SimLane servers

### Access Control
- Subscription checks integrated with existing permission system
- Feature flags validated on both frontend and backend
- API rate limiting for billing endpoints
- Audit logging for all subscription changes

### Data Protection
- Encryption of sensitive billing data at rest
- Secure transmission of all payment-related data
- GDPR compliance for billing information
- Data retention policies for billing events

## Implementation Phases

### Phase 1: Foundation (Week 1-2)
- Create billing Django app structure
- Implement core models and migrations
- Set up Stripe SDK integration
- Create basic admin interfaces
- Implement subscription service layer

### Phase 2: Core Billing Logic (Week 3-4)
- Implement subscription decorators
- Create checkout flow and webhook handling
- Add subscription status checking
- Implement member limit enforcement
- Create management commands for plan setup

### Phase 3: Feature Integration (Week 5-6)
- Gate race planning features behind subscriptions
- Update club management views with subscription checks
- Implement API endpoint modifications
- Add subscription status to templates
- Create billing dashboard interface

### Phase 4: UI/UX Enhancement (Week 7-8)
- Create subscription management templates
- Implement upgrade prompts and flows
- Add subscription widgets to club dashboard
- Create billing-related template tags
- Implement responsive billing interfaces

### Phase 5: Testing and Migration (Week 9-10)
- Comprehensive testing of all billing functionality
- Migration of existing clubs to Free tier
- Load testing of webhook endpoints
- Security audit of billing implementation
- Documentation and deployment preparation

## Testing Strategy

### Unit Testing
- Model method testing for subscription logic
- Service layer testing with mocked Stripe calls
- Decorator testing for subscription enforcement
- Template tag testing for billing functionality

### Integration Testing
- End-to-end checkout flow testing
- Webhook processing testing with Stripe CLI
- API endpoint testing with subscription scenarios
- Permission system integration testing

### Load Testing
- Webhook endpoint performance under load
- Subscription checking performance impact
- Database query optimization for billing queries
- Stripe API rate limit handling

### Security Testing
- Webhook signature verification testing
- Payment flow security audit
- Access control testing for billing features
- Data encryption and protection validation

## Migration Plan for Existing Clubs

### Pre-Migration Assessment
1. **Club Size Analysis**
   - Count current members for all existing clubs
   - Identify clubs exceeding Free tier limits (>5 members)
   - Generate migration impact report

2. **Feature Usage Analysis**
   - Identify clubs currently using race planning features
   - Assess impact of feature gating on existing users
   - Plan communication strategy for affected clubs

### Migration Strategy

#### Automatic Migration
- All existing clubs assigned to Free tier initially
- Clubs with ≤5 members: No immediate action required
- Clubs with >5 members: Grace period with feature access

#### Grace Period Implementation
- 30-day grace period for oversized clubs
- Full feature access maintained during grace period
- Progressive notifications about upcoming restrictions
- Easy upgrade path provided throughout grace period

#### Communication Plan
1. **Pre-Migration (2 weeks before)**
   - Email announcement to all club admins
   - In-app notifications about upcoming changes
   - FAQ and upgrade information provided

2. **During Migration**
   - Real-time migration status updates
   - Support team availability for questions
   - Immediate upgrade options for affected clubs

3. **Post-Migration**
   - Follow-up emails with upgrade incentives
   - Usage analytics and recommendations
   - Ongoing support for billing questions

### Rollback Procedures
- Database backup before migration execution
- Feature flag system for quick billing disable
- Rollback scripts for subscription assignments
- Emergency contact procedures for critical issues

## Monitoring and Analytics

### Key Metrics
- Subscription conversion rates by tier
- Member limit utilization across clubs
- Feature usage patterns by subscription tier
- Churn rates and upgrade/downgrade patterns

### Monitoring Setup
- Stripe webhook processing success rates
- Subscription status synchronization accuracy
- Performance impact of subscription checks
- Error rates for billing-related operations

### Alerting
- Failed webhook processing alerts
- Subscription synchronization failures
- High error rates on billing endpoints
- Unusual subscription activity patterns

## Future Enhancements

### Advanced Features
- Annual subscription discounts
- Team-based pricing for large organizations
- Custom enterprise plans
- Integration with additional payment providers

### Analytics and Reporting
- Advanced usage analytics dashboard
- Subscription revenue reporting
- Member engagement metrics by tier
- Predictive churn analysis

### API Enhancements
- GraphQL subscription queries
- Real-time subscription status updates
- Advanced filtering and search for billing data
- Webhook replay and debugging tools

## Success Criteria

### Technical Success Metrics
- 99.9% webhook processing success rate
- <100ms additional latency for subscription checks
- Zero payment data security incidents
- 100% test coverage for billing functionality

### Business Success Metrics
- 15% conversion rate from Free to paid tiers
- <5% monthly churn rate for paid subscriptions
- 90% customer satisfaction with billing experience
- 25% increase in average revenue per club

## Risk Mitigation

### Technical Risks
- **Stripe API downtime**: Implement graceful degradation and retry logic
- **Webhook processing failures**: Comprehensive error handling and manual reconciliation tools
- **Performance impact**: Optimize subscription checks and implement caching
- **Data synchronization issues**: Regular audit jobs and alerting systems

### Business Risks
- **User resistance to paid features**: Comprehensive communication and gradual rollout
- **Pricing sensitivity**: A/B testing of pricing tiers and promotional offers
- **Competition**: Unique value proposition and feature differentiation
- **Regulatory compliance**: Legal review of terms and privacy policies

This comprehensive plan provides the foundation for successfully integrating Stripe billing into SimLane while maintaining the existing user experience and ensuring scalable, secure payment processing.