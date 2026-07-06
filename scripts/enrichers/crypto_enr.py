"""
Энричер crypto — базовая аналитика криптоадреса по ПУБЛИЧНЫМ blockchain-эксплорерам (keyless).

BTC — blockstream.info (Esplora API), ETH — blockchair (публичный dashboard-эндпоинт).
Даёт: баланс, число транзакций, объёмы — публичные данные ончейн (никаких закрытых источников).
Определяет тип адреса эвристикой. Для глубокой трассировки — специализированные тулзы
(deep-ссылки на эксплореры/аналитику в выводе).
"""
import re

import requests

from .base import EnricherResult, enricher

TIMEOUT = 20
UA = {"User-Agent": "osint-crypto/1.0"}

BTC_RX = re.compile(r"^(bc1[0-9a-z]{8,87}|[13][a-km-zA-HJ-NP-Z1-9]{25,34})$")
ETH_RX = re.compile(r"^0x[0-9a-fA-F]{40}$")


def _explorers(kind: str, addr: str) -> dict[str, str]:
    if kind == "btc":
        return {"Blockstream": f"https://blockstream.info/address/{addr}",
                "Mempool": f"https://mempool.space/address/{addr}",
                "Blockchair": f"https://blockchair.com/bitcoin/address/{addr}"}
    return {"Etherscan": f"https://etherscan.io/address/{addr}",
            "Blockchair": f"https://blockchair.com/ethereum/address/{addr}"}


@enricher("crypto_addr", "crypto")
def enrich_crypto(value: str) -> EnricherResult:
    res = EnricherResult("crypto_addr", "crypto", value)
    addr = value.strip()
    root = res.node("crypto", addr)

    if BTC_RX.match(addr):
        kind = "btc"
        root.attrs["chain"] = "bitcoin"
        _btc(res, root, addr)
    elif ETH_RX.match(addr):
        kind = "eth"
        root.attrs["chain"] = "ethereum"
        _eth(res, root, addr)
    else:
        res.fact("Адреса не розпізнана як BTC/ETH (перевір формат або мережу — TRON/BNB тощо).",
                 "crypto")
        return res

    for name, url in _explorers(kind, addr).items():
        res.fact(f"Експлорер: {name} — {url}", "deep-link")
    res.fact("⚖️ Ончейн-дані публічні. Прив'язка адреси до особи потребує ≥2 підтверджень "
             "(біржовий KYC, самозаявлення, кластеризація) — не презюмуй власника.", "methodology")
    return res


def _btc(res, root, addr):
    try:
        r = requests.get(f"https://blockstream.info/api/address/{addr}", headers=UA, timeout=TIMEOUT)
        if r.status_code != 200:
            res.error = f"HTTP {r.status_code} (blockstream)"
            return
        d = r.json()
        cs, ms = d.get("chain_stats", {}), d.get("mempool_stats", {})
        funded = cs.get("funded_txo_sum", 0)
        spent = cs.get("spent_txo_sum", 0)
        bal = (funded - spent) / 1e8
        txn = cs.get("tx_count", 0) + ms.get("tx_count", 0)
        root.attrs.update({"balance_btc": f"{bal:.8f}", "tx_count": txn})
        res.fact(f"BTC баланс: {bal:.8f} BTC; транзакцій: {txn}; "
                 f"отримано за весь час: {funded/1e8:.8f} BTC", "blockstream.info", "B2")
    except Exception as e:
        res.error = str(e)


def _eth(res, root, addr):
    # ethplorer публичный ключ 'freekey' — keyless-режим для базовой инфы по адресу
    try:
        r = requests.get(f"https://api.ethplorer.io/getAddressInfo/{addr}",
                         params={"apiKey": "freekey"}, headers=UA, timeout=TIMEOUT)
        if r.status_code != 200:
            res.error = f"HTTP {r.status_code} (ethplorer)"
            return
        d = r.json()
        bal = float((d.get("ETH") or {}).get("balance") or 0)
        txn = d.get("countTxs", 0)
        tokens = d.get("tokens") or []
        root.attrs.update({"balance_eth": f"{bal:.6f}", "tx_count": txn})
        res.fact(f"ETH баланс: {bal:.6f} ETH; транзакцій: {txn}; "
                 f"ERC-20 токенів: {len(tokens)}", "ethplorer.io", "B2")
    except Exception as e:
        res.error = str(e)
