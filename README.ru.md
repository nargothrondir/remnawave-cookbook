# remnawave-cookbook

[English](README.md) · **Русский**

Skill для ИИ-агента (плагин Claude Code) для эксплуатации флота **Remnawave**, устроенного так:

- **VLESS + REALITY (TCP, Vision)** на порту 443, с **сайтом-приманкой (self-steal)** за **Angie/nginx на unix-сокете**;
- **VLESS поверх xHTTP на том же порту 443** — веб-сервер передаёт его в Xray по одному секретному пути;
- клиенты **Mihomo (Clash.Meta)**;
- всё создаётся **через API панели**, идемпотентно.

«Cookbook» в обоих смыслах: общие рецепты и факты о протоколах и связках — и эталонная реализация, в которой они работают.

## Чем отличается

- **Каждый факт привязан к версии и ссылается на файл-источник.** Стек меняется быстро, а ИИ-ассистенты уверенно отвечают по памяти. Этот skill отвечает по коду Remnawave 2.8.0, Xray v26.6.27 и Mihomo v1.19.31 и помечает всё, что проверить не удалось.
- **Написан с живого флота, затем обезличен.** Никаких IP-адресов, доменов, названий провайдеров и нод. Это проверяет CI, в том числе по секретному списку запрещённых строк, который в репозиторий не попадает.
- **Уроки, которые чего-то стоили.** Тег как идентичность inbound и каскад при переименовании; ноды, которые панель выключает сама; почему по умолчанию `grpc_pass`, а не `proxy_pass`; зачем Mihomo `reuse-settings`.

## Состояние

Этапы 1–6 плана готовы:
- роутер (`SKILL.md`);
- справочник: архитектура, контракты API Remnawave 2.8, Xray v26.6.27, Angie, Mihomo, автоматизация, источники;
- карта операций, диагностика и примеры;
- офлайн-валидатор с тестами;
- аудит живого флота (в эталонной реализации);
- точки входа для других ассистентов;
- «на вырост»: таблица того, что ещё умеет стек (Hysteria2, xHTTP H3, разделение потоков, CDN, WebSocket, gRPC), и страница про Hysteria2, сверенная с исходниками до начала работ.

## Структура

```
.claude-plugin/              манифесты плагина и marketplace
skills/edge-check/           процедура: проверить ноду так, как её видит сканер
skills/delay-probe/          процедура: замер записи из клиента Mihomo, честный A/B
skills/config-review/        процедура: validate.py на профиль и отрендеренный конфиг, находки → исправления
agents/pinned-source-checker.md   проверяет утверждение по исходникам upstream на теге версии
bin/edge-check               пробы HTTPS/TLS только на чтение → PASS/FAIL (в PATH Bash, пока плагин включён)
bin/mihomo-probe.ps1         проверки задержки через контроллер Mihomo → CSV и сводка
skills/remnawave-cookbook/
  SKILL.md                   роутер: архитектура, инварианты, проверенные версии
  reference/                 architecture · remnawave-2.8 · xray-v26.6.27 · angie · mihomo · automation · growth · hysteria2 · sources
  operations.md              задача → что запускать → как выглядит успех
  diagnostics.md             симптом → причина → проверка → исправление
  examples/                  обезличенные профиль, блоки Angie, записи Mihomo
  validate.py                офлайн-проверка экспорта профиля и отрендеренного конфига веб-сервера (stdlib)
  audit.md                   как запускать, что значит каждая находка; аудит живого флота
AGENTS.md                    точка входа для Codex и других инструментов, читающих AGENTS.md
tests/                       по тесту на каждое правило валидатора
tools/
  tells-guard.sh             ничто здесь не должно указывать на реальную инфраструктуру
  check-entrypoints.sh       каждая точка входа ведёт ко всем страницам; ссылки не битые
  check-versions.sh          версии в описании = закреплённые в эталонной реализации
  build-chatgpt-bundle.sh    весь skill одним Markdown-файлом
```

## Установка (Claude Code)

