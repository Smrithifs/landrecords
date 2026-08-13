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

# Search for occupant names
occupant_names = ['ದಾಸ', 'ಮಾರಹನುಮ', 'ಹನುಮಂತ', 'ಬಿನ್', 'ತಳವಾಳ', 'ಇನಾಲ೦ತಿದಾರ್']

print("Searching for occupant names in OCR output:")
print("=" * 70)
image_height = 1700

for name in occupant_names:
    for word in words_with_boxes:
        if name in word['text']:
            y_percent = (word['top'] / image_height) * 100
            print(f"'{name}' found in '{word['text']}' at (left={word['left']}, top={word['top']}) y={y_percent:.1f}% conf={word['conf']:.1f}%")

# Also search for all words in the 50%-80% y range to see what's there
print("\n" + "=" * 70)
print("All words in y-range 50%-80% (middle section):")
print("=" * 70)

middle_words = [w for w in words_with_boxes if 0.50 <= (w['top']/image_height) <= 0.80]
middle_words.sort(key=lambda w: w['top'])

for word in middle_words[:20]:  # Show first 20
    y_percent = (word['top'] / image_height) * 100
    print(f"'{word['text']}' at y={y_percent:.1f}% (left={word['left']}) conf={word['conf']:.1f}%")
