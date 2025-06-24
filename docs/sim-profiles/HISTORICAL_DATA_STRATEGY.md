# Sim Profiles Historical Data Strategy

## Overview

This document analyzes the current data models for tracking historical profile data and provides recommendations for implementing rating progression charts and other historical analytics.

## Current State Analysis

### Existing Historical Data Models

#### 1. **ProfileRating Model** ✅ **PERFECT for Historical Ratings**
```python
class ProfileRating(models.Model):
    sim_profile = models.ForeignKey(SimProfile, on_delete=models.CASCADE, related_name="ratings")
    rating_system = models.ForeignKey(RatingSystem, on_delete=models.CASCADE)
    discipline = models.CharField(max_length=20, choices=RacingDiscipline, blank=True)
    value = models.FloatField()
    recorded_at = models.DateTimeField(auto_now_add=True)  # 🎯 KEY: Automatic timestamping
```

**✅ This model is ALREADY PERFECT for historical rating tracking!**

#### 2. **RatingSystem Model** ✅ **Defines Rating Types**
```python
class RatingSystem(models.Model):
    simulator = models.ForeignKey(Simulator, on_delete=models.CASCADE)
    code = models.CharField(max_length=10)         # "IRATING", "SAFETY", "LICENSE"
    name = models.CharField(max_length=255)        # "iRating", "Safety Rating", "License Class"
    category = models.CharField(max_length=20, choices=RatingCategory)  # SKILL, SAFETY, etc.
    min_value = models.FloatField(null=True)       # e.g., 0
    max_value = models.FloatField(null=True)       # e.g., 10000
```

#### 3. **LapTime Model** ✅ **Has Rating Snapshots**
```python
class LapTime(models.Model):
    sim_profile = models.ForeignKey(SimProfile, on_delete=models.CASCADE)
    rating_at_time = models.FloatField(null=True, blank=True)  # 🎯 Rating when lap was recorded
    recorded_at = models.DateTimeField(auto_now_add=True)
```

## Historical Data Capabilities Assessment

### ✅ **EXISTING CAPABILITIES (Already Implemented)**

#### **Rating History Tracking**
```python
# Get iRating history for a profile
iracing_system = RatingSystem.objects.get(simulator__name="iRacing", code="IRATING")
rating_history = ProfileRating.objects.filter(
    sim_profile=profile,
    rating_system=iracing_system,
    discipline="ROAD"
).order_by('recorded_at')

# Get safety rating history
safety_system = RatingSystem.objects.get(simulator__name="iRacing", code="SAFETY")
safety_history = ProfileRating.objects.filter(
    sim_profile=profile,
    rating_system=safety_system,
    discipline="ROAD"
).order_by('recorded_at')
```

#### **Multi-Discipline Tracking**
```python
# Track different disciplines separately
road_ratings = profile.ratings.filter(discipline="ROAD").order_by('recorded_at')
oval_ratings = profile.ratings.filter(discipline="OVAL").order_by('recorded_at')
```

#### **Performance Over Time**
```python
# Lap time performance with rating context
lap_times_with_rating = LapTime.objects.filter(
    sim_profile=profile
).select_related('sim_layout').order_by('recorded_at')

# Can correlate lap performance with rating progression
```

### ❌ **MISSING CAPABILITIES (Need Implementation)**

#### **Automatic Rating Updates**
```python
# Need service to regularly update ratings from platform APIs
class ProfileRatingService:
    def update_ratings_from_api(self, sim_profile):
        """Fetch latest ratings from platform API and record historical entry"""
        # Implementation needed
```

#### **Rating Change Events**
```python
# Track significant rating changes and their triggers
class RatingChangeEvent(models.Model):
    sim_profile = models.ForeignKey(SimProfile, on_delete=models.CASCADE)
    rating_system = models.ForeignKey(RatingSystem, on_delete=models.CASCADE)
    old_value = models.FloatField()
    new_value = models.FloatField()
    change_amount = models.FloatField()  # new_value - old_value
    change_date = models.DateTimeField()
    trigger_event = models.CharField(max_length=50)  # "race_finish", "api_update", "manual"
    event_details = models.JSONField(null=True, blank=True)  # Race details, etc.
```

