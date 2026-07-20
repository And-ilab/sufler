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

## Портальный launcher I-0

`src/components/PortalLauncher.tsx` реализует основной вариант I.5:

- кнопка AI 56×56 px в правом нижнем углу;
- меню выбора «Суфлёр | Ассистент»;
- одновременное открытие двух независимых окон;
- сворачивание, закрытие, разворачивание и drag-resize окон;
- standalone routes `/sufler` и `/assistant`;
- скрытие launcher и защита routes по ролям I.4.

В приложении роли загружаются из `GET /api/auth/me/`. Vite проксирует `/api`
на Django `http://127.0.0.1:8000`. Если backend недоступен или пользователь не
авторизован, launcher не отображается. Только для локальной разработки можно
задать роли через запятую:

```powershell
$env:VITE_DEV_RBAC_ROLES="contact_center_telephony_operator"
npm run dev
```

Storybook states:

- `Portal/Launcher / Menu Open` — visual baseline I-0;
- `Portal/Launcher / Both Windows` — параллельная работа;
- `Portal/Launcher / Unauthorized` — RBAC-hidden state.

Baseline `tests/ui/__snapshots__/portal-launcher-menu.png` обновляется только
через `npm run test:visual:update` после проверки canvas I-0 и PNG diff.

## Admin center

Маршрут `/ai-hub/admin/` реализован в `src/ai-hub/admin/` по
`ai-hub-settings-mockup`: полноэкранная оболочка, sidebar 240 px с группами,
breadcrumbs и sticky footer «Сохранить». Все 18 screen id доступны как
`/ai-hub/admin/<screen_id>`; профиль КЦ параметров модели использует
`/ai-hub/admin/model_params/cc`.

Production-навигация фильтруется по административным ролям I.4. Переключатель
«Демо роль» включён только в dev/Storybook и не повышает реальные права.
Story `AI Hub/Admin Shell / Default` является основой visual review для
последующих задач P2-04, P3-03, P3-05, P4-03, P4-07 и P5-03.

Экран `Параметры модели LLM` использует API
`/api/admin/model-registry/model-params/`. Форма содержит sliders generation,
chunk/overlap и retrieval thresholds, показывает inline validation и сохраняет
данные в Django DB. Story `AI Hub/Admin Shell / Model Parameters` и baseline
`model-params-form.png` фиксируют layout.

## AI Hub panel

Маршрут `/ai-hub` рендерит host из `src/ai-hub/panel/`: FAB 56 px,
slide-in panel 400 px, pin/minimize/close и вкладки «Ассистент», «Документы»,
«Суфлёр». Вкладки скрываются по I.4 RBAC; `sufler_chat` не даёт вкладку Hub.
При `callActive` tab bar блокируется на единственной вкладке «Суфлёр».

Storybook states: default assistant, documents-only, active call и closed FAB.
HintCard в «Суфлёре» использует общий compact/expand-in-place pattern.
