# Enhanced Car/Class Restrictions System Implementation Plan

## Overview
Comprehensive enhancement of the car and class restrictions system to properly handle simulator-specific car class data, multi-class events, and BOP restrictions from APIs like iRacing.

## Current State Analysis

### Existing Models ✅
- **`CarClass`**: Basic car class model (limited)
- **`CarModel`**: Car models with basic categorization
- **`SimCar`**: Simulator-specific car instances
- **`EventClass`**: Event-specific classes with `allowed_sim_car_ids` JSONField
- **`CarRestriction`**: BOP restrictions per car per race week
- **`Series`**: Has `multiclass` boolean flag

### Current Limitations ❌
1. **Limited CarClass Model**: No simulator-specific car class IDs
2. **No Multi-Class Grouping**: Events can't properly group cars by class
3. **Manual Car Selection**: No API-driven car class population
4. **Limited BOP Storage**: Missing setup IDs and advanced restrictions
5. **No Series-Level Restrictions**: Can't inherit restrictions from series
6. **Poor UI Integration**: Car/class restrictions not visible in signup flow

## API Data Analysis

### iRacing Series API Structure
```json
{
  "car_class_ids": [2708],
  "car_types": [{"car_type": "gt3"}, {"car_type": "road"}],
  "multiclass": false,
  "schedules": [
    {
      "car_restrictions": [
        {
          "car_id": 132,
          "max_dry_tire_sets": 0,
          "max_pct_fuel_fill": 50,
          "power_adjust_pct": -1.75,
          "race_setup_id": 265755,
          "qual_setup_id": 263880,
          "weight_penalty_kg": 5
        }
      ],
      "race_week_cars": [],
      "race_week_car_class_ids": []
    }
  ]
}
```

### iRacing Car Classes API Structure
```json
[
  {
    "car_class_id": 2708,
    "name": "GT3 Class",
    "short_name": "GT3 Class",
    "cars_in_class": [
      {"car_id": 156, "car_dirpath": "mercedesamgevogt3"},
      {"car_id": 188, "car_dirpath": "mclaren720sgt3"}
    ],
    "relative_speed": 52,
    "rain_enabled": true
  }
]
```

## Enhanced Data Model Design

### 1. Enhanced CarClass Model
```python
class CarClass(models.Model):
    # Existing fields
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=100)
    slug = models.SlugField(max_length=120, blank=True)
    category = models.CharField(max_length=100, blank=True)
    description = models.TextField(blank=True)
    icon_url = models.URLField(blank=True)
    
    # NEW: Simulator-specific fields
    simulator = models.ForeignKey(
        Simulator,
        on_delete=models.CASCADE,
        related_name="car_classes",
        null=True,
        blank=True,
        help_text="Simulator this class belongs to (null for generic)"
    )
    external_class_id = models.CharField(
        max_length=50,
        blank=True,
        help_text="Car class ID from simulator API"
    )
    short_name = models.CharField(
        max_length=50,
        blank=True,
        help_text="Short name from simulator API"
    )
    relative_speed = models.IntegerField(
        null=True,
        blank=True,
        help_text="Relative speed rating from simulator"
    )
    rain_enabled = models.BooleanField(
        default=False,
        help_text="Whether this class supports rain racing"
    )
    
    class Meta:
        unique_together = [
            ['simulator', 'external_class_id'],  # Unique per simulator
            ['name', 'simulator']  # Unique name per simulator
        ]
```

### 2. Enhanced CarRestriction Model
```python
class CarRestriction(models.Model):
    # Existing fields
    race_week = models.ForeignKey(RaceWeek, on_delete=models.CASCADE)
    sim_car = models.ForeignKey(SimCar, on_delete=models.CASCADE)
    max_dry_tire_sets = models.IntegerField(default=0)
    max_pct_fuel_fill = models.IntegerField(default=100)
    power_adjust_pct = models.FloatField(default=0)  # Changed to FloatField
    weight_penalty_kg = models.IntegerField(default=0)
    
    # NEW: Setup restrictions
    race_setup_id = models.CharField(
        max_length=50,
        blank=True,
        help_text="Fixed race setup ID from simulator"
    )
    qual_setup_id = models.CharField(
        max_length=50,
        blank=True,
        help_text="Fixed qualifying setup ID from simulator"
    )
    
    # NEW: Additional restrictions (stored as JSON for flexibility)
    additional_restrictions = models.JSONField(
        null=True,
        blank=True,
        help_text="Additional simulator-specific restrictions"
    )
```

