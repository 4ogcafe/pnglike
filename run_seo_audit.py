import os
import re
import json
import xml.etree.ElementTree as ET
from html.parser import HTMLParser
from fastapi.testclient import TestClient

# Import app to test real responses
from app import app

client = TestClient(app)

class PageSEOParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.title = ""
        self.in_title = False
        self.meta_tags = []
        self.canonical = None
        self.headings = {'h1': [], 'h2': [], 'h3': []}
        self.current_heading = None
        self.images = []
        self.schemas = []
        self.in_script = False
        self.script_type = ""
        self.script_content = ""

    def handle_starttag(self, tag, attrs):
        attr_dict = dict(attrs)
        tag_lower = tag.lower()

        if tag_lower == 'title':
            self.in_title = True
        elif tag_lower == 'meta':
            self.meta_tags.append(attr_dict)
        elif tag_lower == 'link' and attr_dict.get('rel') == 'canonical':
            self.canonical = attr_dict.get('href')
        elif tag_lower in ['h1', 'h2', 'h3']:
            self.current_heading = tag_lower
        elif tag_lower == 'img':
            self.images.append({
                'src': attr_dict.get('src', ''),
                'alt': attr_dict.get('alt', None),
                'loading': attr_dict.get('loading', None)
            })
        elif tag_lower == 'script':
            self.script_type = attr_dict.get('type', '')
            if 'ld+json' in self.script_type:
                self.in_script = True
                self.script_content = ""

    def handle_endtag(self, tag):
        tag_lower = tag.lower()
        if tag_lower == 'title':
            self.in_title = False
        elif tag_lower in ['h1', 'h2', 'h3']:
            self.current_heading = None
        elif tag_lower == 'script' and self.in_script:
            self.in_script = False
            try:
                data = json.loads(self.script_content.strip())
                self.schemas.append(data)
            except Exception as e:
                self.schemas.append({'error': str(e), 'raw': self.script_content.strip()[:100]})

    def handle_data(self, data):
        if self.in_title:
            self.title += data.strip()
        elif self.current_heading:
            if self.headings[self.current_heading] and self.headings[self.current_heading][-1].endswith(' '):
                self.headings[self.current_heading][-1] += data.strip()
            else:
                self.headings[self.current_heading].append(data.strip())
        elif self.in_script:
            self.script_content += data

pages_to_audit = [
    ('/', 'Home / Tool Suite'),
    ('/blog', 'Blog Index'),
    ('/about', 'About Us'),
    ('/contact', 'Contact Us'),
    ('/faq', 'FAQ'),
    ('/privacy', 'Privacy Policy'),
    ('/terms', 'Terms of Service'),
    ('/cookies', 'Cookie Policy'),
    ('/blog/ecommerce-product-photography-pure-white-studio-catalogs', 'Blog Post 1 - Ecommerce'),
    ('/blog/mastering-ai-background-removal-u2net-alpha-matting', 'Blog Post 2 - U2Net'),
    ('/blog/inside-pnglike-9-in-1-ai-image-suite-3d-relight-cinematic', 'Blog Post 3 - 9-in-1 Suite'),
]

results = {}

print("=== AUDITING WEB PAGES ===")
for path, label in pages_to_audit:
    resp = client.get(path)
    if resp.status_code != 200:
        results[path] = {'status': resp.status_code, 'error': 'Non-200 status'}
        continue
    
    parser = PageSEOParser()
    parser.feed(resp.text)
    
    # Extract metas
    desc = next((m.get('content') for m in parser.meta_tags if m.get('name', '').lower() == 'description'), None)
    keywords = next((m.get('content') for m in parser.meta_tags if m.get('name', '').lower() == 'keywords'), None)
    robots = next((m.get('content') for m in parser.meta_tags if m.get('name', '').lower() == 'robots'), None)
    og_title = next((m.get('content') for m in parser.meta_tags if m.get('property', '').lower() == 'og:title'), None)
    og_desc = next((m.get('content') for m in parser.meta_tags if m.get('property', '').lower() == 'og:description'), None)
    og_image = next((m.get('content') for m in parser.meta_tags if m.get('property', '').lower() == 'og:image'), None)
    tw_card = next((m.get('content') for m in parser.meta_tags if m.get('name', '').lower() == 'twitter:card'), None)
    
    # Image metrics
    total_imgs = len(parser.images)
    missing_alt = [img['src'] for img in parser.images if not img['alt'] or img['alt'].strip() == '']
    
    results[path] = {
        'label': label,
        'status': resp.status_code,
        'title': parser.title,
        'title_len': len(parser.title),
        'description': desc,
        'description_len': len(desc) if desc else 0,
        'canonical': parser.canonical,
        'robots': robots,
        'og_title': og_title,
        'og_desc': og_desc,
        'og_image': og_image,
        'twitter_card': tw_card,
        'h1_count': len([h for h in parser.headings['h1'] if h]),
        'h1s': [h for h in parser.headings['h1'] if h][:2],
        'h2_count': len([h for h in parser.headings['h2'] if h]),
        'total_images': total_imgs,
        'missing_alt_count': len(missing_alt),
        'missing_alt_samples': missing_alt[:3],
        'schema_count': len(parser.schemas),
        'schemas': parser.schemas
    }

print("\n=== AUDITING ROBOTS.TXT ===")
robots_resp = client.get('/robots.txt')
robots_ok = robots_resp.status_code == 200
robots_text = robots_resp.text
has_sitemap = 'Sitemap:' in robots_text
print(f"Status: {robots_resp.status_code}, Has Sitemap: {has_sitemap}")

print("\n=== AUDITING SITEMAP.XML ===")
sitemap_resp = client.get('/sitemap.xml')
sitemap_ok = sitemap_resp.status_code == 200
sitemap_urls = []
if sitemap_ok:
    try:
        root = ET.fromstring(sitemap_resp.text)
        ns = {'sm': 'http://www.sitemaps.org/schemas/sitemap/0.9'}
        for loc in root.findall('.//sm:loc', ns):
            sitemap_urls.append(loc.text)
    except Exception as e:
        print(f"Error parsing sitemap: {e}")
print(f"Status: {sitemap_resp.status_code}, URLs in sitemap: {len(sitemap_urls)}")

print("\n=== AUDITING LLMS.TXT ===")
llms_resp = client.get('/llms.txt')
print(f"Status: {llms_resp.status_code}, Length: {len(llms_resp.text)} chars")

audit_summary = {
    'pages': results,
    'robots_txt': {
        'status': robots_resp.status_code,
        'has_sitemap': has_sitemap,
        'content_sample': robots_text[:250]
    },
    'sitemap_xml': {
        'status': sitemap_resp.status_code,
        'total_urls': len(sitemap_urls),
        'urls': sitemap_urls
    },
    'llms_txt': {
        'status': llms_resp.status_code,
        'has_content': len(llms_resp.text) > 100
    }
}

with open('seo_audit_results.json', 'w') as f:
    json.dump(audit_summary, f, indent=2)

print("\nAudit completed and saved to seo_audit_results.json")
