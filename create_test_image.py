"""Generate sample satellite test image for UI testing."""
from PIL import Image, ImageDraw

# Create 512x512 satellite style scene
img = Image.new("RGB", (512, 512), (34, 139, 34)) # Forest green background
draw = ImageDraw.Draw(img)

# Ocean / Coastal water body
draw.polygon([(0, 300), (200, 250), (512, 380), (512, 512), (0, 512)], fill=(0, 105, 148))

# River stream
draw.line([(250, 0), (230, 150), (200, 250)], fill=(0, 105, 148), width=18)

# Roads / Highway grid
draw.line([(0, 100), (512, 100)], fill=(120, 120, 120), width=6)
draw.line([(350, 0), (350, 512)], fill=(120, 120, 120), width=6)

# Industrial / Urban building complex
for x in range(370, 480, 30):
    for y in range(120, 240, 30):
        draw.rectangle([x, y, x+20, y+20], fill=(220, 220, 220), outline=(50, 50, 50))

# Save image
img.save("sample_sat_image.png")
print("Saved sample_sat_image.png successfully!")
