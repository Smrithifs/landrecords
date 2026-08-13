from PIL import Image, ImageDraw
import json

# Load the RTC image
image = Image.open('logs/debug/rtc_page.png')
image_width, image_height = image.size

# Create a copy for drawing overlay
overlay = image.copy()
draw = ImageDraw.Draw(overlay)

# Derived zones from confirmed anchor points
derived_zones = {
    'header_labels_zone': {
        'description': 'Header labels (Village, Taluk, Hobli)',
        'y_min': 0.03,
        'y_max': 0.12,
        'x_min': 0.05,
        'x_max': 0.25,
    },
    'header_values_zone': {
        'description': 'Header values (Village, Taluk, Hobli text)',
        'y_min': 0.03,
        'y_max': 0.12,
        'x_min': 0.25,
        'x_max': 0.60,
    },
    'survey_number_zone': {
        'description': 'Survey number field',
        'y_min': 0.12,
        'y_max': 0.18,
        'x_min': 0.05,
        'x_max': 0.15,
    },
    'soil_type_zone': {
        'description': 'Soil type field',
        'y_min': 0.03,
        'y_max': 0.10,
        'x_min': 0.08,
        'x_max': 0.20,
    },
    'land_revenue_zone': {
        'description': 'Land revenue section (left column)',
        'y_min': 0.07,
        'y_max': 0.15,
        'x_min': 0.25,
        'x_max': 0.35,
    },
    'total_area_zone': {
        'description': 'Total area field (right column)',
        'y_min': 0.07,
        'y_max': 0.15,
        'x_min': 0.35,
        'x_max': 0.50,
    },
    'top_occupant_zone': {
        'description': 'Top occupant column (columns 9-10 in top info block)',
        'y_min': 0.10,
        'y_max': 0.25,
        'x_min': 0.40,
        'x_max': 0.85,
    },
    'cultivation_occupant_zone': {
        'description': 'Cultivation table occupant names (bottom section)',
        'y_min': 0.55,
        'y_max': 0.75,
        'x_min': 0.10,
        'x_max': 0.50,
    },
    'footer_land_id_zone': {
        'description': 'Land ID in footer',
        'y_min': 0.92,
        'y_max': 0.98,
        'x_min': 0.90,
        'x_max': 0.98,
    },
    'cultivation_table_zone': {
        'description': 'Cultivation table (bottom section)',
        'y_min': 0.50,
        'y_max': 0.95,
        'x_min': 0.05,
        'x_max': 0.95,
    },
}

# Colors for different zones
colors = {
    'header_labels_zone': 'red',
    'header_values_zone': 'pink',
    'survey_number_zone': 'blue',
    'soil_type_zone': 'green',
    'land_revenue_zone': 'yellow',
    'total_area_zone': 'orange',
    'top_occupant_zone': 'purple',
    'cultivation_occupant_zone': 'lavender',
    'footer_land_id_zone': 'cyan',
    'cultivation_table_zone': 'magenta',
}

# Draw rectangles for each zone
for zone_key, zone_data in derived_zones.items():
    x1 = int(zone_data['x_min'] * image_width)
    y1 = int(zone_data['y_min'] * image_height)
    x2 = int(zone_data['x_max'] * image_width)
    y2 = int(zone_data['y_max'] * image_height)
    
    draw.rectangle([x1, y1, x2, y2], outline=colors.get(zone_key, 'white'), width=3)
    
# Save the overlay
overlay.save('logs/debug/rtc_zones_overlay.png')
print(f'Zone overlay saved to: logs/debug/rtc_zones_overlay.png')
print(f'Image size: {image_width}x{image_height}')
print('\nZones drawn:')
for zone_key, zone_data in derived_zones.items():
    print(f'  {zone_key}: {zone_data["description"]}')