## Implementation Strategy

### Phase 1: Leverage Existing Models (Immediate Implementation)

#### **Setup Rating Systems**
```python
# Management command to create standard rating systems
def create_iracing_rating_systems():
    simulator = Simulator.objects.get(name="iRacing")
    
    # iRating system
    irating_system, created = RatingSystem.objects.get_or_create(
        simulator=simulator,
        code="IRATING",
        defaults={
            "name": "iRating",
            "category": RatingCategory.SKILL,
            "min_value": 0,
            "max_value": 10000,
            "description": "iRacing skill rating system"
        }
    )
    
    # Safety Rating system
    safety_system, created = RatingSystem.objects.get_or_create(
        simulator=simulator,
        code="SAFETY",
        defaults={
            "name": "Safety Rating",
            "category": RatingCategory.SAFETY,
            "min_value": 0.0,
            "max_value": 5.0,
            "description": "iRacing safety rating (0.00 - 5.00)"
        }
    )
    
    # License Class system
    license_system, created = RatingSystem.objects.get_or_create(
        simulator=simulator,
        code="LICENSE",
        defaults={
            "name": "License Class",
            "category": RatingCategory.OTHER,
            "min_value": 1,
            "max_value": 5,
            "description": "iRacing license class (R=1, D=2, C=3, B=4, A=5)"
        }
    )
```

#### **Historical Data Collection Service**
```python
# simlane/sim/services.py
class ProfileHistoryService:
    
    @staticmethod
    def record_rating_update(sim_profile, rating_system, discipline, new_value):
        """Record a new rating entry for historical tracking"""
        ProfileRating.objects.create(
            sim_profile=sim_profile,
            rating_system=rating_system,
            discipline=discipline,
            value=new_value,
            # recorded_at is auto-set
        )
    
    @staticmethod
    def get_rating_history(sim_profile, rating_code, discipline=None, days=365):
        """Get rating history for charts"""
        rating_system = RatingSystem.objects.get(
            simulator=sim_profile.simulator,
            code=rating_code
        )
        
        cutoff_date = timezone.now() - timedelta(days=days)
        
        queryset = ProfileRating.objects.filter(
            sim_profile=sim_profile,
            rating_system=rating_system,
            recorded_at__gte=cutoff_date
        )
        
        if discipline:
            queryset = queryset.filter(discipline=discipline)
        
        return queryset.order_by('recorded_at').values(
            'value', 'recorded_at', 'discipline'
        )
    
    @staticmethod
    def get_rating_trend(sim_profile, rating_code, discipline=None, days=30):
        """Get recent rating trend (up/down/stable)"""
        history = ProfileHistoryService.get_rating_history(
            sim_profile, rating_code, discipline, days
        )
        
        if len(history) < 2:
            return "insufficient_data"
        
        first_rating = history[0]['value']
        last_rating = history[-1]['value']
        change = last_rating - first_rating
        
        if abs(change) < 50:  # Configurable threshold
            return "stable"
        elif change > 0:
            return "improving"
        else:
            return "declining"
```

#### **Chart Data API Endpoints**
```python
# simlane/api/routers/sim.py
@router.get("/profiles/{profile_id}/rating-history/{rating_code}")
def get_rating_history(
    profile_id: str,
    rating_code: str,
    discipline: str = None,
    days: int = 365
):
    """Get rating history data for charts"""
    sim_profile = get_object_or_404(SimProfile, id=profile_id)
    
    history = ProfileHistoryService.get_rating_history(
        sim_profile, rating_code, discipline, days
    )
    
    return {
        "profile_id": profile_id,
        "rating_code": rating_code,
        "discipline": discipline,
        "data_points": list(history),
        "trend": ProfileHistoryService.get_rating_trend(
            sim_profile, rating_code, discipline, 30
        )
    }
```

