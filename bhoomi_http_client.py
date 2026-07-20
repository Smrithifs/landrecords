import requests
import hashlib
import os
import re
import subprocess
from bs4 import BeautifulSoup
from dotenv import load_dotenv

load_dotenv()
if not os.getenv("BHOOMI_USERNAME"):
    load_dotenv(".env.example")
username = os.getenv("BHOOMI_USERNAME")
password = os.getenv("BHOOMI_PASSWORD")

def md5(t): return hashlib.md5(t.encode()).hexdigest()

def get_vs(html):
    soup = BeautifulSoup(html, 'html.parser')
    vs = soup.find('input', {'id': '__VIEWSTATE'})
    ev = soup.find('input', {'id': '__EVENTVALIDATION'})
    vsg = soup.find('input', {'id': '__VIEWSTATEGENERATOR'})
    return (
        vs['value'] if vs and vs.get('value') else '',
        ev['value'] if ev and ev.get('value') else '',
        vsg['value'] if vsg and vsg.get('value') else ''
    )

def get_option_value(html, select_id, option_text):
    soup = BeautifulSoup(html, 'html.parser')
    sel = soup.find('select', {'id': select_id})
    if not sel:
        print(f"  WARNING: {select_id} not found")
        return option_text
    for opt in sel.find_all('option'):
        if option_text.lower() in opt.text.strip().lower():
            print(f"  Matched '{opt.text.strip()}' value='{opt.get('value')}'")
            return opt.get('value', option_text)
    print(f"  No match for '{option_text}' in {select_id}")
    opts = [(o.get('value'), o.text.strip()) for o in sel.find_all('option')]
    print(f"  Available: {opts[:5]}")
    return option_text

session = requests.Session()
session.headers.update({
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "Connection": "keep-alive",
})

SERVICE37 = "https://landrecords.karnataka.gov.in/service37/"

# === LOGIN ===
r = session.get("https://landrecords.karnataka.gov.in/citizenportal/")
vs, ev, vsg = get_vs(r.text)
captcha_r = session.get("https://landrecords.karnataka.gov.in/citizenportal/GenerateCaptcha.aspx")
os.makedirs("logs/debug", exist_ok=True)
with open("logs/debug/captcha.png", "wb") as f: f.write(captcha_r.content)
subprocess.Popen(["open", "logs/debug/captcha.png"])
captcha = input("Enter CAPTCHA: ").strip()

r = session.post("https://landrecords.karnataka.gov.in/citizenportal/", data={
    "ScriptManager1": "updpanl|btnLogin",
    "txtUname": username, "txtCapctha": captcha,
    "HDusername": md5(username), "HDPassword": md5(password),
    "__ASYNCPOST": "true", "btnLogin": "Login",
    "__VIEWSTATE": vs, "__VIEWSTATEGENERATOR": vsg,
    "__EVENTVALIDATION": ev,
}, headers={"X-Requested-With": "XMLHttpRequest"})
print(f"Login: {r.status_code} cookies={list(session.cookies.keys())}")

# === DASHBOARD → INTERMEDIATE → SERVICE37 ===
session.get("https://landrecords.karnataka.gov.in/citizenportal/Dashboard.aspx")
r_int = session.get("https://landrecords.karnataka.gov.in/citizenportal/App_Intermediate_IRTC.aspx",
    headers={"Referer": "https://landrecords.karnataka.gov.in/citizenportal/Dashboard.aspx"})

soup_int = BeautifulSoup(r_int.text, 'html.parser')
form = soup_int.find('form')
form_data = {inp.get('name'): inp.get('value','') for inp in form.find_all('input')}
form_action = form.get('action')

r_s37 = session.post(form_action, data=form_data, headers={
    "Referer": "https://landrecords.karnataka.gov.in/citizenportal/App_Intermediate_IRTC.aspx",
    "Origin": "https://landrecords.karnataka.gov.in"
})
print(f"service37: {r_s37.status_code} cookies={list(session.cookies.keys())}")

vs, ev, vsg = get_vs(r_s37.text)
print(f"service37 VS={len(vs)} EV={len(ev)}")

# Check dropdowns
soup37 = BeautifulSoup(r_s37.text, 'html.parser')
selects = soup37.find_all('select')
print(f"Dropdowns on service37: {[s.get('id') for s in selects]}")

# === DISTRICT SELECTION ===
dist_value = get_option_value(r_s37.text, 'ctl00_MainContent_ddlCDistrict', 'BENGALURU')
r_dist = session.post(SERVICE37, data={
    "__EVENTTARGET": "ctl00$MainContent$ddlCDistrict",
    "__EVENTARGUMENT": "",
    "ctl00$MainContent$ddlCDistrict": dist_value,
    "ctl00$MainContent$ddlCTaluk": "",
    "ctl00$MainContent$ddlCHobli": "",
    "ctl00$MainContent$ddlCVillage": "",
    "__VIEWSTATE": vs, "__VIEWSTATEGENERATOR": vsg, "__EVENTVALIDATION": ev,
}, headers={"Referer": SERVICE37})
vs, ev, vsg = get_vs(r_dist.text)
print(f"After district: VS={len(vs)} EV={len(ev)}")

