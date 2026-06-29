"""
Энричер крипто-адреса — баланс/активность по публичным блокчейн-API (keyless).

BTC: blockchain.info (без ключа). ETH: ethplorer.io с публичным ключом 'freekey'.
Только публичные ончейн-данные.
"""
import re

import requests

from .base import EnricherResult, enricher

TIMEOUT = 15
UA = {"User-Agent": "osint-crypto/1.0"}
BTC_RE = re.compile(r"^(bc1[a-z0-9]{20,}|[13][a-km-zA-HJ-NP-Z1-9]{25,34})$")
ETH_RE = re.compile(r"^0x[a-fA-F0-9]{40}$")


@enricher("crypto_address", "crypto")
def enrich_crypto(value: str) -> EnricherResult:
    res = EnricherResult("crypto_address", "crypto", value)
    v = value.strip()
    root = res.node("crypto", v)
    try:
        if BTC_RE.match(v):
            root.attrs["chain"] = "BTC"
            r = requests.get(f"https://blockchain.info/rawaddr/{v}?limit=0", headers=UA, timeout=TIMEOUT)
            if r.ok:
                d = r.json()
                res.fact(f"BTC: баланс {d.get('final_balance', 0) / 1e8:.8f} BTC, "
                         f"транзакций {d.get('n_tx')}, получено всего "
                         f"{d.get('total_received', 0) / 1e8:.8f} BTC",
                         "blockchain.info", "B2")
                root.attrs["balance_btc"] = round(d.get("final_balance", 0) / 1e8, 8)
            else:
                res.fact("blockchain.info: адрес не найден / лимит API.", "blockchain.info")
        elif ETH_RE.match(v):
            root.attrs["chain"] = "ETH"
            r = requests.get(f"https://api.ethplorer.io/getAddressInfo/{v}?apiKey=freekey",
                             headers=UA, timeout=TIMEOUT)
            if r.ok:
                d = r.json()
                eth = d.get("ETH") or {}
                res.fact(f"ETH: баланс {eth.get('balance')} ETH", "ethplorer.io (freekey)", "B2")
                root.attrs["balance_eth"] = eth.get("balance")
                toks = d.get("tokens") or []
                if toks:
                    res.fact(f"ERC-20 токенов на адресе: {len(toks)}", "ethplorer.io")
                if d.get("countTxs") is not None:
                    res.fact(f"Транзакций: {d.get('countTxs')}", "ethplorer.io")
            else:
                res.fact("ethplorer.io: адрес не найден / лимит API.", "ethplorer.io")
        else:
            res.fact("Формат адреса не распознан (поддержаны BTC и ETH).", "crypto_address")
    except Exception as e:
        res.error = str(e)
    return res