### Phase 2: Enhanced Historical Tracking (Future Implementation)

#### **Rating Change Events Model**
```python
class RatingChangeEvent(models.Model):
    """Track significant rating changes and their causes"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    sim_profile = models.ForeignKey(SimProfile, on_delete=models.CASCADE, related_name="rating_changes")
    rating_system = models.ForeignKey(RatingSystem, on_delete=models.CASCADE)
    discipline = models.CharField(max_length=20, choices=RacingDiscipline, blank=True)
    
    # Change details
    old_value = models.FloatField()
    new_value = models.FloatField()
    change_amount = models.FloatField()  # Calculated: new_value - old_value
    change_percentage = models.FloatField(null=True, blank=True)
    
    # Change context
    change_date = models.DateTimeField()
    trigger_event = models.CharField(max_length=50)  # "race_finish", "api_sync", "manual_update"
    event_reference = models.CharField(max_length=255, blank=True)  # Event ID, race session, etc.
    
    # Additional context
    context_data = models.JSONField(null=True, blank=True)  # Race details, finishing position, etc.
    is_significant = models.BooleanField(default=False)  # Large changes (>100 iRating, >0.1 SR)
    
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        indexes = [
            models.Index(fields=['sim_profile', 'rating_system', 'change_date']),
            models.Index(fields=['change_date']),
            models.Index(fields=['is_significant']),
        ]
        
    def save(self, *args, **kwargs):
        # Calculate derived fields
        self.change_amount = self.new_value - self.old_value
        if self.old_value != 0:
            self.change_percentage = (self.change_amount / self.old_value) * 100
        
        # Determine if change is significant
        self.is_significant = self._is_significant_change()
        super().save(*args, **kwargs)
    
    def _is_significant_change(self):
        """Determine if this is a significant rating change"""
        if self.rating_system.code == "IRATING":
            return abs(self.change_amount) >= 100
        elif self.rating_system.code == "SAFETY":
            return abs(self.change_amount) >= 0.1
        elif self.rating_system.code == "LICENSE":
            return abs(self.change_amount) >= 1
        return False
```

#### **Performance Milestone Tracking**
```python
class PerformanceMilestone(models.Model):
    """Track significant achievements and milestones"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    sim_profile = models.ForeignKey(SimProfile, on_delete=models.CASCADE, related_name="milestones")
    milestone_type = models.CharField(max_length=50)  # "rating_peak", "license_promotion", "first_win"
    milestone_value = models.FloatField(null=True, blank=True)
    milestone_data = models.JSONField(null=True, blank=True)
    achieved_at = models.DateTimeField()
    created_at = models.DateTimeField(auto_now_add=True)
```

### Phase 3: Advanced Analytics (Long-term)

#### **Rating Progression Analytics**
```python
class RatingProgressionAnalytics:
    
    @staticmethod
    def calculate_progression_rate(sim_profile, rating_code, discipline=None):
        """Calculate average rating improvement per month"""
        history = ProfileHistoryService.get_rating_history(
            sim_profile, rating_code, discipline, days=365
        )
        
        if len(history) < 2:
            return None
        
        first_entry = history[0]
        last_entry = history[-1]
        
        time_diff = last_entry['recorded_at'] - first_entry['recorded_at']
        rating_diff = last_entry['value'] - first_entry['value']
        
        months = time_diff.days / 30.44  # Average days per month
        return rating_diff / months if months > 0 else 0
    
    @staticmethod
    def find_rating_peaks_and_valleys(sim_profile, rating_code, discipline=None):
        """Identify significant peaks and valleys in rating history"""
        history = list(ProfileHistoryService.get_rating_history(
            sim_profile, rating_code, discipline, days=365
        ))
        
        if len(history) < 3:
            return {"peaks": [], "valleys": []}
        
        peaks = []
        valleys = []
        
        for i in range(1, len(history) - 1):
            current = history[i]['value']
            prev_val = history[i-1]['value']
            next_val = history[i+1]['value']
            
            # Peak detection
            if current > prev_val and current > next_val:
                peaks.append({
                    "date": history[i]['recorded_at'],
                    "value": current,
                    "significance": current - min(prev_val, next_val)
                })
            
            # Valley detection
            elif current < prev_val and current < next_val:
                valleys.append({
                    "date": history[i]['recorded_at'],
                    "value": current,
                    "significance": max(prev_val, next_val) - current
                })
        
        return {"peaks": peaks, "valleys": valleys}
```