### 3. New SeriesCarClass Model
```python
class SeriesCarClass(models.Model):
    """Links series to allowed car classes with ordering for multi-class events"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    series = models.ForeignKey(Series, on_delete=models.CASCADE, related_name="allowed_classes")
    car_class = models.ForeignKey(CarClass, on_delete=models.CASCADE, related_name="series_usage")
    
    # Multi-class ordering and grouping
    class_order = models.IntegerField(
        default=0,
        help_text="Order for multi-class events (0=fastest class)"
    )
    is_primary_class = models.BooleanField(
        default=True,
        help_text="Whether this is a primary class for the series"
    )
    
    # Class-specific settings
    min_entries = models.IntegerField(
        null=True,
        blank=True,
        help_text="Minimum entries needed for this class"
    )
    max_entries = models.IntegerField(
        null=True,
        blank=True,
        help_text="Maximum entries allowed for this class"
    )
    
    class Meta:
        unique_together = ['series', 'car_class']
        ordering = ['class_order', 'car_class__name']
```

### 4. Enhanced EventClass Model
```python
class EventClass(models.Model):
    # Existing fields
    event = models.ForeignKey(Event, on_delete=models.CASCADE, related_name="classes")
    name = models.CharField(max_length=255)
    slug = models.SlugField(max_length=280, blank=True)
    car_class = models.ForeignKey(CarClass, on_delete=models.SET_NULL, null=True, blank=True)
    
    # ENHANCED: Better car restrictions
    allowed_sim_cars = models.ManyToManyField(
        SimCar,
        blank=True,
        related_name="event_classes",
        help_text="Specific cars allowed in this class"
    )
    # Keep JSONField as backup/override
    allowed_sim_car_ids = models.JSONField(null=True, blank=True)
    
    # NEW: Class-specific settings
    class_order = models.IntegerField(
        default=0,
        help_text="Order for multi-class display (0=fastest)"
    )
    min_entries = models.IntegerField(
        null=True,
        blank=True,
        help_text="Minimum entries for this class"
    )
    max_entries = models.IntegerField(
        null=True,
        blank=True,
        help_text="Maximum entries for this class"
    )
    entry_fee = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="Entry fee for this class"
    )
    
    # Enhanced BOP
    bop_overrides = models.JSONField(null=True, blank=True)
    inherit_series_restrictions = models.BooleanField(
        default=True,
        help_text="Whether to inherit BOP from series/race week"
    )
```

## Implementation Plan

### Phase 1: Data Model Enhancements (2-3 days)

#### 1.1 Model Updates
- [ ] Add new fields to `CarClass` model
- [ ] Create `SeriesCarClass` model
- [ ] Enhance `CarRestriction` model
- [ ] Enhance `EventClass` model
- [ ] Create database migrations

#### 1.2 Data Import Enhancements
- [ ] Update iRacing car class import to populate new fields
- [ ] Create management command to sync car classes from API
- [ ] Update series import to create `SeriesCarClass` relationships
- [ ] Enhance car restriction import with new fields

### Phase 2: API Integration (2-3 days)

#### 2.1 Car Class API Integration
```python
def import_car_classes_from_api(simulator):
    """Import car classes from simulator API"""
    # Fetch car classes from iRacing API
    # Create/update CarClass objects with external_class_id
    # Link cars to classes via CarModel.car_class
```

#### 2.2 Series Restriction Integration
```python
def import_series_restrictions(series_data, simulator):
    """Import series-level car class restrictions"""
    # Process car_class_ids from series data
    # Create SeriesCarClass relationships
    # Handle multiclass flag and ordering
```

