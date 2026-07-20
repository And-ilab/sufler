import { Button, Card, Fab, HintCard, Sidebar, StatusBadge } from './components'
import './App.css'

const navItems = [
  { label: 'Диалоги', href: '#dialogs', active: true },
  { label: 'Подсказки', href: '#hints' },
  { label: 'Отчёты', href: '#reports' },
]

function App() {
  return (
    <div className="app-shell">
      <Sidebar items={navItems} />
      <main className="app-main">
        <header className="app-header">
          <div>
            <p className="app-eyebrow">Рабочее место оператора</p>
            <h1>Активный диалог</h1>
          </div>
          <StatusBadge status="success">В сети</StatusBadge>
        </header>

        <Card>
          <h2>Иван Петров</h2>
          <p className="app-muted">Клиент уточняет условия выпуска платёжной карты.</p>
          <div className="app-actions">
            <Button>Ответить</Button>
            <Button variant="secondary">Завершить</Button>
            <Button variant="ghost">Передать</Button>
          </div>
        </Card>

        <HintCard title="Рекомендуемый ответ">
          Для оформления карты потребуется паспорт. Заявку можно подать в отделении
          или через интернет-банкинг. Срок выпуска зависит от выбранного продукта.
        </HintCard>
      </main>
      <div className="app-fab">
        <Fab aria-label="Открыть чат" badge={2}>💬</Fab>
      </div>
    </div>
  )
}

export default App