## Chart Implementation Examples

### Frontend Chart Data Structure
```javascript
// Rating history chart data format
const ratingHistoryData = {
    labels: ['2024-01-01', '2024-01-15', '2024-02-01', ...],  // Dates
    datasets: [
        {
            label: 'Road iRating',
            data: [1450, 1475, 1423, 1501, ...],  // Rating values
            borderColor: 'rgb(75, 192, 192)',
            tension: 0.1
        },
        {
            label: 'Road Safety Rating',
            data: [3.45, 3.48, 3.42, 3.51, ...],  // Safety rating values
            borderColor: 'rgb(255, 99, 132)',
            tension: 0.1,
            yAxisID: 'y1'  // Secondary Y-axis for different scale
        }
    ]
};

// Multi-discipline comparison
const disciplineComparisonData = {
    labels: ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun'],
    datasets: [
        {
            label: 'Road iRating',
            data: [1450, 1475, 1501, 1520, 1485, 1512],
            borderColor: 'rgb(75, 192, 192)'
        },
        {
            label: 'Oval iRating',
            data: [1200, 1215, 1195, 1220, 1240, 1235],
            borderColor: 'rgb(54, 162, 235)'
        }
    ]
};
```

### Django Template Integration
```html
<!-- Profile rating charts -->
<div class="grid grid-cols-1 lg:grid-cols-2 gap-6 mb-8">
    <!-- iRating History -->
    <div class="bg-white dark:bg-gray-800 rounded-lg shadow p-6">
        <h3 class="text-lg font-medium mb-4">iRating Progress</h3>
        <canvas id="irating-chart" width="400" height="200"></canvas>
    </div>
    
    <!-- Safety Rating History -->
    <div class="bg-white dark:bg-gray-800 rounded-lg shadow p-6">
        <h3 class="text-lg font-medium mb-4">Safety Rating Progress</h3>
        <canvas id="safety-chart" width="400" height="200"></canvas>
    </div>
</div>

<script>
// Fetch and display rating history
fetch(`/api/profiles/{{ profile.id }}/rating-history/IRATING?discipline=ROAD&days=365`)
    .then(response => response.json())
    .then(data => {
        renderRatingChart('irating-chart', data.data_points, 'iRating');
    });
</script>
```

## Conclusion

### ✅ **EXISTING MODELS ARE SUFFICIENT**

The current `ProfileRating` model is **already perfectly designed** for historical rating tracking:

1. **Automatic timestamping** with `recorded_at`
2. **Multi-rating system support** via `RatingSystem` FK
3. **Multi-discipline tracking** via `discipline` field
4. **Optimized indexes** for historical queries
5. **Flexible value storage** for any rating type

### 🚀 **IMMEDIATE IMPLEMENTATION PATH**

1. **Create rating systems** for iRacing (iRating, Safety Rating, License)
2. **Build collection service** to record rating updates
3. **Create API endpoints** for chart data
4. **Implement frontend charts** using existing data

### 📈 **FUTURE ENHANCEMENTS**

1. **Rating change events** for detailed change tracking
2. **Performance milestones** for achievement tracking
3. **Advanced analytics** for progression insights
4. **Automated data collection** from platform APIs

**The existing data model requires NO changes** - it's already perfectly suited for comprehensive historical rating tracking and chart generation! 