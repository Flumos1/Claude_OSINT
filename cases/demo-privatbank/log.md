# Журнал сбора

> Каждая строка — действие: что искал, где, чем, что нашёл. Для воспроизводимости.

| Дата/время | Действие | Источник/инструмент | Результат | Файл/ссылка |
|------------|----------|---------------------|-----------|-------------|
| 2026-06-10 | Enrich company 14360570 (ua) | Платформа /api/enrich → ua_company+prozorro+opendatabot | ЄДРПОУ валиден; 2817 тендеров; ссылки на реестры | data/company-14360570.json |
| 2026-06-10 | Enrich domain privatbank.ua | Платформа /api/enrich → domain_recon | NS AWS, 2 IP, RDAP | data/domain-privatbank.ua.json |
| 2026-06-10 | Enrich ip 75.2.32.163 | Платформа /api/enrich → ip_geo_asn | AWS Global Accelerator, Seattle | data/ip-75.2.32.163.json |