#### 2.3 Enhanced Car Restriction Import
```python
def import_car_restrictions(schedule_data, race_week):
    """Import enhanced car restrictions with setup IDs"""
    # Process car_restrictions array
    # Include race_setup_id and qual_setup_id
    # Handle floating-point power adjustments
```

### Phase 3: Admin Interface (1-2 days)

#### 3.1 Enhanced Admin Views
- [ ] Car class management with simulator filtering
- [ ] Series car class configuration
- [ ] Visual car restriction management
- [ ] Bulk import tools for restrictions

#### 3.2 Management Commands
- [ ] `sync_car_classes` - Import from simulator APIs
- [ ] `apply_series_restrictions` - Apply series-level restrictions to events
- [ ] `validate_car_restrictions` - Check for conflicts/issues

### Phase 4: User Interface Enhancements (3-4 days)

#### 4.1 Event Detail Page Improvements
```html
<!-- Multi-class event display -->
<div class="event-classes">
  {% for event_class in event.classes.all %}
    <div class="class-section">
      <h3>{{ event_class.name }}</h3>
      <div class="allowed-cars">
        {% for car in event_class.get_allowed_cars %}
          <div class="car-card">
            <!-- Car image, name, BOP restrictions -->
          </div>
        {% endfor %}
      </div>
    </div>
  {% endfor %}
</div>
```

#### 4.2 Enhanced Signup Form
```html
<!-- Class-based car selection -->
<div class="car-selection">
  {% if event.is_multiclass %}
    <!-- Show classes first, then cars within each class -->
    {% for event_class in event.classes.all %}
      <div class="class-group">
        <h4>{{ event_class.name }}</h4>
        <div class="car-options">
          {% for car in event_class.get_allowed_cars %}
            <label class="car-option">
              <input type="radio" name="preferred_car" value="{{ car.id }}">
              <div class="car-info">
                <img src="{{ car.small_image.url }}" alt="{{ car.display_name }}">
                <span>{{ car.display_name }}</span>
                {% if car.has_bop_restrictions %}
                  <div class="bop-info">
                    <!-- Show BOP restrictions -->
                  </div>
                {% endif %}
              </div>
            </label>
          {% endfor %}
        </div>
      </div>
    {% endfor %}
  {% else %}
    <!-- Single class - show cars directly -->
  {% endif %}
</div>
```

#### 4.3 Car Ownership Integration
```python
def get_user_available_cars(user, event):
    """Get cars user owns that are allowed for this event"""
    user_cars = get_user_owned_cars(user, event.simulator)
    allowed_cars = event.get_allowed_cars()
    return user_cars.intersection(allowed_cars)
```

### Phase 5: Business Logic Enhancements (2-3 days)

#### 5.1 Car Restriction Validation
```python
class EventClass:
    def get_allowed_cars(self):
        """Get all cars allowed in this class"""
        if self.allowed_sim_cars.exists():
            return self.allowed_sim_cars.all()
        elif self.car_class:
            return self.car_class.get_cars_for_simulator(self.event.simulator)
        return SimCar.objects.none()
    
    def get_bop_restrictions(self, race_week=None):
        """Get BOP restrictions for this class"""
        # Combine series, race week, and event-specific restrictions
        
    def can_user_select_car(self, user, car):
        """Check if user can select a specific car"""
        # Check ownership, restrictions, etc.
```

#### 5.2 Multi-Class Event Logic
```python
class Event:
    @property
    def is_multiclass(self):
        return self.classes.count() > 1
    
    def get_class_for_car(self, car):
        """Get the event class that allows this car"""
        
    def validate_entry_distribution(self):
        """Validate min/max entries per class"""
```

### Phase 6: Signup Flow Integration (2-3 days)

