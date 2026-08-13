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

# Known ground truth values from raw_html
ground_truth_anchors = {
    'survey_no': '2',
    'village': 'ADAKAMARANAHALLI',
    'hissa_no': '*',
    'land_id_part1': '6127',
    'land_id_part2': '7900',
    'land_id_part3': '0003',
}

print("Cross-validating ground truth anchors against OCR word list:")
print("=" * 70)

for anchor_name, anchor_value in ground_truth_anchors.items():
    print(f"\nSearching for {anchor_name} = '{anchor_value}':")
    found = False
    for word in words_with_boxes:
        if anchor_value in word['text']:
            found = True
            print(f"  ✓ Found at (left={word['left']}, top={word['top']}, width={word['width']}, height={word['height']}) with confidence={word['conf']:.1f}%")
            print(f"    OCR text: '{word['text']}'")
    if not found:
        print(f"  ✗ NOT FOUND in OCR output")

# Also search for partial matches and similar-looking OCR errors
print("\n" + "=" * 70)
print("Searching for partial matches and OCR errors:")

# Search for village name parts
village_parts = ['ADAKAMARANAHALLI', 'ADAKAMARAN', 'AHALLI', 'ADAKA']
for part in village_parts:
    for word in words_with_boxes:
        if part in word['text'] or word['text'] in part:
            print(f"Village part '{part}' matched OCR: '{word['text']}' at (left={word['left']}, top={word['top']}) conf={word['conf']:.1f}%")

# Search for land ID parts
land_id_parts = ['6127', '7900', '0003', '003']
for part in land_id_parts:
    for word in words_with_boxes:
        if part in word['text']:
            print(f"Land ID part '{part}' matched OCR: '{word['text']}' at (left={word['left']}, top={word['top']}) conf={word['conf']:.1f}%")

# Search for survey number variations
survey_variants = ['2', '೨', '02', '002']
for variant in survey_variants:
    for word in words_with_boxes:
        if variant in word['text']:
            print(f"Survey variant '{variant}' matched OCR: '{word['text']}' at (left={word['left']}, top={word['top']}) conf={word['conf']:.1f}%")
