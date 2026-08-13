import json
import os
from datetime import datetime

def main():
    log_dir = "logs/debug"
    os.makedirs(log_dir, exist_ok=True)
    
    print("\n=== KAVERI EC SCRAPER - MANUAL MODE ===")
    print("Since login doesn't work in test browser, you'll do everything manually.")
    print()
    print("Please complete the following steps in your REGULAR browser:")
    print("1. Go to https://kaveri.karnataka.gov.in/landing-page")
    print("2. Login and complete the entire process")
    print("3. Navigate to dashboard")
    print("4. Scroll down and click Online EC")
    print("5. Click Continue")
    print("6. Click After 2004")
    print("7. Fill in all search details (District, SRO, Village, Survey Number, Date)")
    print("8. Enter the captcha")
    print("9. Click Search button")
    print("10. Wait for results to load")
    print()
    print("Once results are displayed:")
    print("1. Right-click on the page and select 'Save Page As...'")
    print("2. Save as 'Webpage, HTML only' to: logs/debug/kaveri_ec_results.html")
    print("3. Press ENTER here when done")
    print()
    
    input("Press ENTER after saving the HTML file...")
    
    html_path = f"{log_dir}/kaveri_ec_results.html"
    if not os.path.exists(html_path):
        print(f"HTML file not found: {html_path}")
        print("Please save the page first.")
        return
    
    print(f"Reading HTML from: {html_path}")
    
    # Read the saved HTML
    with open(html_path, "r", encoding="utf-8") as f:
        page_content = f.read()
    
    # Extract table data
    from bs4 import BeautifulSoup
    soup = BeautifulSoup(page_content, 'html.parser')
    
    ec_data = {
        "timestamp": datetime.now().isoformat(),
        "results": []
    }
    
    # Find all tables
    tables = soup.find_all('table')
    print(f"Found {len(tables)} tables")
    
    for table_idx, table in enumerate(tables):
        rows = table.find_all('tr')
        print(f"Table {table_idx}: {len(rows)} rows")
        
        for row_idx, row in enumerate(rows):
            cells = row.find_all(['td', 'th'])
            if len(cells) >= 2:
                row_data = [cell.get_text(strip=True) for cell in cells]
                if any(row_data):  # Only add non-empty rows
                    ec_data["results"].append({
                        "table": table_idx,
                        "row": row_idx,
                        "data": row_data
                    })
                    print(f"Row {row_idx}: {row_data}")
    
    # Save results
    with open(f"{log_dir}/kaveri_ec_result.json", "w", encoding="utf-8") as f:
        json.dump(ec_data, f, indent=2, ensure_ascii=False)
    print(f"Results saved to {log_dir}/kaveri_ec_result.json")
    
    print("\n=== EXTRACTION COMPLETE ===")
    print(f"Total results extracted: {len(ec_data['results'])}")

if __name__ == "__main__":
    main()
