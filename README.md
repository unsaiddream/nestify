<div align="center">

<img src="assets/logo.svg" width="80" height="80" alt="Nestify"/>

# Nestify

**AI-агент для риелторов на Krisha.kz**

Автоматически ищет объявления, анализирует их через Gemini AI и пишет сообщения продавцам — всё локально, без облаков.

[![Demo](https://img.shields.io/badge/▶_Live_Demo-4f8ef7?style=for-the-badge&logoColor=white)](https://unsaiddream.github.io/nestify/)
[![Python](https://img.shields.io/badge/Python_3.11+-3776AB?style=for-the-badge&logo=python&logoColor=white)](https://python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-009688?style=for-the-badge&logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com)
[![Gemini](https://img.shields.io/badge/Gemini_AI-4285F4?style=for-the-badge&logo=google&logoColor=white)](https://aistudio.google.com)

</div>

---

## Как это работает

```
Риелтор задаёт параметры клиента (район, бюджет, метраж)
        ↓
Playwright открывает Krisha.kz от имени аккаунта риелтора
        ↓
Gemini анализирует каждое объявление — цена адекватна? стоит писать?
        ↓
По одобренным — агент пишет сообщение продавцу
        ↓
Риелтор видит все результаты в дашборде
```

## Стек

| Компонент | Технология |
|-----------|-----------|
| Бэкенд | FastAPI + Python 3.11 |
| Браузерная автоматизация | Playwright (Chromium) |
| AI мозг | Google Gemini API |
| База данных | SQLite (локально) |
| Интерфейс | HTML / CSS / JS |
| Десктоп | PyInstaller → .app / .exe |

## Запуск

### Из исходников

```bash
git clone https://github.com/unsaiddream/nestify
cd nestify
pip install -r requirements.txt
playwright install chromium
python main.py
```

Откроется браузер на `http://localhost:8000`.

### Готовые сборки

Скачай из [Releases](https://github.com/unsaiddream/nestify/releases):

| Платформа | Файл |
|-----------|------|
| 🍎 macOS | `Nestify.dmg` |
| 🪟 Windows | `Nestify-Setup.exe` |

> **macOS:** если появится «повреждён» — выполни в Terminal:
> ```bash
> xattr -cr /Applications/Nestify.app
> ```

## Структура проекта

```
nestify/
├── main.py              # точка входа
├── api/
│   ├── server.py        # FastAPI приложение
│   └── routes/          # auth, agent, listings
├── agent/
│   ├── browser.py       # Playwright — поиск, отправка сообщений
│   ├── gemini.py        # Gemini API — анализ объявлений
│   └── analyzer.py      # логика агента
├── database/
│   └── db.py            # SQLite
├── ui/                  # фронтенд
└── docs/                # GitHub Pages демо
```

## Важно

- Агент действует **от имени аккаунта риелтора** — как CRM-система
- Gemini токен хранится **локально** в SQLite, никуда не отправляется
- Между действиями есть **задержки** — не похоже на бота
- Поддержка **нескольких клиентов** одновременно
- Города: Алматы, Астана, Шымкент, Актобе, Атырау, Павлодар и др.

---

<div align="center">
  <sub>Сделано для риелторов Казахстана · Всё локально · Никаких облаков</sub>
</div>
