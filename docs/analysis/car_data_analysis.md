# iRacing Car Data Analysis

## Current Problem
The existing car data loading script is creating duplicate names like "Acura Acura NSX GT3 EVO 22" because it's incorrectly mapping API fields. We're also throwing away valuable data and misusing the CarClass model for categories.

## iRacing API Car Data Structure
Based on analysis of the iRacing API response, here are all available fields grouped by purpose and priority:

---

## GROUP 1: CORE IDENTIFICATION & RELATIONSHIPS

### Fields for CarModel:
- `car_name` → **full_name** (e.g., "Skip Barber Formula 2000")
- `car_name_abbreviated` → **abbreviated_name** (e.g., "SBRS")  
- `car_make` → **manufacturer** (e.g., "Pontiac", "Modified")
- `car_model` → **name** (e.g., "Solstice", "SK")

### Fields for SimCar:
- `car_id` → **sim_api_id** (for API calls)
- `package_id` → **package_id** (for ownership tracking) ⚠️ **CRITICAL**

### Current Issue:
- We're using `car_name` as CarModel.name, but it's the full display name
- We need to extract manufacturer and model properly
- `package_id` is missing but essential for ownership tracking

---

## GROUP 2: CATEGORIZATION & CLASSIFICATION

### New CarCategory Model Needed:
- `categories` → Array like `["formula_car", "sports_car", "oval"]`
- These are broad groupings, NOT racing classes

### New CarType Model Needed:
- `car_types` → Array of objects like `[{"car_type": "openwheel"}, {"car_type": "road"}]`
- Cars can have multiple types (many-to-many relationship)

### CarClass (existing, but needs fixing):
- Should represent specific racing classes like "GT3", "LMP2", "Formula 3"
- Currently being misused for categories

---

## GROUP 3: TECHNICAL SPECIFICATIONS (High Priority)

### Performance Data:
- `hp` → **horsepower** (e.g., 132)
- `car_weight` → **weight_lbs** (e.g., 1250)
- `max_power_adjust_pct` → **max_power_adjust_pct** (e.g., 0)
- `min_power_adjust_pct` → **min_power_adjust_pct** (e.g., -5)
- `max_weight_penalty_kg` → **max_weight_penalty_kg** (e.g., 250)

### Capabilities:
- `has_headlights` → **has_headlights** (boolean)
- `has_multiple_dry_tire_types` → **has_multiple_dry_tire_types** (boolean)
- `has_rain_capable_tire_types` → **has_rain_capable_tire_types** (boolean)
- `rain_enabled` → **rain_enabled** (boolean)
- `ai_enabled` → **ai_enabled** (boolean)

---

## GROUP 4: PRICING & OWNERSHIP (High Priority)

### SimCar Fields:
- `price` → **price** (e.g., 11.95)
- `price_display` → **price_display** (e.g., "$11.95")
- `free_with_subscription` → **free_with_subscription** (boolean)
- `is_ps_purchasable` → **is_purchasable** (boolean)

### Current Issue:
- These fields are completely missing from our models
- Essential for showing pricing and purchase options to users

---

## GROUP 5: CUSTOMIZATION OPTIONS (Medium Priority)

### Paint & Visual Customization:
- `patterns` → **patterns_count** (e.g., 3)
- `allow_number_colors` → **allow_number_colors** (boolean)
- `allow_number_font` → **allow_number_font** (boolean)
- `allow_sponsor1` → **allow_sponsor1** (boolean)
- `allow_sponsor2` → **allow_sponsor2** (boolean)
- `allow_wheel_color` → **allow_wheel_color** (boolean)
- `paint_rules` → **paint_rules** (JSON object with complex rules)

---

## GROUP 6: MEDIA & CONTENT (Medium Priority)

### Images:
- `logo` → **logo_url** (e.g., "/img/logos/partners/skipbarber-logo.png")
- `small_image` → **small_image** (e.g., "skipbarberformula2000-small.jpg")
- `large_image` → **large_image** (e.g., "skipbarberformula2000-large.jpg")
- `gallery_images` → **gallery_images_count** (e.g., "8")
- `detail_screen_shot_images` → **screenshot_images** (comma-separated list)

### Content:
- `detail_copy` → **description_html** (rich HTML description)
- `detail_techspecs_copy` → **tech_specs_html** (technical specifications HTML)
- `forum_url` → **forum_url** (link to forums)
- `search_filters` → **search_filters** (e.g., "road,openwheel,skippy,sbrs,rt2000")

---

## GROUP 7: ADMINISTRATIVE DATA (Low Priority)

### Dates & Status:
- `created` → **created_date** (e.g., "2006-05-03T19:10:00Z")
- `first_sale` → **first_sale_date** (e.g., "2008-02-03T00:00:00Z")
- `retired` → **retired** (boolean)
- `award_exempt` → **award_exempt** (boolean)

### Administrative IDs:
- `sku` → **sku** (e.g., 10009)

---

## GROUP 8: FILE SYSTEM DATA (Low Priority)

### File Paths:
- `car_dirpath` → **car_dirpath** (e.g., "rt2000")
- `folder` → **folder_path** (e.g., "/img/cars/skipbarberformula2000")
- `template_path` → **template_path** (e.g., "car_templates/1_template_SBRS.zip")

---

## GROUP 9: CONFIGURATION DATA (Low Priority)

### Technical Configuration:
- `car_configs` → **car_configs** (usually empty array)
- `car_config_defs` → **car_config_defs** (usually empty array)
- `car_rules` → **car_rules** (usually empty array)

---

## RECOMMENDATIONS BY PRIORITY

### 🔴 CRITICAL - Fix Immediately:
1. **Fix name duplication** - properly map manufacturer/model/full_name
2. **Add package_id** - essential for ownership tracking
3. **Create CarCategory model** - stop misusing CarClass
4. **Add pricing fields** - price, free_with_subscription, etc.

### 🟡 HIGH PRIORITY - Next Phase:
1. **Add technical specs** - hp, weight, capabilities
2. **Create CarType model** - for multiple car types per car
3. **Add media fields** - logo_url, images
4. **Add display_name to SimCar** - use car_name for display

### 🟢 MEDIUM PRIORITY - Future Enhancement:
1. **Customization options** - paint patterns, customization rules
2. **Rich content** - HTML descriptions, tech specs
3. **Administrative data** - creation dates, SKU, etc.

### ⚪ LOW PRIORITY - Optional:
1. **File system paths** - mostly for internal iRacing use
2. **Empty configuration arrays** - not used by most cars

---

## NEXT STEPS

1. **Discuss field placement** - which fields go in which models
2. **Plan migration strategy** - how to add fields without breaking existing data
3. **Update data loading script** - fix the name duplication and add new fields
4. **Create new models** - CarCategory and CarType
5. **Test with real data** - ensure the new structure works correctly 