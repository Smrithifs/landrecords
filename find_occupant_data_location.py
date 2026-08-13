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

image_height = 1700
image_width = 2800

# Search for all occupant-related keywords and their positions
occupant_keywords = ['ತಳವಾಳ', 'ಇನಾಂ', 'ದಾಸ', 'ಬಿನ್', 'ಮಾರಹನುಮ', 'ಹನುಮಂತ', 'ಮೇಲಿನ ಜಂಟಿ', 'RR', '5RR', '4']

print("LOCATING ALL OCCUPANT-RELATED KEYWORDS:")
print("=" * 80)

for keyword in occupant_keywords:
    matches = []
    for word in words_with_boxes:
        if keyword in word['text']:
            y_percent = (word['top'] / image_height) * 100
            x_percent = (word['left'] / image_width) * 100
            matches.append({
                'text': word['text'],
                'y': y_percent,
                'x': x_percent,
                'conf': word['conf']
            })
    
    if matches:
        print(f"\n'{keyword}' found {len(matches)} times:")
        for match in matches:
            print(f"  '{match['text']}' at y={match['y']:.1f}%, x={match['x']:.1f}% conf={match['conf']:.1f}%")
    else:
        print(f"\n'{keyword}' NOT FOUND")

# Group by y-regions to understand the structure
print("\n" + "=" * 80)
print("GROUPING BY Y-REGIONS:")
print("=" * 80)

all_occupant_words = []
for keyword in occupant_keywords:
    for word in words_with_boxes:
        if keyword in word['text']:
            y_percent = (word['top'] / image_height) * 100
            all_occupant_words.append({
                'text': word['text'],
                'y': y_percent,
                'x': (word['left'] / image_width) * 100,
            })

all_occupant_words.sort(key=lambda w: w['y'])

# Define regions
regions = {
    'top_section (0-20%)': [],
    'middle_section (20-60%)': [],
    'bottom_section (60-100%)': [],
}

for word in all_occupant_words:
    if word['y'] < 20:
        regions['top_section (0-20%)'].append(word)
    elif word['y'] < 60:
        regions['middle_section (20-60%)'].append(word)
    else:
        regions['bottom_section (60-100%)'].append(word)

for region_name, words in regions.items():
    if words:
        print(f"\n{region_name}: {len(words)} words")
        for word in words:
            print(f"  '{word['text']}' at y={word['y']:.1f}%, x={word['x']:.1f}%")
