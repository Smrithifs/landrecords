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

# Key Kannada field labels to search for
kannada_labels = {
    'ಸರ್ವೆ ನಂಬರು': 'Survey Number',
    'ಹಿಸ್ಸಾ': 'Hissa',
    'ಪೀಸೆವಾರು': 'Split-up Details',
    'ಒಟ್ಟು ವಿಸ್ತೀರ್ಣ': 'Total Area',
    'ಕಂದಾಯ': 'Land Revenue',
    'ಮಣ್ಣಿನ ನಮೂನೆ': 'Soil Type',
    'ಪಟ್ಟಾ': 'Patta',
    'ಕಟ್ಟೆ ಅಥವಾ ಸ್ವಾಧೀನದಾರನ ಹೆಸರು': 'Occupant Name',
    'ಖಾತೆ ನಂ': 'Khata No',
    'ಗ್ರಾಮ': 'Village',
    'ತಾಲ್ಲೂಕು': 'Taluk',
    'ಹೋಬಳಿ': 'Hobli',
}

print("Searching for Kannada field labels in OCR output:")
print("=" * 70)

for kn_label, en_label in kannada_labels.items():
    print(f"\n{en_label} ('{kn_label}'):")
    found = False
    for word in words_with_boxes:
        if kn_label in word['text'] or word['text'] in kn_label:
            found = True
            print(f"  ✓ Found at (left={word['left']}, top={word['top']}, width={word['width']}, height={word['height']}) conf={word['conf']:.1f}%")
            print(f"    OCR text: '{word['text']}'")
    if not found:
        print(f"  ✗ NOT FOUND")

# Also search for partial label matches
print("\n" + "=" * 70)
print("Searching for partial label matches:")

label_parts = ['ಸರ್ವೆ', 'ನಂಬರು', 'ಹಿಸ್ಸಾ', 'ಪೀಸೆ', 'ವಾರು', 'ಒಟ್ಟು', 'ವಿಸ್ತೀರ್ಣ', 'ಕಂದಾಯ', 'ಮಣ್ಣಿನ', 'ನಮೂನೆ', 'ಪಟ್ಟಾ', 'ಕಟ್ಟೆ', 'ಸ್ವಾಧೀನ', 'ಹೆಸರು', 'ಖಾತೆ', 'ಗ್ರಾಮ', 'ತಾಲ್ಲೂಕು', 'ಹೋಬಳಿ']

for part in label_parts:
    matches = []
    for word in words_with_boxes:
        if part in word['text']:
            matches.append(word)
    if matches:
        print(f"\nLabel part '{part}' found {len(matches)} times:")
        for match in matches[:3]:  # Show first 3 matches
            print(f"  '{match['text']}' at (left={match['left']}, top={match['top']}) conf={match['conf']:.1f}%")
