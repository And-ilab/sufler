# Frontend foundation

Базовый UI-слой Суфлёра: Vite, React, TypeScript, Tailwind CSS, Storybook и
визуальные тесты Playwright.

## Требования

- актуальная LTS-версия Node.js;
- npm из поставки Node.js.

## Команды

```bash
npm install
npm run dev
npm run lint
npm run build
```

Storybook:

```bash
npm run storybook
npm run build-storybook
```

Визуальные тесты:

```bash
npm run playwright:install
npm run test:visual
npm run test:visual:update
```

`test:visual:update` разрешено запускать только после осознанной проверки
изменений UI. Обновлённые PNG нужно просмотреть в diff и приложить к review.

## Структура

- `src/tokens.css` — брендовые, семантические, spacing и shadow tokens;
- `src/components` — компоненты, их стили, barrel export и stories;
- `.storybook` — конфигурация каталога компонентов;
- `../tests/ui` — Playwright visual tests и эталонные PNG;
- `public/assets` — статические канонические assets.

Обязательные брендовые значения определены только через tokens:
`--color-primary: #0D3880`, `--color-primary-dark: #0A2A66`,
`--color-secondary: #E31E24`, `--radius: 8px`.

Логотип `public/assets/belarusbank-logo.png` скопирован из канонического
`canvases/assets/belarusbank-logo.png`. Канонический PNG извлечён без
преобразований из `BELARUSBANK_LOGO_DATA_URL` в
`canvases/online-chat-mockups.canvas.tsx`; исходный canvas не изменяется.

## UI WORKFLOW

1. Проверить требования в `docs/ui` и актуальную спецификацию v1.4.
2. Добавить или уточнить tokens, не встраивая брендовые цвета в компоненты.
3. Реализовать доступный типизированный компонент в `src/components`.
4. Добавить отдельную Storybook story для состояний компонента.
5. Создать или осознанно обновить visual baseline.
6. На PR review проверить API, доступность, stories и PNG-diff.

Изменение baseline без соответствующего изменения компонента или tokens
считается ошибкой. Генерируемые `storybook-static`, `node_modules`,
Playwright reports и test results не коммитятся.
