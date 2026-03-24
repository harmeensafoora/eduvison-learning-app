#!/usr/bin/env python
import requests
import sys

pdf_path = r'd:\8th Sem\eduvison\eduvision-code\KBN01\KBN01\medical-pdf-app\uploads\The Heart!.pdf'

print(f"Testing upload with: {pdf_path}")
print(f"File exists: {sys.modules.__contains__('os') or __import__('os').path.exists(pdf_path)}")

with open(pdf_path, 'rb') as f:
    files = {'file': ('The Heart!.pdf', f)}
    try:
        print("Sending request to http://127.0.0.1:8000/upload...")
        r = requests.post('http://127.0.0.1:8000/upload', files=files, timeout=60)
        print(f"Status Code: {r.status_code}")
        
        if r.status_code == 200:
            print("✓ Upload successful!")
            import json
            data = r.json()
            print(f"Session ID: {data.get('session_id', 'N/A')[:12]}...")
            print(f"Response keys: {list(data.keys())}")
        else:
            print(f"✗ Upload failed with {r.status_code}")
            print(f"Response Text: {r.text[:1000]}")
            
    except requests.exceptions.Timeout:
        print("✗ Request timed out (API might be hanging or too slow)")
    except Exception as e:
        import traceback
        print(f"✗ Error: {type(e).__name__}: {e}")
        traceback.print_exc()
