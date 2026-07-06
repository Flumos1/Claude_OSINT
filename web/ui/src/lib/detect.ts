// Авто-детект типа сущности из сырого ввода. Возвращает ранжированные догадки —
// первая используется по умолчанию, остальные предлагаются как «может, вы имели в виду…».

export type EntityType =
  | "email" | "domain" | "ip" | "phone"
  | "username" | "company" | "person" | "url";

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
};

const LABEL: Record<EntityType, string> = {
  email: "email", domain: "домен", ip: "IP", phone: "телефон",
  username: "username", company: "компания", person: "персона", url: "URL",
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
  else if (RE.ip.test(v)) out.push(g("ip"));
  else if (RE.url.test(v)) { out.push(g("url")); out.push(g("domain")); }
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
  else out.push(g("username"));

  // username почти всегда осмысленный запасной вариант для одиночного токена
  if (!out.some((o) => o.type === "username") && !/\s/.test(v) && !RE.email.test(v)) {
    out.push(g("username"));
  }
  return out;
}
