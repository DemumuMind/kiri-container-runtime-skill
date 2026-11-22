[English](README.md) | [Русский](README.ru.md)

# Навык Kiri Container Runtime

Агентский навык для [Kiri](https://runkiri.com/) — контейнерного рантайма на Rust. Он учит ИИ-агента запускать, проверять и чинить контейнеры Kiri, Compose-стеки, сборки, локальные домены, Kubernetes и диагностику Docker-совместимыми командами.

Навык не хранит версию или адреса документации как истину. При каждом использовании `scripts/kiri_facts.py` сам находит официальный сайт, документацию, API релизов и фид контрольных сумм через метаданные GitHub-репозитория, сверяет их с локальной установкой и сообщает о расхождении. Если источники переехали, навык последует за ними без правки файлов.

## Зачем он нужен

- **Docker-совместимость:** `docker --context kiri ...` и `kiri ...` для жизненного цикла контейнеров, Compose и сборок.
- **Актуальность без обновлений:** адреса и версии определяются в рантайме, а не зашиты в текст.
- **Разные платформы:** Linux работает на ядре хоста, macOS — в небольшой VM, Windows — внутри WSL2. Актуальная матрица команд берется из живой документации.
- **Безопасные операции:** явный выбор движка, проверка контекста, smoke-контейнеры, диагностика без токенов и честные режимы отказов.
- **Готов к агентам:** один вызов `kiri_brief.py` возвращает стадию, риски, следующие действия и проверки; `SKILL.md` — жёсткий контракт.
- **Декларативная адаптация:** `templates/project-adoption.yaml` и `scripts/kiri_apply.py` покрывают новый проект, добавление Kiri в существующий и миграцию без захардкоженных путей.
- **Учитывает стадию:** install, upgrade, остановленный движок, сломанный контекст, CI, инцидент, миграция, живая нагрузка, простой и пустой хост — у каждого свой playbook.

## Установка

Через [Agent Skills CLI](https://github.com/vercel-labs/skills):

```bash
npx skills add DemumuMind/kiri-container-runtime-skill
```

Для Hermes Agent — скопируйте каталог в дерево навыков:

```bash
git clone https://github.com/DemumuMind/kiri-container-runtime-skill.git
mkdir -p ~/.hermes/skills/software-development
cp -R kiri-container-runtime-skill ~/.hermes/skills/software-development/kiri-container-runtime
```

Перезапустите сессию агента, чтобы каталог навыков обновился.

## Требования

| Требование | Зачем |
| --- | --- |
| Python 3, стандартная библиотека | Резолвер источников без внешних пакетов |
| Доступ в интернет | Для живых проверок; без сети режим `degraded` указывается явно |
| `GITHUB_TOKEN` или `GH_TOKEN` (опционально) | Снимает лимит анонимного GitHub API; используется только для `api.github.com` |
| Установленный Kiri | `kiri` — предмет навыка |
| Docker CLI с контекстами | Контекст `kiri` указывает на сокет движка |
| POSIX shell | Для дополнительных скриптов проверки и контекста |

Сам Kiri ставится с [runkiri.com/download](https://runkiri.com/download/) или официальным установщиком:

```bash
curl -fsSL https://runkiri.com/install.sh | bash
```

## Быстрый старт

```bash
# 1. Один вызов — полная картина: стадия, риски, действия, проверки
python3 scripts/kiri_brief.py

# 2. Глубокая проверка источников при необходимости
python3 scripts/kiri_facts.py

# 2b. План адаптации проекта (новый / добавление / миграция)
python3 scripts/kiri_apply.py --project . --mode auto
# добавьте --write после закрытия блокирующих значений

# 3. Работа через контекст kiri
docker --context kiri run --rm alpine echo KIRI_OK
docker --context kiri compose -f templates/compose-smoke.yaml up -d
docker --context kiri compose -f templates/compose-smoke.yaml down
```

Агент читает сначала `stage`, выполняет `next_actions` по порядку и заканчивает `verification`. Вопрос оператору задаётся только тогда, когда brief не знает значение (образ, порт, ключи), или перед необратимым внешним действием.

## Состав репозитория

| Путь | Назначение |
| --- | --- |
| `SKILL.md` | Контракт агента: первый вызов, карта стадий, процедура, безопасность, проверка |
| `references/workflows.md` | Playbook по стадиям с критериями завершения |
| `references/adoption.md` | Как агент применяет YAML-контракт к реальным проектам |
| `references/failures.md` | Симптом → проверка → фикс → верификация |
| `references/integrations.md` | CI, SDK, systemd, сборки, несколько проектов, публичный доступ |
| `references/cli.md` | Шаблоны команд; источник — живые доки |
| `references/linux.md` | Linux: сокет, контекст, группа, обновления |
| `references/platforms.md` | Особенности платформ; источник — живые доки |
| `scripts/kiri_brief.py` | Один вызов: стадия, риски, действия, проверки |
| `scripts/kiri_facts.py` | Динамическое обнаружение источников и сверка версий |
| `scripts/kiri-doctor.sh` | Проверка здоровья и smoke-контейнер |
| `scripts/kiri-context.sh` | Идемпотентное создание/выбор контекста |
| `templates/compose-smoke.yaml` | Минимальный Compose-стек |
| `templates/project-adoption.yaml` | Декларативный контракт: новый проект / добавление / миграция |
| `scripts/kiri_apply.py` | Чтение YAML, определение профиля, план и запись |
| `templates/github-actions.yml` | CI-шаблон с быстрым провалом по стадии |
| `tests/test_facts.py` | Тест переезда источников и деградации сети |
| `tests/test_brief.py` | Тест приоритета стадий и контракта агента |
| `tests/test_apply.py` | Тест YAML, определения профиля и безопасной записи |
| `.github/workflows/source-watch.yml` | Ежедневная проверка дрейфа |

## Как работает актуальность

Единственная константа — идентификатор репозитория Kiri на GitHub (`KIRI_BOOTSTRAP_REPO`, при переезде репозитория переменная окружения меняет его). Из его метаданных навык берет домашнюю страницу, ветку и API релизов; со страницы — ссылки на документацию, установщик и контрольные суммы. Каждый источник хешируется, адреса печатаются в `discovery.resolved_urls`, а версия сравнивается с локальной.

Если репозиторий переехал или добавил новую версию, правки в навыке не нужны. Если недоступен сам bootstrap — режим `degraded` называет конкретный источник, и ответ опирается только на локальный `kiri --help`.

## Ключевые слова

kiri container runtime, runkiri, kiri skill, agent skill, docker desktop alternative, orbstack alternative, containers, docker cli, compose, buildx, linux containers, rust runtime, devops agent, hermes agent skill.

## Лицензия

MIT — DemumuMind.
