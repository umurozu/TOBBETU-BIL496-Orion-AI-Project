"""Quick API test script"""
import requests
import os

BASE = "http://localhost:8000"

# 1. Upload a test image
print("=== Testing Upload ===")
# Create a minimal valid PNG
import struct, zlib
def make_tiny_png():
    """Creates a minimal 2x2 red PNG."""
    raw = b'\x00' + b'\xff\x00\x00' * 2  # row 1
    raw += b'\x00' + b'\xff\x00\x00' * 2  # row 2
    compressed = zlib.compress(raw)
    
    def chunk(ctype, data):
        c = ctype + data
        crc = struct.pack('>I', zlib.crc32(c) & 0xFFFFFFFF)
        return struct.pack('>I', len(data)) + c + crc
    
    sig = b'\x89PNG\r\n\x1a\n'
    ihdr = struct.pack('>IIBBBBB', 2, 2, 8, 2, 0, 0, 0)
    return sig + chunk(b'IHDR', ihdr) + chunk(b'IDAT', compressed) + chunk(b'IEND', b'')

png_data = make_tiny_png()
with open("test_img.png", "wb") as f:
    f.write(png_data)

resp = requests.post(f"{BASE}/upload", files={"file": ("test.png", open("test_img.png", "rb"), "image/png")})
print(f"Status: {resp.status_code}")
print(f"Response: {resp.json()}")

if resp.status_code == 200:
    data = resp.json()
    session_id = data["data"]["session_id"]
    print(f"\nSession ID: {session_id}")
    
    # 2. Test process
    print("\n=== Testing Process (Enhancement) ===")
    resp2 = requests.post(f"{BASE}/process", json={
        "session_id": session_id,
        "editing_type": "enhancement",
        "parameters": {}
    })
    print(f"Status: {resp2.status_code}")
    rj = resp2.json()
    print(f"Response status: {rj.get('status')}")
    print(f"Response message: {rj.get('message')}")
    if rj.get("data"):
        print(f"Result keys: {list(rj['data'].keys())}")
    
    # 3. Test status
    print("\n=== Testing Status ===")
    resp3 = requests.get(f"{BASE}/status/{session_id}")
    print(f"Status: {resp3.status_code}")
    print(f"Response: {resp3.json()}")

# Cleanup
os.remove("test_img.png")
print("\n=== All tests complete ===")
