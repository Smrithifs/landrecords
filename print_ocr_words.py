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

# Sort by top position (top-to-bottom)
words_with_boxes.sort(key=lambda w: w['top'])

# Print table header
print(f"{'Text':<30} {'Left':>6} {'Top':>6} {'Width':>6} {'Height':>6} {'Conf':>6}")
print('-' * 70)

# Print each word
for word in words_with_boxes:
    print(f"{word['text']:<30} {word['left']:>6} {word['top']:>6} {word['width']:>6} {word['height']:>6} {word['conf']:>6.1f}")

print(f"\nTotal words: {len(words_with_boxes)}")
