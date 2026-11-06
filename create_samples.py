import math
import os
from PIL import Image, ImageDraw, ImageFilter

samples_dir = os.path.join(os.path.dirname(__file__), "static", "samples")
os.makedirs(samples_dir, exist_ok=True)

# 1. Product: Modern Sneaker / Shoe
def create_product_sample():
    width, height = 800, 600
    # Background: textured studio floor & wall
    img = Image.new("RGB", (width, height), (235, 238, 242))
    draw = ImageDraw.Draw(img)
    
    # Wall/Floor horizon line
    for y in range(400, 600):
        shade = int(210 - (y - 400) * 0.2)
        draw.line([(0, y), (width, y)], fill=(shade, shade + 3, shade + 8))
    
    # Soft shadow
    shadow = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    sdraw = ImageDraw.Draw(shadow)
    sdraw.ellipse([200, 430, 600, 475], fill=(50, 50, 60, 110))
    shadow = shadow.filter(ImageFilter.GaussianBlur(14))
    img.paste(shadow, (0, 0), shadow)
    
    draw = ImageDraw.Draw(img)
    # Sneaker sole
    sole_points = [
        (220, 420), (280, 425), (420, 430), (540, 428), (580, 415),
        (570, 440), (530, 450), (380, 450), (260, 445), (215, 432)
    ]
    draw.polygon(sole_points, fill=(245, 245, 245), outline=(200, 200, 200))
    
    # Sneaker body (Vibrant Blue & Orange)
    body_points = [
        (225, 420), (250, 370), (330, 310), (430, 315), (470, 345),
        (560, 385), (580, 415), (540, 428), (280, 425)
    ]
    draw.polygon(body_points, fill=(24, 119, 242))
    
    # Shoe collar / tongue
    draw.polygon([(330, 310), (360, 270), (420, 275), (430, 315)], fill=(255, 107, 0))
    
    # White swoosh / stripe
    stripe = [(280, 380), (360, 360), (460, 340), (520, 370), (460, 375), (370, 395)]
    draw.polygon(stripe, fill=(255, 255, 255))
    
    # Laces
    for y_off in range(0, 30, 8):
        draw.line([(370 + y_off, 300 + y_off), (405 + y_off, 290 + y_off)], fill=(255, 255, 255), width=3)
    
    img.save(os.path.join(samples_dir, "product_sneaker.jpg"), quality=95)
    print("Created product_sneaker.jpg")

# 2. Portrait: Person profile
def create_portrait_sample():
    width, height = 700, 800
    # Background: vibrant sunset gradient with bokeh
    img = Image.new("RGB", (width, height))
    for y in range(height):
        r = int(245 - (y / height) * 80)
        g = int(140 + (y / height) * 60)
        b = int(180 + (y / height) * 40)
        for x in range(width):
            img.putpixel((x, y), (r, g, b))
            
    draw = ImageDraw.Draw(img)
    # Add bokeh circles in background
    for cx, cy, rad, color in [
        (120, 150, 60, (255, 255, 255, 90)),
        (580, 220, 90, (255, 220, 180, 80)),
        (160, 480, 75, (255, 240, 200, 70)),
        (620, 560, 110, (240, 180, 220, 60))
    ]:
        circle = Image.new("RGBA", (width, height), (0, 0, 0, 0))
        cdraw = ImageDraw.Draw(circle)
        cdraw.ellipse([cx - rad, cy - rad, cx + rad, cy + rad], fill=color)
        circle = circle.filter(ImageFilter.GaussianBlur(15))
        img.paste(circle, (0, 0), circle)
        
    draw = ImageDraw.Draw(img)
    # Person shoulders & body
    draw.ellipse([175, 480, 525, 950], fill=(30, 41, 59)) # Jacket
    # Neck
    draw.rectangle([310, 380, 390, 500], fill=(235, 180, 150))
    # Head
    draw.ellipse([270, 220, 430, 410], fill=(240, 188, 160)) # Face
    # Hair
    draw.ellipse([250, 170, 450, 330], fill=(44, 28, 18)) # Hair top
    draw.chord([250, 200, 310, 360], 90, 270, fill=(44, 28, 18))
    draw.chord([390, 200, 450, 360], 270, 90, fill=(44, 28, 18))
    # Shirt collar
    draw.polygon([(310, 480), (350, 530), (390, 480)], fill=(255, 255, 255))
    
    img.save(os.path.join(samples_dir, "portrait_person.jpg"), quality=95)
    print("Created portrait_person.jpg")

# 3. Object: Coffee Cup & Ceramic Mug
def create_cup_sample():
    width, height = 700, 600
    # Wooden table background
    img = Image.new("RGB", (width, height), (218, 185, 150))
    draw = ImageDraw.Draw(img)
    for y in range(0, height, 15):
        shade = 185 + int(10 * math.sin(y * 0.1))
        draw.line([(0, y), (width, y)], fill=(shade + 30, shade, shade - 30))
        
    # Mug shadow
    shadow = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    sdraw = ImageDraw.Draw(shadow)
    sdraw.ellipse([220, 430, 480, 480], fill=(60, 40, 30, 130))
    shadow = shadow.filter(ImageFilter.GaussianBlur(16))
    img.paste(shadow, (0, 0), shadow)
    
    draw = ImageDraw.Draw(img)
    # Mug handle
    draw.ellipse([400, 240, 510, 390], fill=(220, 38, 38))
    draw.ellipse([425, 265, 485, 365], fill=(218, 185, 150))
    
    # Mug body (Ceramic Red)
    draw.polygon([(240, 200), (440, 200), (410, 440), (270, 440)], fill=(220, 38, 38))
    # Mug rim (top ellipse)
    draw.ellipse([240, 175, 440, 225], fill=(239, 68, 68))
    # Coffee liquid inside
    draw.ellipse([250, 182, 430, 218], fill=(60, 35, 20))
    # Latte heart art
    draw.ellipse([325, 192, 345, 208], fill=(250, 240, 230))
    draw.ellipse([335, 192, 355, 208], fill=(250, 240, 230))
    draw.polygon([(325, 200), (355, 200), (340, 214)], fill=(250, 240, 230))

    img.save(os.path.join(samples_dir, "coffee_mug.jpg"), quality=95)
    print("Created coffee_mug.jpg")

create_product_sample()
create_portrait_sample()
create_cup_sample()
