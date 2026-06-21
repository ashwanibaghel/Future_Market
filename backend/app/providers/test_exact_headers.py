import requests

def test_exact():
    headers = {
        'Connection': 'keep-alive',
        'Cache-Control': 'max-age=0',
        'DNT': '1',
        'Upgrade-Insecure-Requests': '1',
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Sec-Fetch-User': '?1',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.9',
        'Sec-Fetch-Site': 'none',
        'Sec-Fetch-Mode': 'navigate',
        # Removed 'br' to avoid Brotli compression if package not installed
        'Accept-Encoding': 'gzip, deflate',
        'Accept-Language': 'en-US,en;q=0.9,hi;q=0.8',
    }
    
    url = "https://www.nseindia.com/api/NextApi/apiClient/GetQuoteApi?functionName=getSymbolDerivativesData&symbol=NIFTY"
    
    s = requests.Session()
    print("Hitting home page...")
    r1 = s.get("https://www.nseindia.com", headers=headers, timeout=10)
    print("Home Status:", r1.status_code)
    
    print("Hitting option-chain landing page...")
    r2 = s.get("https://www.nseindia.com/option-chain", headers=headers, timeout=10)
    print("Landing Status:", r2.status_code)
    
    print("Hitting API...")
    r3 = s.get(url, headers=headers, timeout=10)
    print("API Status:", r3.status_code)
    print("API Content-Encoding:", r3.headers.get("content-encoding"))
    
    try:
        data = r3.json()
        print("API Success!")
        print("Keys:", list(data.keys()))
        if "data" in data and len(data["data"]) > 0:
            print("Number of records in 'data':", len(data["data"]))
            print("First record:", data["data"][0])
            print("Underlying Spot Value:", data.get("underlyingValue"))
    except Exception as e:
        print("Failed to parse JSON:", e)
        print("Raw Content start:", repr(r3.content[:100]))

test_exact()