```
/plugin marketplace add nargothrondir/remnawave-cookbook
/plugin install remnawave-cookbook@remnawave-cookbook
```

Что входит (имена с префиксом плагина):

| Компонент | Вид | Зачем |
|---|---|---|
| `remnawave-cookbook` | skill | справочник: архитектура, инварианты, проверенные факты, диагностика |
| `edge-check` | skill + `bin/edge-check` | выглядит ли нода снаружи как обычный сайт на nginx: TLS, сертификат, заголовки, 404, все страницы ошибок, чужой Host |
| `delay-probe` | skill + `bin/mihomo-probe.ps1` | замер задержки из клиента Mihomo: burst и после простоя, честный A/B, когда разница реальна |
| `config-review` | skill | `validate.py` на экспорт профиля и отрендеренный конфиг веб-сервера; каждая находка → её исправление |
| `pinned-source-checker` | агент | CONFIRMED / REFUTED / UNVERIFIABLE для утверждения про Xray, Remnawave, Mihomo, Angie или nginx — с цитатой из исходника на теге версии |

Skills подключаются сами на подходящие вопросы или явно
(`/remnawave-cookbook:edge-check`). Скрипты из `bin/` лежат в `PATH` инструмента
Bash, пока плагин включён.

Чтобы плагин был у всех, кто работает в репозитории, зарегистрируйте
marketplace и включите плагин в `.claude/settings.json` этого репозитория
(`extraKnownMarketplaces`, `enabledPlugins`); Claude Code один раз спросит
каждого пользователя, доверять ли marketplace.

Без системы плагинов скопируйте `skills/remnawave-cookbook/` в
`~/.claude/skills/` или `<проект>/.claude/skills/` — справочник работает сам
по себе; процедурам нужен `bin/` рядом.

## Другие ассистенты

- **OpenAI Codex** и другие инструменты, читающие `AGENTS.md`: склонируйте репозиторий в свой проект или рядом с ним — `AGENTS.md` ведёт к тому же содержимому.
- **ChatGPT** (без доступа к репозиторию): выполните `bash tools/build-chatgpt-bundle.sh` или скачайте артефакт `chatgpt-bundle` любого прогона CI и добавьте `remnawave-cookbook.md` в файлы «Проекта» ChatGPT.

CI проверяет, что все они ведут к одним и тем же страницам, так что ни одна точка входа не устаревает незаметно.

## Эталонная реализация

Описанная здесь архитектура работает из двух публичных репозиториев:
- [`ansible-playbooks`](https://github.com/nargothrondir/ansible-playbooks) — провижининг и автоматизация панели через API;
- [`docker-stacks`](https://github.com/nargothrondir/docker-stacks) — стек ноды: нода Remnawave, Angie, ACME-хук.

## Благодарности

- **[Case211/skill-remnawave-xray](https://github.com/Case211/skill-remnawave-xray)** — спасибо! Устройство этого skill вдохновлено той работой: роутер над справочными страницами, диагностика от симптома, исполняемая проверка согласованности, синхронизированные точки входа. Текст здесь написан заново по первоисточникам, для другой архитектуры и других версий. Ни текст, ни код не копировались, поэтому у репозитория своя лицензия (MIT), а у оригинала — AGPL-3.0.
- **[XTLS/Xray-core](https://github.com/XTLS/Xray-core)** и статья RPRX [XHTTP: Beyond REALITY](https://github.com/XTLS/Xray-core/discussions/4113).
- **[Remnawave](https://github.com/remnawave)**, **[MetaCubeX/mihomo](https://github.com/MetaCubeX/mihomo)**, **Angie**.
- **[legiz-ru/my-remnawave](https://github.com/legiz-ru/my-remnawave)** — за разобранный пример xHTTP через nginx с Remnawave.

## Дисклеймер

Образовательный материал о технологиях приватности и обхода цензуры. Применяйте в рамках закона своей юрисдикции. В примерах — заглушки (`example.com`, документационные диапазоны адресов). Это шаблоны, а не готовые конфиги для запуска.

## Лицензия

MIT — см. [LICENSE](LICENSE).