# === TALUK ===
taluk_value = get_option_value(r_dist.text, 'ctl00_MainContent_ddlCTaluk', 'Bangalore North')
r_taluk = session.post(SERVICE37, data={
    "__EVENTTARGET": "ctl00$MainContent$ddlCTaluk",
    "__EVENTARGUMENT": "",
    "ctl00$MainContent$ddlCDistrict": dist_value,
    "ctl00$MainContent$ddlCTaluk": taluk_value,
    "ctl00$MainContent$ddlCHobli": "",
    "ctl00$MainContent$ddlCVillage": "",
    "__VIEWSTATE": vs, "__VIEWSTATEGENERATOR": vsg, "__EVENTVALIDATION": ev,
}, headers={"Referer": SERVICE37})
vs, ev, vsg = get_vs(r_taluk.text)
print(f"After taluk: VS={len(vs)} EV={len(ev)}")

# === HOBLI ===
hobli_value = get_option_value(r_taluk.text, 'ctl00_MainContent_ddlCHobli', 'YALAHANKA')
r_hobli = session.post(SERVICE37, data={
    "__EVENTTARGET": "ctl00$MainContent$ddlCHobli",
    "__EVENTARGUMENT": "",
    "ctl00$MainContent$ddlCDistrict": dist_value,
    "ctl00$MainContent$ddlCTaluk": taluk_value,
    "ctl00$MainContent$ddlCHobli": hobli_value,
    "ctl00$MainContent$ddlCVillage": "",
    "__VIEWSTATE": vs, "__VIEWSTATEGENERATOR": vsg, "__EVENTVALIDATION": ev,
}, headers={"Referer": SERVICE37})
vs, ev, vsg = get_vs(r_hobli.text)

# === VILLAGE ===
village_value = get_option_value(r_hobli.text, 'ctl00_MainContent_ddlCVillage', 'KRUSHNASAGARA')
r_village = session.post(SERVICE37, data={
    "__EVENTTARGET": "ctl00$MainContent$ddlCVillage",
    "__EVENTARGUMENT": "",
    "ctl00$MainContent$ddlCDistrict": dist_value,
    "ctl00$MainContent$ddlCTaluk": taluk_value,
    "ctl00$MainContent$ddlCHobli": hobli_value,
    "ctl00$MainContent$ddlCVillage": village_value,
    "__VIEWSTATE": vs, "__VIEWSTATEGENERATOR": vsg, "__EVENTVALIDATION": ev,
}, headers={"Referer": SERVICE37})
vs, ev, vsg = get_vs(r_village.text)

# === SURVEY NUMBER + GO ===
r_go = session.post(SERVICE37, data={
    "__EVENTTARGET": "ctl00$MainContent$btnGo",
    "__EVENTARGUMENT": "",
    "ctl00$MainContent$ddlCDistrict": dist_value,
    "ctl00$MainContent$ddlCTaluk": taluk_value,
    "ctl00$MainContent$ddlCHobli": hobli_value,
    "ctl00$MainContent$ddlCVillage": village_value,
    "ctl00$MainContent$txtCSurveyNo": "2",
    "__VIEWSTATE": vs, "__VIEWSTATEGENERATOR": vsg, "__EVENTVALIDATION": ev,
}, headers={"Referer": SERVICE37})
vs, ev, vsg = get_vs(r_go.text)
print(f"After GO: VS={len(vs)} EV={len(ev)}")

# === FETCH DETAILS with Surnoc=* ===
r_fetch = session.post(SERVICE37, data={
    "__EVENTTARGET": "",
    "__EVENTARGUMENT": "",
    "ctl00$MainContent$btnCFetchDetails": "Fetch details",
    "ctl00$MainContent$ddlCDistrict": dist_value,
    "ctl00$MainContent$ddlCTaluk": taluk_value,
    "ctl00$MainContent$ddlCHobli": hobli_value,
    "ctl00$MainContent$ddlCVillage": village_value,
    "ctl00$MainContent$txtCSurveyNo": "2",
    "ctl00$MainContent$ddlCSurnocNo": "*",
    "ctl00$MainContent$ddlCHissaNo": "",
    "__VIEWSTATE": vs,
    "__VIEWSTATEGENERATOR": vsg,
    "__EVENTVALIDATION": ev,
}, headers={"Referer": SERVICE37})

with open("logs/debug/fetch_response.html", "w") as f:
    f.write(r_fetch.text)

# Print ALL text content
soup_f = BeautifulSoup(r_fetch.text, 'html.parser')
print("All text in fetch response:")
for tag in soup_f.find_all(['td', 'span', 'label', 'div', 'p']):
    t = tag.text.strip()
    if t and 3 < len(t) < 300:
        print(f"  [{tag.name}]: {t[:150]}")

# Check for View RTC link
for a in soup_f.find_all('a', href=True):
    print(f"Link: {a.text.strip()} -> {a['href']}")

# Check for image
img = soup_f.find('img', {'id': 'Image1'})
if img:
    img_url = SERVICE37 + img['src']
    img_r = session.get(img_url, headers={"Referer": SERVICE37})
    print(f"Image: {img_r.status_code} size={len(img_r.content)}")
    with open("logs/debug/rtc_image.png", "wb") as f:
        f.write(img_r.content)
    subprocess.Popen(["open", "logs/debug/rtc_image.png"])
    print("Image opened!")

print(f"Response length: {len(r_fetch.text)}")
