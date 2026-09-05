"""Test runner for fallback question scan and PDF download button."""
import sys, os
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

from dotenv import load_dotenv
load_dotenv()

from PIL import Image, ImageDraw
import app

print("--- Testing Image Scanning Fallback & PDF Download ---", flush=True)

# 1. Test image scanning with empty question string
img1 = Image.new("RGB", (400, 400), color=(34, 139, 34))
draw1 = ImageDraw.Draw(img1)
draw1.rectangle([100, 100, 200, 200], fill=(211, 211, 211))

print("\n1. Testing Image Scanning without question (empty string)...", flush=True)
banner, answer, conf, ev_img, trace_str = app.run_query(img1, None, "")
print(f"Banner: {banner}", flush=True)
print(f"Answer: {answer[:120]}...", flush=True)
print(f"Confidence: {conf}", flush=True)
assert len(answer) > 0
print("IMAGE SCAN FALLBACK TEST: PASS", flush=True)

# 2. Test PDF Download Button function
print("\n2. Testing PDF Download Button function...", flush=True)
pdf_path = app.generate_pdf_report(trace_str, answer, conf)
print(f"Generated PDF Filepath: {pdf_path}", flush=True)
assert pdf_path and os.path.isabs(pdf_path) and os.path.exists(pdf_path)
print("PDF DOWNLOAD TEST: PASS", flush=True)

print("\n=== ALL TESTS PASSED SUCCESSFULLY! ===", flush=True)
