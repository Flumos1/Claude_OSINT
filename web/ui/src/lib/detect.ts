// Авто-детект типа сущности из сырого ввода. Возвращает ранжированные догадки —
// первая используется по умолчанию, остальные предлагаются как «может, вы имели в виду…».

export type EntityType =
  | "email" | "domain" | "ip" | "phone"
  | "username" | "company" | "person" | "url"
  | "crypto" | "aircraft" | "vessel";

export interface Guess {
  type: EntityType;
  country?: "ua" | "ru";
  label: string; // человекочитаемая подпись чипа
}

const RE = {
  email: /^[^\s@]+@[^\s@]+\.[^\s@]+$/,
  ip: /^(\d{1,3}\.){3}\d{1,3}$/,
  url: /^https?:\/\//i,
  domain: /^(?=.{1,253}$)([a-z0-9-]+\.)+[a-z]{2,}$/i,
  phone: /^\+?[\d\s()-]{7,}$/,
  digits: /^\d+$/,
  btc: /^(bc1[a-z0-9]{20,}|[13][a-km-zA-HJ-NP-Z1-9]{25,34})$/,
  eth: /^0x[a-fA-F0-9]{40}$/,
  tron: /^T[1-9A-HJ-NP-Za-km-z]{33}$/,
  imo: /^(imo)?\s*\d{7}$/i,
  icao24: /^[0-9a-f]{6}$/i,
  tail: /^[a-z]{1,2}-[a-z0-9]{2,5}$/i,
};

const LABEL: Record<EntityType, string> = {
  email: "email", domain: "домен", ip: "IP", phone: "телефон",
  username: "username", company: "компания", person: "персона", url: "URL",
  crypto: "крипто-адрес", aircraft: "✈ борт", vessel: "⚓ судно",
};

function g(type: EntityType, country?: Guess["country"]): Guess {
  const flag = country === "ua" ? "🇺🇦 " : country === "ru" ? "🇷🇺 " : "";
  return { type, country, label: flag + LABEL[type] };
}

export function detect(raw: string): Guess[] {
  const v = raw.trim();
  if (!v) return [];
  const out: Guess[] = [];

  if (RE.email.test(v)) out.push(g("email"));
  else if (RE.btc.test(v) || RE.eth.test(v) || RE.tron.test(v)) out.push(g("crypto"));
  else if (RE.ip.test(v)) out.push(g("ip"));
  else if (RE.url.test(v)) { out.push(g("url")); out.push(g("domain")); }
  else if (RE.imo.test(v)) { out.push(g("vessel")); }  // IMO 7 цифр / "IMO NNNNNNN"
  else if (RE.digits.test(v)) {
    // числовые идентификаторы реестров
    if (v.length === 8) out.push(g("company", "ua")); // ЄДРПОУ
    if (v.length === 10 || v.length === 12) out.push(g("company", "ru")); // ИНН
    if (v.length === 13) out.push(g("company", "ru")); // ОГРН
    out.push(g("phone"));
  }
  else if (RE.phone.test(v) && /\d/.test(v) && (v.startsWith("+") || v.replace(/\D/g, "").length >= 10)) {
    out.push(g("phone"));
  }
  else if (RE.domain.test(v)) out.push(g("domain"));
  else if (/\s/.test(v) && v.split(/\s+/).length >= 2 && /[а-яёіїєґa-z]/i.test(v)) {
    // два+ слова → похоже на ФИО
    out.push(g("person", /[а-яёіїєґ]/i.test(v) ? "ua" : undefined));
  }
  else if (RE.tail.test(v)) { out.push(g("aircraft")); out.push(g("username")); }  // бортовой номер UR-PSR
  else out.push(g("username"));

  // ICAO24-hex (6 hex) может быть и ником, и бортом — предложим оба
  if (RE.icao24.test(v) && !out.some((o) => o.type === "aircraft")) out.push(g("aircraft"));
  // username почти всегда осмысленный запасной вариант для одиночного токена
  const isCrypto = RE.btc.test(v) || RE.eth.test(v) || RE.tron.test(v);
  if (!out.some((o) => o.type === "username") && !/\s/.test(v) && !RE.email.test(v) && !isCrypto) {
    out.push(g("username"));
  }
  return out;
}
