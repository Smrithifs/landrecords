import json

# Load OCR boxes data
with open('logs/debug/rtc_ocr_boxes.json', 'r', encoding='utf-8') as f:
    ocr_data = json.load(f)

# Build list of words with coordinates
words_with_boxes = []
for i in range(len(ocr_data['text'])):
    text = ocr_data['text'][i].strip()
    conf = ocr_data['conf'][i]
    if text and conf > 0:
        words_with_boxes.append({
            'text': text,
            'left': ocr_data['left'][i],
            'top': ocr_data['top'][i],
            'width': ocr_data['width'][i],
            'height': ocr_data['height'][i],
            'conf': conf
        })

# Confirmed anchor points from cross-validation
confirmed_anchors = {
    'header_village_label': {'text': 'ಗ್ರಾಮ', 'x': 218, 'y': 70, 'conf': 96},
    'header_taluk_label': {'text': 'ತಾಲ್ಲೂಕು', 'x': 214, 'y': 99, 'conf': 96},
    'header_hobli_label': {'text': 'ಹೋಬಳಿ:', 'x': 865, 'y': 99, 'conf': 95},
    'soil_type_label': {'text': 'ನಮೂನೆ', 'x': 281, 'y': 71, 'conf': 96},
    'land_revenue_label': {'text': 'ಕಂದಾಯ', 'x': 851, 'y': 139, 'conf': 86},
    'total_label': {'text': 'ಒಟ್ಟು', 'x': 358, 'y': 180, 'conf': 95},
    'area_label': {'text': 'ವಿಸ್ತೀರ್ಣ', 'x': 414, 'y': 179, 'conf': 96},
    'name_label': {'text': 'ಹೆಸರು', 'x': 1539, 'y': 135, 'conf': 95},
    'survey_number_value': {'text': '2', 'x': 221, 'y': 229, 'conf': 62},
    'land_id_6127': {'text': '6127', 'x': 2601, 'y': 1599, 'conf': 95},
    'land_id_7900': {'text': '7900', 'x': 2660, 'y': 1599, 'conf': 95},
    'hissa_value': {'text': '*:', 'x': 597, 'y': 1604, 'conf': 74},
}

print("CONFIRMED ANCHOR POINTS:")
print("=" * 80)
print(f"{'Anchor':<25} {'Text':<15} {'X':>6} {'Y':>6} {'Conf':>6} {'Y%':>6}")
print("-" * 80)

image_height = 1700
image_width = 2800

for anchor_name, data in confirmed_anchors.items():
    y_percent = (data['y'] / image_height) * 100
    x_percent = (data['x'] / image_width) * 100
    print(f"{anchor_name:<25} {data['text']:<15} {data['x']:>6} {data['y']:>6} {data['conf']:>6} {y_percent:>5.1f}%")

print("\n" + "=" * 80)
print("DERIVED ZONE MAPPING:")
print("=" * 80)

# Derive zones based on confirmed anchors
derived_zones = {
    'header_section': {
        'description': 'Header labels (Village, Taluk, Hobli)',
        'y_min': 0.03,  # Based on village label at y=70 (4.1%)
        'y_max': 0.12,  # Based on hobli label at y=99 (5.8%) + margin
        'x_min': 0.05,  # Based on village label at x=218 (7.8%)
        'x_max': 0.40,  # Based on hobli label at x=865 (30.9%)
    },
    'survey_number_zone': {
        'description': 'Survey number field',
        'y_min': 0.12,  # Below header
        'y_max': 0.18,  # Based on survey value at y=229 (13.5%)
        'x_min': 0.05,  # Left side
        'x_max': 0.15,  # Based on survey value at x=221 (7.9%)
    },
    'soil_type_zone': {
        'description': 'Soil type field',
        'y_min': 0.03,  # Based on soil label at y=71 (4.2%)
        'y_max': 0.10,  # Near header
        'x_min': 0.08,  # Based on soil label at x=281 (10.0%)
        'x_max': 0.20,  # Estimated
    },
    'land_revenue_zone': {
        'description': 'Land revenue section',
        'y_min': 0.07,  # Based on revenue label at y=139 (8.2%)
        'y_max': 0.15,  # Estimated
        'x_min': 0.25,  # Based on revenue label at x=851 (30.4%)
        'x_max': 0.45,  # Estimated
    },
    'total_area_zone': {
        'description': 'Total area field',
        'y_min': 0.09,  # Based on total label at y=180 (10.6%)
        'y_max': 0.18,  # Estimated
        'x_min': 0.10,  # Based on total label at x=358 (12.8%)
        'x_max': 0.20,  # Based on area label at x=414 (14.8%)
    },
    'occupant_name_zone': {
        'description': 'Occupant name field',
        'y_min': 0.07,  # Based on name label at y=135 (7.9%)
        'y_max': 0.15,  # Estimated
        'x_min': 0.50,  # Based on name label at x=1539 (55.0%)
        'x_max': 0.70,  # Estimated
    },
    'footer_land_id_zone': {
        'description': 'Land ID in footer',
        'y_min': 0.92,  # Based on land ID at y=1599 (94.1%)
        'y_max': 0.98,  # Bottom of image
        'x_min': 0.90,  # Based on land ID at x=2601 (93.0%)
        'x_max': 0.98,  # Right edge
    },
    'cultivation_table_zone': {
        'description': 'Cultivation table (bottom section)',
        'y_min': 0.50,  # Middle of image
        'y_max': 0.95,  # Based on footer data
        'x_min': 0.05,  # Full width
        'x_max': 0.95,
    },
}

print(f"{'Zone':<30} {'Y-Min':>8} {'Y-Max':>8} {'X-Min':>8} {'X-Max':>8}")
print("-" * 80)
for zone_name, zone_data in derived_zones.items():
    print(f"{zone_name:<30} {zone_data['y_min']:>8.2f} {zone_data['y_max']:>8.2f} {zone_data['x_min']:>8.2f} {zone_data['x_max']:>8.2f}")
    print(f"  {zone_data['description']}")