#### 6.1 Enhanced User Signup Form
```python
class UserEventSignupForm(forms.ModelForm):
    # Class selection (for multi-class events)
    preferred_class = forms.ModelChoiceField(
        queryset=EventClass.objects.none(),
        required=False,
        help_text="Choose your preferred class"
    )
    
    # Car selection (filtered by class and ownership)
    preferred_car = forms.ModelChoiceField(
        queryset=SimCar.objects.none(),
        help_text="Choose your preferred car"
    )
    
    def __init__(self, *args, **kwargs):
        self.event = kwargs.pop('event')
        self.user = kwargs.pop('user')
        super().__init__(*args, **kwargs)
        
        # Set up class choices
        self.fields['preferred_class'].queryset = self.event.classes.all()
        
        # Set up car choices based on ownership and event restrictions
        available_cars = self.get_available_cars()
        self.fields['preferred_car'].queryset = available_cars
    
    def get_available_cars(self):
        """Get cars user can select for this event"""
        # Filter by event restrictions and user ownership
```

#### 6.2 Real-time Car Filtering
```javascript
// HTMX-powered car filtering based on class selection
function updateCarChoices(classId) {
    htmx.ajax('GET', `/events/${eventId}/cars/?class=${classId}`, {
        target: '#car-selection',
        swap: 'innerHTML'
    });
}
```

### Phase 7: Advanced Features (Optional - 1-2 days)

#### 7.1 BOP Visualization
- [ ] Visual BOP comparison charts
- [ ] Performance impact indicators
- [ ] Historical BOP change tracking

#### 7.2 Car Recommendation System
- [ ] Suggest cars based on user skill level
- [ ] Recommend based on owned cars
- [ ] Class balance recommendations

#### 7.3 Restriction Conflict Detection
- [ ] Detect conflicting restrictions
- [ ] Warn about missing car ownership
- [ ] Validate setup availability

## Success Criteria

### Functional Requirements ✅
1. **Multi-class Support**: Events can have multiple classes with proper grouping
2. **API Integration**: Car classes and restrictions imported from simulator APIs
3. **Enhanced BOP**: Complete BOP data including setup IDs and advanced restrictions
4. **User-friendly Selection**: Intuitive car/class selection in signup forms
5. **Ownership Integration**: Only show cars users actually own
6. **Validation**: Comprehensive validation of restrictions and requirements

### Technical Requirements ✅
1. **Generic Design**: Works across multiple simulators (not iRacing-specific)
2. **Performance**: Efficient queries for car/class filtering
3. **Scalability**: Handles large numbers of cars and classes
4. **Maintainability**: Clean separation of concerns
5. **Extensibility**: Easy to add new restriction types

### User Experience Requirements ✅
1. **Clear Visualization**: Easy to understand car/class restrictions
2. **Smart Defaults**: Intelligent car recommendations
3. **Real-time Feedback**: Immediate validation and filtering
4. **Mobile Friendly**: Works well on all device sizes
5. **Accessibility**: Meets accessibility standards

## Migration Strategy

### Database Migration
1. **Phase 1**: Add new fields with defaults
2. **Phase 2**: Migrate existing data
3. **Phase 3**: Add constraints and indexes
4. **Phase 4**: Remove deprecated fields

### Data Migration
1. **Import car classes** from simulator APIs
2. **Link existing cars** to proper classes
3. **Migrate existing restrictions** to new format
4. **Create series-class relationships**

### Rollback Plan
- Keep existing JSONField as backup
- Gradual migration with feature flags
- Ability to fall back to old system

## Timeline and Resources

### Total Estimated Time: 12-16 days

**Phase 1**: Data Models (2-3 days)
**Phase 2**: API Integration (2-3 days)  
**Phase 3**: Admin Interface (1-2 days)
**Phase 4**: UI Enhancements (3-4 days)
**Phase 5**: Business Logic (2-3 days)
**Phase 6**: Signup Integration (2-3 days)
**Phase 7**: Advanced Features (1-2 days, optional)

### Dependencies
- Access to simulator APIs (iRacing car classes API)
- Updated car and series data
- HTMX for dynamic UI interactions
- Django formsets for complex forms

### Risk Mitigation
- **API Changes**: Generic design to handle API variations
- **Data Integrity**: Comprehensive validation and migration scripts
- **Performance**: Proper indexing and query optimization
- **User Experience**: Progressive enhancement and fallbacks

This enhanced system will provide a robust, scalable foundation for car and class restrictions that works across multiple simulators while providing an excellent user experience for event signup and management. 