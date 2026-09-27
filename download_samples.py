"""Download real satellite imagery samples from public direct URLs."""
import urllib.request
import os

os.makedirs("sample_images", exist_ok=True)

# Direct reliable high-res satellite / aerial photo URLs
SATELLITE_SAMPLES = {
    "vqa_city_harbor.jpg": "https://images.unsplash.com/photo-1526778548025-fa2f459cd5c1?w=800&q=80",  # Real satellite view of island / coast
    "grounding_airport.jpg": "https://images.unsplash.com/photo-1542314831-068cd1dbfeeb?w=800&q=80", # Real aerial city / airport view
    "change_before_2000.jpg": "https://images.unsplash.com/photo-1500382017468-9049fed747ef?w=800&q=80", # Landscape T1 (green fields)
    "change_after_2014.jpg": "https://images.unsplash.com/photo-1513836279014-a89f7a76ae86?w=800&q=80",  # Landscape T2 (seasonal / urban change)
    "fusion_sar_optical.jpg": "https://images.unsplash.com/photo-1451187580459-43490279c0fa?w=800&q=80"  # Earth from space / night satellite view
}

headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}

for fname, url in SATELLITE_SAMPLES.items():
    fpath = os.path.join("sample_images", fname)
    try:
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req) as resp, open(fpath, 'wb') as out_file:
            out_file.write(resp.read())
        print(f"Downloaded {fname} successfully ({os.path.getsize(fpath)} bytes).")
    except Exception as err:
        print(f"Failed downloading {fname}: {err}")
