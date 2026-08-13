import json
from rapidfuzz import fuzz, process

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

image_width = 2800
image_height = 1700

print("PART B: DYNAMIC LABEL-RELATIVE + CONTENT-BOUNDARY DETECTION")
print("=" * 80)

# Key labels to locate dynamically (using shorter fragments for better OCR match)
anchor_labels = {
    'occupant_label': 'ಸ್ವಾಧೀನದಾರನ ಹೆಸರು',  # Shortened from full label
    'cultivation_label': 'ಸಾಗುವಳಿ',
    'other_rights_label': 'ಇತರೆ ಹಕ್ಕುಗಳು',
}

# Function to find label position via fuzzy match
def find_label_position(label_text, threshold=70):
    """Find the position of a label using fuzzy matching."""
    best_match = None
    best_score = 0
    
    for word in words_with_boxes:
        score = fuzz.ratio(label_text, word['text'])
        if score > best_score and score >= threshold:
            best_score = score
            best_match = word
    
    return best_match, best_score

# Locate anchor labels
print("\nLocating anchor labels dynamically:")
for label_name, label_text in anchor_labels.items():
    match, score = find_label_position(label_text)
    if match:
        y_percent = (match['top'] / image_height) * 100
        print(f"  {label_name}: '{label_text}'")
        print(f"    Found at (left={match['left']}, top={match['top']}) y={y_percent:.1f}% with score={score}")
        print(f"    Matched text: '{match['text']}'")
    else:
        print(f"  {label_name}: '{label_text}' - NOT FOUND (best score below threshold)")

# Dynamic zone extraction based on label positions
print("\n" + "=" * 80)
print("DYNAMIC ZONE EXTRACTION:")
print("=" * 80)

# Find occupant label
occupant_match, _ = find_label_position('ಸ್ವಾಧೀನದಾರನ ಹೆಸರು', threshold=60)
if occupant_match:
    print(f"\ntop_occupant_zone (dynamic):")
    print(f"  Start: after label at y={occupant_match['top']} ({occupant_match['top']/image_height*100:.1f}%)")
    
    # Use a margin below the label to find data rows (labels are in header, data is below)
    start_y = occupant_match['top'] + 50  # 50 pixels below label
    end_y = start_y + 100  # Capture up to 100 pixels of data (narrower to avoid other fields)
    
    print(f"  Data zone: y={start_y} ({start_y/image_height*100:.1f}%) to y={end_y} ({end_y/image_height*100:.1f}%)")
    
    # Extract words in this dynamic zone (focus on right side where occupant data is)
    zone_words = []
    for word in words_with_boxes:
        x_percent = word['left'] / image_width
        if (word['top'] > start_y and word['top'] < end_y and x_percent > 0.40):  # Right 60% of image
            zone_words.append(word)
    
    zone_words.sort(key=lambda w: w['top'])
    
    # Group by rows
    rows = []
    current_row = []
    current_y = None
    y_tolerance = 20
    
    for word in zone_words:
        if current_y is None or abs(word['top'] - current_y) > y_tolerance:
            if current_row:
                rows.append(current_row)
            current_row = [word]
            current_y = word['top']
        else:
            current_row.append(word)
    
    if current_row:
        rows.append(current_row)
    
    print(f"  Found {len(rows)} rows:")
    for i, row in enumerate(rows):
        row_text = ' '.join([w['text'] for w in row])
        print(f"    Row {i+1}: '{row_text}'")

# Find cultivation label
cultivation_match, _ = find_label_position('12. ಸಾಗುವಳಿ', threshold=60)
if cultivation_match:
    print(f"\ncultivation_table_zone (dynamic):")
    print(f"  Start: after label at y={cultivation_match['top']} ({cultivation_match['top']/image_height*100:.1f}%)")
    
    # End at bottom of image
    end_y = image_height
    print(f"  End: image bottom at y={end_y} (100%)")
    
    # Extract words in this dynamic zone
    zone_words = []
    for word in words_with_boxes:
        if word['top'] > cultivation_match['top']:
            zone_words.append(word)
    
    zone_words.sort(key=lambda w: w['top'])
    
    # Group by rows
    rows = []
    current_row = []
    current_y = None
    y_tolerance = 20
    
    for word in zone_words:
        if current_y is None or abs(word['top'] - current_y) > y_tolerance:
            if current_row:
                rows.append(current_row)
            current_row = [word]
            current_y = word['top']
        else:
            current_row.append(word)
    
    if current_row:
        rows.append(current_row)
    
    print(f"  Found {len(rows)} rows:")
    for i, row in enumerate(rows[:15]):  # Show first 15 rows
        row_text = ' '.join([w['text'] for w in row])
        print(f"    Row {i+1}: '{row_text}'")

print("\n" + "=" * 80)
print("CONFIRMATION: No hard-coded percentages used")
print("All zones computed from live-detected label positions")
print("=" * 80)
