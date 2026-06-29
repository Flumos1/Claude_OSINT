// Движок подсказок «что дальше» — декларативные правила: тип входа + находки → действия.
// Расширяется вместе с энричерами. Подсказка либо пивотит на новый поиск (pivot),
// либо информативна (tip).

import type { EnrichResult, GraphNode } from "./api";

export interface Suggestion {
  title: string;
  desc: string;
  tone: "accent" | "neutral";
  pivot?: { type: string; value: string; country?: string };
  action?: "deep" | "save"; // спец-действия: deep-скан / сохранить в кейс
}

function lowConfidence(nodes: GraphNode[]): number {
  return nodes.filter((n) => {
    const c = String(n.attrs?.confidence || "");
    return c === "D5" || (typeof n.attrs?.score === "number" && (n.attrs.score as number) < 55);
  }).length;
}

export function suggest(res: EnrichResult): Suggestion[] {
  const out: Suggestion[] = [];
  const t = res.input.type;
  const byType = (k: string) => res.nodes.filter((n) => n.type === k && n.value !== res.input.value);

  // Пивоты на обнаруженные смежные сущности
  for (const e of byType("email"))
    out.push({ title: "Проверить email", desc: `${e.value} → утечки, Gravatar, привязки`, tone: "accent", pivot: { type: "email", value: e.value } });
  for (const d of byType("domain"))
    out.push({ title: "Разведка домена", desc: `${d.value} → DNS, сертификаты, Wayback`, tone: "neutral", pivot: { type: "domain", value: d.value } });
  for (const p of byType("phone"))
    out.push({ title: "Проверить телефон", desc: `${p.value} → оператор, регион`, tone: "neutral", pivot: { type: "phone", value: p.value } });

  // Тип-специфичные подсказки
  if (t === "username") {
    const low = lowConfidence(res.nodes);
    out.push({ title: "Запустить deep-режим", desc: "740 сайтов WhatsMyName вместо 21 — с прогрессом", tone: "accent", action: "deep" });
    if (low > 0)
      out.push({ title: `${low} хитов под вопросом`, desc: "Низкая уверенность — открыть для ручной проверки аватара", tone: "neutral" });
    const gh = res.nodes.find((n) => n.type === "url" && String(n.value).includes("github.com"));
    if (gh) out.push({ title: "GitHub → репозитории", desc: "Собрать репо, языки, утёкшие секреты", tone: "neutral" });
  }
  if (t === "email") {
    const dom = res.input.value.split("@")[1];
    if (dom) out.push({ title: "Разведка домена почты", desc: `${dom} → инфраструктура и связанные адреса`, tone: "neutral", pivot: { type: "domain", value: dom } });
  }
  if (t === "domain") {
    out.push({ title: "Проверить на тайпсквоттинг", desc: "Похожие домены (dnstwist) — фишинг/бренд-защита", tone: "neutral" });
  }
  if (t === "company") {
    out.push({ title: "Проверить бенефициаров", desc: "Перейти к скилу company-dd: связи и аффилированность", tone: "neutral" });
  }

  // Всегда — сохранить в кейс
  out.push({ title: "Сохранить в кейс", desc: "С provenance, источником и датой сбора", tone: "neutral", action: "save" });
  return out;
}
