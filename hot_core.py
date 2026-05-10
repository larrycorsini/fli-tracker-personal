import httpx
import json

def traverse_and_extract(obj):
    hotels = []
    
    if isinstance(obj, dict):
        for k, v in obj.items():
            if isinstance(v, list) and len(v) > 10:
                if isinstance(v[5], str) and (v[8] is None or isinstance(v[8], list)):
                    name = v[5]
                    price = v[8][0] if v[8] and isinstance(v[8], list) and len(v[8]) > 0 else "Sold Out"
                    rating = v[7][0][0] if v[7] and isinstance(v[7], list) and len(v[7]) > 0 and isinstance(v[7][0], list) and len(v[7][0]) > 0 else "N/A"
                    total_price = v[13][0] if len(v) > 13 and v[13] and isinstance(v[13], list) and len(v[13]) > 0 else "N/A"
                    
                    price_val = float(price.replace("$", "").replace(",", "")) if price != "Sold Out" else float('inf')
                    
                    hotels.append({
                        "name": name,
                        "price_per_night": price,
                        "total_price": total_price,
                        "price_val": price_val,
                        "rating": rating
                    })
            hotels.extend(traverse_and_extract(v))
    elif isinstance(obj, list):
        for item in obj:
            hotels.extend(traverse_and_extract(item))
            
    return hotels


def search_hotels_core(city: str, checkin: str, checkout: str) -> list[dict]:
    # checkin: 2026-05-10
    ci_y, ci_m, ci_d = [int(x) for x in checkin.split("-")]
    co_y, co_m, co_d = [int(x) for x in checkout.split("-")]
    
    url = "https://www.google.com/_/TravelFrontendUi/data/batchexecute?rpcids=Ya3XAc&source-path=%2Ftravel%2Fsearch&hl=en-US&soc-app=162&soc-platform=1&soc-device=1&rt=c"
    
    req_data = f'["hotels in {city}",null,null,[null,null,null,"USD",[[{ci_y},{ci_m},{ci_d}],[{co_y},{co_m},{co_d}],1,null,0],null,null,null,null,null,null,null,null,[2,null,0],null,null,null,null,null],null,null,null,null,null,1]'
    f_req = [[["Ya3XAc", req_data, None, "generic"]]]
    
    payload = {
        "f.req": json.dumps(f_req)
    }
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Content-Type": "application/x-www-form-urlencoded;charset=UTF-8"
    }
    
    with httpx.Client() as client:
        resp = client.post(url, data=payload, headers=headers)
        
        text = resp.text
        if text.startswith(")]}'"):
            text = text[4:]
            
        all_hotels = []
        chunks = text.split("\n")
        for chunk in chunks:
            try:
                # Cleaning chunk (sometimes it has a length prefix)
                if not chunk.strip() or chunk.strip().isdigit():
                    continue
                
                arr = json.loads(chunk)
                if isinstance(arr, list) and len(arr) > 0 and len(arr[0]) > 2:
                    resp_str = arr[0][2]
                    if isinstance(resp_str, str) and resp_str.startswith("["):
                        inner = json.loads(resp_str)
                        res = traverse_and_extract(inner)
                        all_hotels.extend(res)
            except Exception:
                continue
                
        # Deduplicate and sort by price
        seen = set()
        unique_hotels = []
        for h in all_hotels:
            if h["name"] not in seen:
                seen.add(h["name"])
                unique_hotels.append(h)
                
        unique_hotels.sort(key=lambda x: x["price_val"])
        
        # Cleanup sorting key if desired
        for h in unique_hotels:
            del h["price_val"]
            
        return unique_hotels
