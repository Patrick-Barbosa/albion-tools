import urllib.request
import json
import sys
import argparse
from datetime import datetime, timezone

sys.stdout.reconfigure(encoding='utf-8')

def parse_date(d_str):
    if not d_str or d_str.startswith("0001"):
        return None
    for fmt in ("%Y-%m-%dT%H:%M:%S", "%Y-%m-%dT%H:%M:%S.%f", "%Y-%m-%d %H:%M:%S"):
        try:
            return datetime.strptime(d_str.split("+")[0].split("Z")[0], fmt).replace(tzinfo=timezone.utc)
        except ValueError:
            pass
    return None

def audit_items(city: str, items: list):
    url = f"https://west.albion-online-data.com/api/v2/stats/prices/{','.join(items)}.json?locations={city}&qualities=1,2,3,4,5"
    req = urllib.request.Request(url, headers={"User-Agent": "AlbionSafeSuite/3.0"})
    with urllib.request.urlopen(req, timeout=10) as resp:
        data = json.loads(resp.read().decode("utf-8"))

    now = datetime.now(timezone.utc)
    print(f"=== 🔍 AUDITORIA DE PREÇOS EM {city.upper()} ===")
    print(f"Hora Atual UTC: {now.strftime('%Y-%m-%d %H:%M:%S')}\n")

    for d in data:
        sell_p = d.get("sell_price_min", 0)
        sell_dt = parse_date(d.get("sell_price_min_date"))
        
        buy_p = d.get("buy_price_max", 0)
        buy_dt = parse_date(d.get("buy_price_max_date"))
        
        if sell_p > 0 or buy_p > 0:
            age_sell = f"{(now - sell_dt).total_seconds() / 60:.1f} min atrás" if sell_dt else "N/A"
            age_buy = f"{(now - buy_dt).total_seconds() / 60:.1f} min atrás" if buy_dt else "N/A"
            is_fresh = (sell_dt and (now - sell_dt).total_seconds() <= 3600)
            status = "🟢 ATUALIZADO" if is_fresh else "🔴 OBSOLETO (>1h)"
            
            print(f"[{status}] Item: {d['item_id']:<20} Q{d['quality']} | Menor Venda: {sell_p:>8,}s ({age_sell}) | Maior Compra: {buy_p:>8,}s ({age_buy})")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Auditar idade de preços do Albion Online")
    parser.add_argument("--city", type=str, default="Lymhurst", help="Cidade")
    parser.add_argument("--items", type=str, default="T5_BAG,T5_BAG@1,T4_BAG,T4_BAG@1,T5_RUNE,T4_RUNE", help="Lista de itens separados por vírgula")
    args = parser.parse_args()

    audit_items(args.city, args.items.split(","))
