import { useCallback, useEffect, useMemo, useRef, useState, type CSSProperties, type JSX, type ReactNode } from 'react'
import type { ArmTheme } from './theme'
import {
  acceptDialog,
  attachmentDownloadUrl,
  blockDialogRemote,
  closeDialogRemote,
  deleteMessageRemote,
  dialogRefCode,
  editMessageRemote,
  fetchClientHistory,
  formatWaitMmSs,
  getDialog,
  liftClientBlock,
  listClientBlocks,
  listDialogs,
  markDialogRead,
  maskPhone,
  onlineChatArmWsUrl,
  REPLY_TEMPLATES,
  sendOperatorMessage,
  slaToneFromSeconds,
  transferDialogRemote,
  uploadOperatorAttachment,
  type ClientHistoryItem,
  type OnlineChatDialog,
  type OnlineChatMessage,
  type ReceiptStatus,
  type SlaTone,
} from '../api/onlineChatApi'
import { operatorsApi } from '../api/managementApi'
import {
  Button,
  Callout,
  Card,
  CardBody,
  CardHeader,
  Divider,
  Grid,
  H3,
  IconButton,
  Link,
  Pill,
  Row,
  Select,
  Spacer,
  Stack,
  Text,
  TextArea,
} from './primitives'

const CANVAS_MOCKUP_VERSION = 'v1.4.74'

export type OperatorPresence =
  | "online"
  | "invisible"
  | "break"
  | "lunch"
  | "tech_break"
  | "training"
  | "meeting"
  | "offline_queue"
  | "offline";
type OperatorStatusShadeKey =
  | "available"
  | "invisible"
  | "break"
  | "lunch"
  | "tech_break"
  | "training"
  | "meeting"
  | "offline_queue"
  | "offline";

type StatusShadeStyle = {
  background: string;
  color: string;
  border: string;
  borderLeft: string;
};

const OPERATOR_STATUSES: {
  id: OperatorPresence;
  label: string;
  shadeKey: OperatorStatusShadeKey;
  tone: "success" | "warning" | "neutral" | "info";
}[] = [
  { id: "online", label: "в сети", shadeKey: "available", tone: "success" },
  { id: "invisible", label: "невидимка", shadeKey: "invisible", tone: "neutral" },
  { id: "break", label: "перерыв", shadeKey: "break", tone: "warning" },
  { id: "lunch", label: "обед", shadeKey: "lunch", tone: "warning" },
  { id: "tech_break", label: "техперерыв", shadeKey: "tech_break", tone: "warning" },
  { id: "training", label: "обучение", shadeKey: "training", tone: "info" },
  { id: "meeting", label: "встреча", shadeKey: "meeting", tone: "info" },
  { id: "offline_queue", label: "офлайн-обращения", shadeKey: "offline_queue", tone: "info" },
  { id: "offline", label: "не в сети", shadeKey: "offline", tone: "neutral" },
];

/** Per-status tint: inactive = light bg + colored text/left border; active = stronger fill + border on same hue. */
function operatorStatusShade(
  t: ArmTheme,
  key: OperatorStatusShadeKey,
): { inactive: StatusShadeStyle; active: StatusShadeStyle } {
  const light = t.kind === "light";
  const map: Record<OperatorStatusShadeKey, { inactive: StatusShadeStyle; active: StatusShadeStyle }> = light
    ? {
        available: {
          inactive: { background: "#e8f5e9", color: "#2e7d32", border: "#2e7d3240", borderLeft: "#2e7d32" },
          active: { background: "#1B8F4A", color: "#FFFFFF", border: "#146C38", borderLeft: "#0F5A2E" },
        },
        invisible: {
          inactive: { background: "#f3e5f5", color: "#6a1b9a", border: "#6a1b9a40", borderLeft: "#6a1b9a" },
          active: { background: "#7B1FA2", color: "#FFFFFF", border: "#6A1B9A", borderLeft: "#4A148C" },
        },
        break: {
          inactive: { background: "#fff8e1", color: "#f57f17", border: "#f57f1740", borderLeft: "#f57f17" },
          active: { background: "#F57C00", color: "#FFFFFF", border: "#E65100", borderLeft: "#BF360C" },
        },
        tech_break: {
          inactive: { background: "#fff3e0", color: "#e65100", border: "#e6510040", borderLeft: "#e65100" },
          active: { background: "#E64A19", color: "#FFFFFF", border: "#BF360C", borderLeft: "#8D2B0A" },
        },
        lunch: {
          inactive: { background: "#fffde7", color: "#f9a825", border: "#f9a82540", borderLeft: "#f9a825" },
          active: { background: "#F9A825", color: "#FFFFFF", border: "#F57F17", borderLeft: "#E65100" },
        },
        training: {
          inactive: { background: "#e0f2f1", color: "#00695c", border: "#00695c40", borderLeft: "#00695c" },
          active: { background: "#00897B", color: "#FFFFFF", border: "#00695C", borderLeft: "#004D40" },
        },
        meeting: {
          inactive: { background: "#e8eaf6", color: "#3949ab", border: "#3949ab40", borderLeft: "#3949ab" },
          active: { background: "#3949AB", color: "#FFFFFF", border: "#283593", borderLeft: "#1A237E" },
        },
        offline_queue: {
          inactive: { background: "#e3f2fd", color: "#1565c0", border: "#1565c040", borderLeft: "#1565c0" },
          active: { background: "#1565C0", color: "#FFFFFF", border: "#0D47A1", borderLeft: "#0A3A84" },
        },
        offline: {
          inactive: { background: "#eceff1", color: "#546e7a", border: "#546e7a40", borderLeft: "#546e7a" },
          active: { background: "#546E7A", color: "#FFFFFF", border: "#37474F", borderLeft: "#263238" },
        },
      }
    : {
        available: {
          inactive: { background: "#1F8A6524", color: "#6FD4A0", border: "#3FA26655", borderLeft: "#3FA266" },
          active: { background: "#2E9E68", color: "#FFFFFF", border: "#52B896", borderLeft: "#6FD4A0" },
        },
        invisible: {
          inactive: { background: "#6A1B9A24", color: "#CE93D8", border: "#6A1B9A55", borderLeft: "#AB47BC" },
          active: { background: "#9C27B0", color: "#FFFFFF", border: "#CE93D8", borderLeft: "#E1BEE7" },
        },
        break: {
          inactive: { background: "#F57F1724", color: "#FFB74D", border: "#F57F1755", borderLeft: "#FFB74D" },
          active: { background: "#FB8C00", color: "#FFFFFF", border: "#FFB74D", borderLeft: "#FFCC80" },
        },
        tech_break: {
          inactive: { background: "#E6510024", color: "#FFAB91", border: "#E6510055", borderLeft: "#FF7043" },
          active: { background: "#F4511E", color: "#FFFFFF", border: "#FF8A65", borderLeft: "#FFAB91" },
        },
        lunch: {
          inactive: { background: "#F9A82524", color: "#FFD54F", border: "#F9A82555", borderLeft: "#FFCA28" },
          active: { background: "#FBC02D", color: "#1A1A1A", border: "#FFD54F", borderLeft: "#FFECB3" },
        },
        training: {
          inactive: { background: "#00695C24", color: "#4DB6AC", border: "#00695C55", borderLeft: "#26A69A" },
          active: { background: "#00897B", color: "#FFFFFF", border: "#4DB6AC", borderLeft: "#80CBC4" },
        },
        meeting: {
          inactive: { background: "#3949AB24", color: "#7986CB", border: "#3949AB55", borderLeft: "#5C6BC0" },
          active: { background: "#5C6BC0", color: "#FFFFFF", border: "#7986CB", borderLeft: "#9FA8DA" },
        },
        offline_queue: {
          inactive: { background: "#1565C024", color: "#64B5F6", border: "#1565C055", borderLeft: "#42A5F5" },
          active: { background: "#1E88E5", color: "#FFFFFF", border: "#64B5F6", borderLeft: "#90CAF9" },
        },
        offline: {
          inactive: { background: "#546E7A24", color: "#90A4AE", border: "#546E7A55", borderLeft: "#78909C" },
          active: { background: "#607D8B", color: "#FFFFFF", border: "#90A4AE", borderLeft: "#B0BEC5" },
        },
      };
  return map[key];
}

function OperatorStatusPill({
  t,
  status,
  active = false,
  size = "sm",
  onClick,
}: {
  t: ArmTheme;
  status: (typeof OPERATOR_STATUSES)[number];
  active?: boolean;
  size?: "sm" | "md";
  onClick?: () => void;
}): JSX.Element {
  const [hovered, setHovered] = useState(false);
  const shade = operatorStatusShade(t, status.shadeKey)[active ? "active" : "inactive"];
  return (
    <button
      type="button"
      className="arm-status-pill"
      aria-pressed={active}
      onClick={onClick}
      onMouseEnter={() => setHovered(true)}
      onMouseLeave={() => setHovered(false)}
      style={{
        fontFamily: "inherit",
        fontSize: size === "sm" ? 11 : 13,
        lineHeight: 1.3,
        padding: size === "sm" ? "3px 9px 3px 7px" : "5px 12px 5px 10px",
        borderRadius: 9999,
        cursor: onClick ? "pointer" : "default",
        border: `1px solid ${shade.border}`,
        borderLeft: size === "sm" ? `2px solid ${shade.borderLeft}` : `3px solid ${shade.borderLeft}`,
        background: shade.background,
        color: shade.color,
        fontWeight: active ? 700 : hovered ? 600 : 500,
        whiteSpace: "nowrap",
        flexShrink: 0,
        boxShadow: active ? "0 1px 4px rgba(0,0,0,0.18)" : undefined,
      }}
    >
      {status.label}
    </button>
  );
}
type ArmView = "active" | "colleague";
type ArmStatsTab =
  | "dialogs"
  | "history"
  | "stats"
  | "colleagues"
  | "internal"
  | "templates"
  | "settings"
  | "help";
type ArmRole = "operator" | "supervisor" | "admin";

const ARM_ROLE_LABELS: Record<ArmRole, string> = {
  operator: "Оператор КЦ",
  supervisor: "Супервизор",
  admin: "Администратор",
};

/** Overlay menu stubs aligned with TZ II.5 / АРМ (no real navigation yet). */
const ARM_MENU_ITEMS: { id: ArmStatsTab; label: string; hint: string; roles: ArmRole[] }[] = [
  { id: "dialogs", label: "Диалоги", hint: "Очереди и активная переписка", roles: ["operator", "supervisor", "admin"] },
  { id: "history", label: "История обращений", hint: "Единая история клиента", roles: ["operator", "supervisor", "admin"] },
  { id: "stats", label: "Статистика смены", hint: "Личные показатели оператора", roles: ["operator", "supervisor", "admin"] },
  { id: "colleagues", label: "Диалоги коллег", hint: "Просмотр без ответа", roles: ["operator", "supervisor", "admin"] },
  { id: "internal", label: "Внутренний чат", hint: "Переписка между операторами", roles: ["operator", "supervisor", "admin"] },
  { id: "templates", label: "Шаблоны ответов", hint: "Быстрые заготовки", roles: ["operator", "supervisor", "admin"] },
  { id: "settings", label: "Настройки АРМ", hint: "Тема, уведомления, звук", roles: ["operator", "supervisor", "admin"] },
  { id: "help", label: "Справка", hint: "Краткая инструкция по АРМ", roles: ["operator", "supervisor", "admin"] },
];

function armMenuItemsForRole(role: ArmRole) {
  return ARM_MENU_ITEMS.filter((item) => item.roles.includes(role));
}

function firstArmStatsTabForRole(role: ArmRole): ArmStatsTab {
  return armMenuItemsForRole(role)[0]?.id ?? "dialogs";
}

export type ColorScheme =
  | "default"
  | "belarusbank_classic"
  | "belarusbank_soft"
  | "belarusbank_emerald"
  | "belarusbank_night";
export const COLOR_SCHEME_ORDER: ColorScheme[] = [
  "default",
  "belarusbank_classic",
  "belarusbank_soft",
  "belarusbank_emerald",
  "belarusbank_night",
];
const ARM_LEFT_WIDTH_MIN = 180;
const ARM_LEFT_WIDTH_MAX = 380;
const ARM_LEFT_WIDTH_DEFAULT = 220;
const ARM_RIGHT_WIDTH_MIN = 220;
const ARM_RIGHT_WIDTH_MAX = 420;
const ARM_RIGHT_WIDTH_DEFAULT = 260;
export const CLOSE_TOPICS = [
  "Карты и счета",
  "Платежи и переводы",
  "Мобильный банк",
  "Кредиты",
  "Ипотека",
  "Вклады",
  "Юрлица",
  "Блокировка / безопасность",
  "Техническая поддержка",
  "Прочее",
];

/** Fallback roster if operators API is unavailable. */
export const TRANSFER_OPERATORS = [
  "Петрова А.С.",
  "Сидоров М.В.",
  "Козлов Д.А.",
  "Морозова Е.И.",
  "Васильев Н.П.",
];

export type SchemePalette = {
  label: string;
  accent: string;
  accentWeak: string;
  accentControl: string;
  headerBg: string;
  panelBg: string;
  badge: string;
};

export function getSchemePalette(theme: ArmTheme, scheme: ColorScheme): SchemePalette {
  const isLight = theme.kind === "light";

  if (scheme === "belarusbank_classic") {
    return isLight
      ? {
          label: "Беларусбанк Classic",
          accent: "#0C4DA2",
          accentWeak: "#BFD3F3",
          accentControl: "#0A3F87",
          headerBg: "linear-gradient(135deg, #EAF2FF 0%, #DCEAFF 55%, #F4F8FF 100%)",
          panelBg: "linear-gradient(180deg, #F7FAFF 0%, #EDF4FF 100%)",
          badge: "#C62828",
        }
      : {
          label: "Беларусбанк Classic",
          accent: "#6AA8F0",
          accentWeak: "#2A4570",
          accentControl: "#8BBCF5",
          headerBg: "linear-gradient(135deg, #15253D 0%, #1A2F4A 55%, #182433 100%)",
          panelBg: "linear-gradient(180deg, #121A28 0%, #152235 100%)",
          badge: "#EF5350",
        };
  }
  if (scheme === "belarusbank_soft") {
    return isLight
      ? {
          label: "Беларусбанк Soft",
          accent: "#2E5AAC",
          accentWeak: "#C8D6EF",
          accentControl: "#2A4F93",
          headerBg: "linear-gradient(135deg, #F3F7FF 0%, #EAF1FF 58%, #FDFEFF 100%)",
          panelBg: "linear-gradient(180deg, #FAFCFF 0%, #F1F6FF 100%)",
          badge: "#D46A6A",
        }
      : {
          label: "Беларусбанк Soft",
          accent: "#8AA8E0",
          accentWeak: "#2C3A58",
          accentControl: "#A4BAE8",
          headerBg: "linear-gradient(135deg, #1A2233 0%, #1F2A40 58%, #181F2C 100%)",
          panelBg: "linear-gradient(180deg, #141A26 0%, #1A2434 100%)",
          badge: "#E08080",
        };
  }
  if (scheme === "belarusbank_emerald") {
    return isLight
      ? {
          label: "Беларусбанк Emerald",
          accent: "#007A43",
          accentWeak: "#BEE8D5",
          accentControl: "#00663A",
          headerBg: "linear-gradient(135deg, #EAF8F1 0%, #DCF3E8 58%, #F2FBF6 100%)",
          panelBg: "linear-gradient(180deg, #F5FCF8 0%, #EAF7F1 100%)",
          badge: "#0B9E5E",
        }
      : {
          label: "Беларусбанк Emerald",
          accent: "#6FD4A0",
          accentWeak: "#244A38",
          accentControl: "#8EE0B4",
          headerBg: "linear-gradient(135deg, #1A3428 0%, #214835 58%, #1C3A2C 100%)",
          panelBg: "linear-gradient(180deg, #173028 0%, #1E3C30 100%)",
          badge: "#52B896",
        };
  }
  if (scheme === "belarusbank_night") {
    return isLight
      ? {
          label: "Беларусбанк Night",
          accent: "#0D5C86",
          accentWeak: "#C5D9E6",
          accentControl: "#0A4D70",
          headerBg: "linear-gradient(135deg, #E8F1F8 0%, #D8E8F4 60%, #EFF6FB 100%)",
          panelBg: "linear-gradient(180deg, #F3F8FC 0%, #E6F1F8 100%)",
          badge: "#2D7FB8",
        }
      : {
          label: "Беларусбанк Night",
          accent: "#5BA4D4",
          accentWeak: "#1A3344",
          accentControl: "#7AB8DE",
          headerBg: "linear-gradient(135deg, #122430 0%, #173040 60%, #142028 100%)",
          panelBg: "linear-gradient(180deg, #0F1C24 0%, #152A36 100%)",
          badge: "#4A9AD0",
        };
  }
  return {
    label: "Текущая",
    accent: theme.accent.primary,
    accentWeak: theme.stroke.secondary,
    accentControl: theme.accent.control,
    headerBg: theme.fill.tertiary,
    panelBg: theme.bg.elevated,
    badge: theme.palette.diffStripRemoved,
  };
}
const RADIUS_SM = 6;
const RADIUS_MD = 8;
type QueueItem = {
  id: string;
  name: string;
  channel: string;
  dept: string;
  preview: string;
  wait: string;
  urgent: boolean;
  active?: boolean;
  result?: "offline" | "closed" | "declined";
  operatorName?: string;
  readOnly?: boolean;
  /** True when item comes from Django online_chat API (not canvas mock). */
  live?: boolean;
  phone?: string;
  firstName?: string;
  lastName?: string;
  slaTone?: SlaTone;
  clientOnline?: boolean;
  initiatedBy?: string;
  refCode?: string;
  needsReply?: boolean;
};

function slaToneColor(tone?: SlaTone): string {
  if (tone === "critical") return "#E53935";
  if (tone === "warn") return "#F9A825";
  return "#2E7D32";
}

function SlaWaitPill({ wait, slaTone }: { wait: string; slaTone?: SlaTone }): JSX.Element {
  const color = slaToneColor(slaTone);
  return (
    <span
      style={{
        fontSize: 11,
        padding: "2px 6px",
        borderRadius: 4,
        background: `${color}18`,
        color,
        border: `1px solid ${color}40`,
        fontWeight: 600,
        lineHeight: 1.3,
        flexShrink: 0,
      }}
    >
      {wait}
    </span>
  );
}

function dialogToQueueItem(
  dialog: OnlineChatDialog,
  options?: { active?: boolean },
): QueueItem {
  const needsReply = dialog.needs_reply ?? false;
  const waitSeconds = needsReply ? dialog.wait_seconds : 0;
  const slaTone = needsReply ? slaToneFromSeconds(waitSeconds) : "ok";
  return {
    id: dialog.id,
    name: dialog.client_name || "Клиент",
    channel: dialog.channel === "widget" ? "Сайт" : dialog.channel,
    dept: "Розничные продукты",
    preview: dialog.preview || "—",
    wait: needsReply ? formatWaitMmSs(waitSeconds) : "—",
    urgent: needsReply && slaTone === "critical",
    slaTone,
    active: options?.active,
    live: true,
    phone: dialog.client_phone,
    firstName: dialog.client_first_name,
    lastName: dialog.client_last_name,
    operatorName: dialog.operator_name || undefined,
    clientOnline: dialog.client_online,
    initiatedBy: dialog.initiated_by,
    refCode: dialogRefCode(dialog),
    needsReply,
  };
}

function messageTimeLabel(iso: string): string {
  try {
    return new Date(iso).toLocaleTimeString("ru-RU", {
      hour: "2-digit",
      minute: "2-digit",
    });
  } catch {
    return "";
  }
}

function initialsFromDisplayName(name: string): string {
  return name
    .split(/\s+/)
    .map((part) => part[0] ?? "")
    .join("")
    .slice(0, 2)
    .toUpperCase();
}

const QUEUE: QueueItem[] = [
  {
    id: "1",
    name: "Анна Козлова",
    channel: "Сайт",
    dept: "Розничные продукты",
    preview: "Подскажите лимит снятия наличных в банкомате?",
    wait: "02:14",
    urgent: true,
    active: true,
  },
  {
    id: "2",
    name: "Пётр Мельников",
    channel: "Telegram",
    dept: "Розничные продукты",
    preview: "Не приходит SMS для подтверждения операции",
    wait: "00:45",
    urgent: false,
  },
  {
    id: "3",
    name: "ООО «Вектор»",
    channel: "Сайт",
    dept: "Юрлица",
    preview: "Тарифы на РКО для ИП",
    wait: "00:12",
    urgent: false,
  },
];

const MY_DIALOGUES: QueueItem[] = [
  {
    id: "m1",
    name: "Светлана Р.",
    channel: "Viber",
    dept: "Розничные продукты",
    preview: "Когда будет готов перевод SWIFT?",
    wait: "04:32",
    urgent: false,
    active: true,
  },
  {
    id: "m2",
    name: "Дмитрий В.",
    channel: "Сайт",
    dept: "Ипотека",
    preview: "Уточните ставку по ипотеке «Моя квартира»",
    wait: "01:08",
    urgent: false,
  },
];

const OFFLINE_QUEUE: QueueItem[] = [
  {
    id: "o1",
    name: "Пётр Мельников",
    channel: "Telegram",
    dept: "Розничные продукты",
    preview: "Не приходит SMS для подтверждения операции",
    wait: "—",
    urgent: false,
    result: "offline",
  },
];

const CLOSED_QUEUE: QueueItem[] = [
  {
    id: "l1",
    name: "ООО «Вектор»",
    channel: "Сайт",
    dept: "Юрлица",
    preview: "Тарифы на РКО для ИП",
    wait: "—",
    urgent: false,
    result: "closed",
  },
];

const INITIATED_QUEUE: QueueItem[] = [
  {
    id: "i1",
    name: "Елена С.",
    channel: "Сайт",
    dept: "Розничные продукты",
    preview: "Исходящее: напоминание о платеже",
    wait: "00:05",
    urgent: false,
  },
];

const SHARED_QUEUE: QueueItem[] = [
  {
    id: "s1",
    name: "Марина Т.",
    channel: "Сайт",
    dept: "Розничные продукты",
    preview: "Как подключить SMS-информирование?",
    wait: "03:55",
    urgent: true,
  },
  {
    id: "s2",
    name: "ИП Ковалёв",
    channel: "Telegram",
    dept: "Юрлица",
    preview: "Запрос выписки по расчётному счёту",
    wait: "02:40",
    urgent: false,
  },
];

const COLLEAGUE_DIALOGUES: QueueItem[] = [
  {
    id: "c1",
    name: "Анна Козлова",
    channel: "Сайт",
    dept: "Розничные продукты",
    preview: "Подскажите лимит снятия наличных в банкомате?",
    wait: "02:14",
    urgent: true,
    operatorName: "Петрова А.С.",
    readOnly: true,
  },
  {
    id: "c2",
    name: "Дмитрий В.",
    channel: "Viber",
    dept: "Ипотека",
    preview: "Уточните ставку по ипотеке «Моя квартира»",
    wait: "01:08",
    urgent: false,
    operatorName: "Сидоров М.В.",
    readOnly: true,
  },
  {
    id: "c3",
    name: "Марина Т.",
    channel: "Telegram",
    dept: "Розничные продукты",
    preview: "Как подключить SMS-информирование?",
    wait: "03:55",
    urgent: false,
    operatorName: "Петрова А.С.",
    readOnly: true,
  },
];

type QueueSectionId =
  | "waiting"
  | "mine"
  | "colleagues"
  | "offline"
  | "closed"
  | "shared"
  | "initiated";

type QueueSectionDef = {
  id: QueueSectionId;
  title: string;
  count: number;
  items: QueueItem[];
  defaultExpanded: boolean;
};

const QUEUE_SECTIONS: QueueSectionDef[] = [
  { id: "waiting", title: "Ожидают ответа", count: 3, items: QUEUE, defaultExpanded: true },
  { id: "mine", title: "В диалоге со мной", count: 2, items: MY_DIALOGUES, defaultExpanded: true },
  { id: "offline", title: "Офлайн", count: 1, items: OFFLINE_QUEUE, defaultExpanded: false },
  { id: "closed", title: "Недавно закрытые", count: 1, items: CLOSED_QUEUE, defaultExpanded: false },
  { id: "shared", title: "Общая очередь", count: 5, items: SHARED_QUEUE, defaultExpanded: false },
  { id: "initiated", title: "Инициированные мной", count: 1, items: INITIATED_QUEUE, defaultExpanded: false },
];

const COLLEAGUES_SECTION: QueueSectionDef = {
  id: "colleagues",
  title: "Диалоги коллег",
  count: COLLEAGUE_DIALOGUES.length,
  items: COLLEAGUE_DIALOGUES,
  defaultExpanded: false,
};

function queueSectionsForRole(role: ArmRole): QueueSectionDef[] {
  if (role === "operator" || role === "supervisor") {
    return [QUEUE_SECTIONS[0], QUEUE_SECTIONS[1], COLLEAGUES_SECTION, ...QUEUE_SECTIONS.slice(2)];
  }
  return QUEUE_SECTIONS;
}

function findSectionForQueueItem(queueId: string, sections: QueueSectionDef[]): QueueSectionDef | undefined {
  return sections.find((section) => section.items.some((item) => item.id === queueId));
}

function defaultExpandedSections(): Record<QueueSectionId, boolean> {
  const allSections = [...QUEUE_SECTIONS, COLLEAGUES_SECTION];
  return allSections.reduce(
    (acc, section) => {
      acc[section.id] = section.defaultExpanded;
      return acc;
    },
    {} as Record<QueueSectionId, boolean>,
  );
}

function allSectionsExpandedState(sections: QueueSectionDef[]): Record<QueueSectionId, boolean> {
  return sections.reduce(
    (acc, section) => {
      acc[section.id] = true;
      return acc;
    },
    {} as Record<QueueSectionId, boolean>,
  );
}

function allSectionsCollapsedState(sections: QueueSectionDef[]): Record<QueueSectionId, boolean> {
  return sections.reduce(
    (acc, section) => {
      acc[section.id] = false;
      return acc;
    },
    {} as Record<QueueSectionId, boolean>,
  );
}

function isSectionExpanded(
  expandedSections: Record<QueueSectionId, boolean>,
  section: QueueSectionDef,
): boolean {
  return expandedSections[section.id] ?? section.defaultExpanded;
}

function areAllSectionsCollapsed(
  expandedSections: Record<QueueSectionId, boolean>,
  sections: QueueSectionDef[],
): boolean {
  return sections.every((section) => !isSectionExpanded(expandedSections, section));
}

function panelStyle(t: ArmTheme, extra?: CSSProperties): CSSProperties {
  return {
    background: t.fill.secondary,
    border: `1px solid ${t.stroke.secondary}`,
    borderRadius: RADIUS_MD,
    ...extra,
  };
}

type SuflerFeedbackChoice = "used" | "not_used" | "partial";

const SUFLER_FEEDBACK_OPTIONS: { id: SuflerFeedbackChoice; label: string }[] = [
  { id: "used", label: "Воспользовался" },
  { id: "not_used", label: "Не воспользовался" },
  { id: "partial", label: "Неполный ответ" },
];

type FeedbackChipPalette = {
  idleBg: string;
  idleBorder: string;
  activeBg: string;
  activeBorder: string;
  activeColor: string;
};

/** Разноцветные чипы оценки (как в суфлёре): зелёный / сине-серый / янтарный. */
function feedbackChipPalette(t: ArmTheme, choice: SuflerFeedbackChoice): FeedbackChipPalette {
  const isLight = t.kind === "light";
  if (choice === "used") {
    return {
      idleBg: t.diff.insertedLine,
      idleBorder: isLight ? "#1F8A6533" : "#3FA26640",
      activeBg: isLight ? "#1F8A6533" : "#3FA2664D",
      activeBorder: t.palette.diffStripAdded,
      activeColor: isLight ? "#1F8A65" : "#52B896",
    };
  }
  if (choice === "not_used") {
    return {
      idleBg: isLight ? "#3685BF12" : "#599CE71A",
      idleBorder: isLight ? "#3685BF2E" : "#599CE738",
      activeBg: isLight ? "#3685BF24" : "#599CE730",
      activeBorder: isLight ? "#3685BF70" : "#599CE788",
      activeColor: t.text.primary,
    };
  }
  return {
    idleBg: isLight ? "#E8C03014" : "#E8C0301F",
    idleBorder: isLight ? "#E8C03040" : "#E8C03050",
    activeBg: isLight ? "#E8C0302E" : "#E8C03042",
    activeBorder: isLight ? "#C06028A8" : "#F0A040B3",
    activeColor: isLight ? "#8A6D00" : "#E8C030",
  };
}

function feedbackChipStyle(
  t: ArmTheme,
  choice: SuflerFeedbackChoice,
  selected: boolean,
  hovered: boolean,
  disabled: boolean,
): CSSProperties {
  const palette = feedbackChipPalette(t, choice);
  const emphasized = selected || hovered;
  return {
    display: "inline-flex",
    alignItems: "center",
    fontSize: 12,
    fontWeight: emphasized ? 600 : 500,
    padding: "5px 10px",
    borderRadius: 6,
    border: `1px solid ${emphasized ? palette.activeBorder : palette.idleBorder}`,
    background: emphasized ? palette.activeBg : palette.idleBg,
    color: emphasized ? palette.activeColor : t.text.secondary,
    cursor: disabled ? "not-allowed" : "pointer",
    opacity: disabled ? 0.55 : 1,
    lineHeight: 1.25,
    whiteSpace: "nowrap",
    flexShrink: 0,
    appearance: "none",
    fontFamily: "inherit",
    outline: "none",
  };
}

function SuflerFeedbackChip({
  t,
  option,
  selected,
  disabled,
  onSelect,
}: {
  t: ArmTheme;
  option: (typeof SUFLER_FEEDBACK_OPTIONS)[number];
  selected: boolean;
  disabled?: boolean;
  onSelect: () => void;
}): JSX.Element {
  const [hovered, setHovered] = useState(false);
  return (
    <button
      type="button"
      className="arm-feedback-chip"
      disabled={disabled}
      title={option.label}
      style={feedbackChipStyle(t, option.id, selected, hovered && !disabled, !!disabled)}
      onMouseEnter={() => setHovered(true)}
      onMouseLeave={() => setHovered(false)}
      onClick={() => {
        if (disabled) return;
        onSelect();
      }}
    >
      {option.label}
    </button>
  );
}

function SuflerFeedbackRow({
  t,
  scheme: _scheme,
  cardId: _cardId,
  disabled,
}: {
  t: ArmTheme;
  scheme: SchemePalette;
  cardId: string;
  disabled?: boolean;
}): JSX.Element {
  const [selected, setSelected] = useState<SuflerFeedbackChoice | null>(null);

  return (
    <div
      style={{
        display: "flex",
        flexDirection: "row",
        flexWrap: "wrap",
        gap: 6,
        marginTop: 8,
        alignItems: "center",
      }}
    >
      {SUFLER_FEEDBACK_OPTIONS.map((option) => (
        <SuflerFeedbackChip
          key={option.id}
          t={t}
          option={option}
          selected={selected === option.id}
          disabled={disabled}
          onSelect={() => setSelected(selected === option.id ? null : option.id)}
        />
      ))}
    </div>
  );
}

function AutoFadeNotice({
  message,
  onDone,
  style,
}: {
  message: string;
  onDone: () => void;
  style?: CSSProperties;
}): JSX.Element {
  const [hiding, setHiding] = useState(false);
  const onDoneRef = useRef(onDone);
  onDoneRef.current = onDone;

  useEffect(() => {
    setHiding(false);
    const fadeTimer = window.setTimeout(() => setHiding(true), 2600);
    const clearTimer = window.setTimeout(() => onDoneRef.current(), 3500);
    return () => {
      window.clearTimeout(fadeTimer);
      window.clearTimeout(clearTimer);
    };
  }, [message]);

  return (
    <Callout
      tone="success"
      className={`arm-fade-notice${hiding ? " arm-fade-notice--hiding" : ""}`}
      style={{ marginTop: 8, fontSize: 12, ...style }}
    >
      {message}
    </Callout>
  );
}
type RelevanceTier = "high" | "mediumStrong" | "mediumLight" | "low";

function parseRelevancePercent(relevance: number | string): number {
  if (typeof relevance === "number") return relevance;
  const match = relevance.match(/(\d+(?:\.\d+)?)/);
  return match ? Number(match[1]) : 0;
}

function relevanceTierFromPercent(pct: number): RelevanceTier {
  if (pct >= 90) return "high";
  if (pct >= 85) return "mediumStrong";
  if (pct >= 80) return "mediumLight";
  return "low";
}

type RelevanceShadeStyle = {
  tier: RelevanceTier;
  tone: "success" | "warning" | "neutral";
  background: string;
  border: string;
  borderLeft: string;
};

/** Shared relevance palette: ≥90% green, 85–89% amber-strong, 80–84% amber-light, <80% neutral. */
const RELEVANCE_SHADE_COLORS = {
  high: {
    borderLight: "#2E7D3270",
    borderDark: "#3FA26688",
  },
  mediumStrong: {
    bgLight: "#E8A02030",
    bgDark: "#E8A03042",
    borderLight: "#C0602880",
    borderDark: "#F0904080",
    borderLeftLight: "#C06028CC",
    borderLeftDark: "#F0A040D9",
  },
  mediumLight: {
    bgLight: "#F0D88018",
    bgDark: "#E8C03024",
    borderLight: "#B8883850",
    borderDark: "#C8984860",
    borderLeftLight: "#B88860A0",
    borderLeftDark: "#C8A060B0",
  },
  low: {
    bgLight: "#ECEFF120",
    bgDark: "#546E7A28",
    borderLight: "#78909C66",
    borderDark: "#90A4AE77",
    borderLeftLight: "#78909C",
    borderLeftDark: "#90A4AE",
  },
} as const;

function relevanceShade(t: ArmTheme, relevance: number | string): RelevanceShadeStyle {
  const tier = relevanceTierFromPercent(parseRelevancePercent(relevance));
  const isLight = t.kind === "light";

  if (tier === "high") {
    const c = RELEVANCE_SHADE_COLORS.high;
    return {
      tier,
      tone: "success",
      background: t.diff.insertedLine,
      border: isLight ? c.borderLight : c.borderDark,
      borderLeft: t.palette.diffStripAdded,
    };
  }
  if (tier === "mediumStrong") {
    const c = RELEVANCE_SHADE_COLORS.mediumStrong;
    return {
      tier,
      tone: "warning",
      background: isLight ? c.bgLight : c.bgDark,
      border: isLight ? c.borderLight : c.borderDark,
      borderLeft: isLight ? c.borderLeftLight : c.borderLeftDark,
    };
  }
  if (tier === "mediumLight") {
    const c = RELEVANCE_SHADE_COLORS.mediumLight;
    return {
      tier,
      tone: "warning",
      background: isLight ? c.bgLight : c.bgDark,
      border: isLight ? c.borderLight : c.borderDark,
      borderLeft: isLight ? c.borderLeftLight : c.borderLeftDark,
    };
  }
  const c = RELEVANCE_SHADE_COLORS.low;
  return {
    tier,
    tone: "neutral",
    background: isLight ? c.bgLight : c.bgDark,
    border: isLight ? c.borderLight : c.borderDark,
    borderLeft: isLight ? c.borderLeftLight : c.borderLeftDark,
  };
}

/** Neutral right-panel cards: border is a more saturated tone of the field background. */
function neutralCardSurface(t: ArmTheme, isExpanded: boolean): { background: string; border: string } {
  const background = isExpanded ? t.bg.elevated : t.fill.tertiary;
  return {
    background,
    border: t.stroke.secondary,
  };
}

type SpellError = {
  word: string;
  suggestion: string;
  start: number;
  end: number;
};

/** Demo-словарь для макета: типичные опечатки оператора в теме лимитов ATM. */
const SPELL_DEMO_CORRECTIONS: Record<string, string> = {
  лимты: "лимиты",
  дебитовой: "дебетовой",
  минскаму: "минскому",
  суточны: "суточный",
  банкомате: "банкоматах",
  овет: "ответ",
};

function findSpellErrors(text: string): SpellError[] {
  const errors: SpellError[] = [];
  const wordRegex = /[а-яёА-ЯЁ]+/g;
  let match: RegExpExecArray | null;
  while ((match = wordRegex.exec(text)) !== null) {
    const suggestion = SPELL_DEMO_CORRECTIONS[match[0].toLowerCase()];
    if (suggestion) {
      errors.push({
        word: match[0],
        suggestion,
        start: match.index,
        end: match.index + match[0].length,
      });
    }
  }
  return errors;
}

function applySpellFixes(text: string, errors: SpellError[]): string {
  let result = text;
  for (const err of [...errors].sort((a, b) => b.start - a.start)) {
    result = result.slice(0, err.start) + err.suggestion + result.slice(err.end);
  }
  return result;
}

/** Демо-полировка текста без орфографических ошибок (нормализация пробелов, заглавная буква). */
function polishTextDemo(text: string): string {
  const normalized = text.replace(/\s+/g, " ").trim();
  if (normalized.length === 0) return text;
  return normalized.charAt(0).toUpperCase() + normalized.slice(1);
}

type AiImproveModalState = {
  original: string;
  improved: string;
};

function AiImprovePopover({
  t,
  scheme,
  state,
  onAccept,
  onDismiss,
}: {
  t: ArmTheme;
  scheme: SchemePalette;
  state: AiImproveModalState;
  onAccept: () => void;
  onDismiss: () => void;
}): JSX.Element {
  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-labelledby="ai-improve-title"
      style={{
        position: "absolute",
        bottom: "calc(100% + 8px)",
        left: 0,
        right: 0,
        zIndex: 100,
        background: t.bg.elevated,
        border: `1px solid ${scheme.accent}`,
        borderRadius: RADIUS_MD,
        padding: 12,
        boxSizing: "border-box",
      }}
    >
      <Row style={{ alignItems: "center", justifyContent: "space-between", gap: 8 }}>
        <Text id="ai-improve-title" weight="semibold">
          Улучшение текста
        </Text>
        <IconButton title="Закрыть" aria-label="Закрыть" onClick={onDismiss}>
          ×
        </IconButton>
      </Row>
      <div
        style={{
          marginTop: 10,
          maxHeight: 100,
          padding: "10px 12px",
          borderRadius: RADIUS_SM,
          background: t.fill.quaternary,
          border: `1px solid ${t.stroke.tertiary}`,
          overflowY: "auto",
        }}
      >
        <Text style={{ fontSize: 13, lineHeight: 1.55, whiteSpace: "pre-wrap" }}>{state.improved}</Text>
      </div>
      <Row style={{ marginTop: 12, justifyContent: "flex-end", alignItems: "center", gap: 8 }}>
        <Button variant="ghost" onClick={onDismiss}>
          Закрыть
        </Button>
        <Button variant="primary" onClick={onAccept}>
          Применить
        </Button>
      </Row>
      <Text tone="secondary" style={{ fontSize: 11, lineHeight: 1.4, textAlign: "center", marginTop: 8 }}>
        Всегда проверяйте сгенерированные сообщения перед отправкой
      </Text>
    </div>
  );
}

function spellErrorColor(t: ArmTheme): string {
  return t.kind === "light" ? "#c62828" : "#ef5350";
}

/** Подсветка опечаток и подсказки (протокол 02.07 §2.1.4 — оператор видит текст перед отправкой). */
function SpellCheckHints({
  t,
  text,
  errors,
}: {
  t: ArmTheme;
  text: string;
  errors: SpellError[];
}): JSX.Element | null {
  if (errors.length === 0) return null;
  const color = spellErrorColor(t);
  const segments: Array<{ text: string; error: boolean }> = [];
  let cursor = 0;
  for (const err of errors) {
    if (err.start > cursor) {
      segments.push({ text: text.slice(cursor, err.start), error: false });
    }
    segments.push({ text: text.slice(err.start, err.end), error: true });
    cursor = err.end;
  }
  if (cursor < text.length) {
    segments.push({ text: text.slice(cursor), error: false });
  }

  return (
    <div
      style={{
        marginTop: 4,
        padding: "6px 8px",
        borderRadius: RADIUS_SM,
        background: t.fill.quaternary,
        border: `1px solid ${t.stroke.tertiary}`,
      }}
    >
      <Text style={{ fontSize: 11, color: t.text.tertiary, marginBottom: 4 }}>Проверка орфографии</Text>
      <Text style={{ fontSize: 12, lineHeight: 1.5, whiteSpace: "pre-wrap" }}>
        {segments.map((seg, index) =>
          seg.error ? (
            <span
              key={index}
              style={{
                textDecoration: "underline wavy",
                textDecorationColor: color,
                color,
              }}
            >
              {seg.text}
            </span>
          ) : (
            <span key={index}>{seg.text}</span>
          ),
        )}
      </Text>
      <Stack gap={2} style={{ marginTop: 6 }}>
        {errors.map((err) => (
          <Text key={`${err.start}-${err.word}`} style={{ fontSize: 11, color: t.text.secondary }}>
            {err.word} → {err.suggestion}
          </Text>
        ))}
      </Stack>
    </div>
  );
}

type SuflerHintData = {
  id: string;
  title: string;
  preview: string;
  answerText: string;
  operatorTip?: string;
  relevance: string;
  relevanceTone: "success" | "neutral" | "warning";
  suzTitle: string;
  highlighted?: boolean;
};

const SUFLER_HINTS: SuflerHintData[] = [
  {
    id: "limits",
    title: "Лимиты снятия наличных",
    preview: "Суточный лимит снятия в банкоматах Беларусбанка для дебетовых карт…",
    answerText:
      "Суточный лимит снятия в банкоматах Беларусбанка для дебетовых карт составляет 2 000 BYN. Лимит обнуляется в 00:00 по минскому времени.",
    operatorTip:
      "При превышении клиент получит отказ операции — предложите альтернативу: отделение банка или безналичный перевод.",
    relevance: "94%",
    relevanceTone: "success",
    suzTitle: "Лимиты снятия наличных",
    highlighted: true,
  },
  {
    id: "atm-fees",
    title: "Комиссии ATM",
    preview: "Комиссия за снятие в банкоматах других банков — от 1,5%…",
    answerText:
      "Комиссия за снятие наличных в банкоматах других банков составляет от 1,5% от суммы, минимум 3 BYN. В банкоматах Беларусбанка для карт банка комиссия не взимается.",
    operatorTip: "Уточните тип карты и банк-эмитент перед ответом клиенту.",
    relevance: "81%",
    relevanceTone: "warning",
    suzTitle: "Комиссии банкоматов",
  },
];

type ClientInfoData = {
  name: string;
  phoneMasked: string;
  phoneFull: string;
  dialogNo: string;
  visitorId: string;
  visitTime: string;
  entryPath: string;
  entryChannel: string;
  browser: string;
  device: string;
  email: string;
  channel: string;
};

const ACTIVE_CLIENT: ClientInfoData = {
  name: "Анна Козлова",
  phoneMasked: "+375 ** ***-**-45",
  phoneFull: "+375 29 123-45-45",
  dialogNo: "№ 18 944",
  visitorId: "vis-7f3a2b1c",
  visitTime: "09.07.2026, 08:42",
  entryPath: "/cards/debit",
  entryChannel: "Виджет сайта",
  browser: "Chrome 125",
  device: "Windows 11",
  email: "anna.k@example.com",
  channel: "Сайт",
};

type SummaryHistoryData = {
  summary: string;
  detailedSummary: string;
  preview: string;
};

const EMPTY_SUMMARY_HISTORY: SummaryHistoryData = {
  summary: "История обращений пока не загружена.",
  detailedSummary: "Откройте диалог клиента, чтобы загрузить единую историю и summary.",
  preview: "Нет данных",
};

function historyToSummary(items: ClientHistoryItem[], apiSummary: string): SummaryHistoryData {
  if (!items.length) {
    return {
      summary: "Обращений по этому клиенту не найдено.",
      detailedSummary: "Нет предыдущих диалогов по телефону / внешнему ID.",
      preview: "Пусто",
    };
  }
  const latest = items[0];
  const detailed = items
    .slice(0, 8)
    .map((item) => {
      const date = item.created_at
        ? new Date(item.created_at).toLocaleString("ru-RU")
        : "—";
      const topic = item.topic || "без темы";
      const operator = item.operator_name || "не назначен";
      return `${date} · ${item.channel} · ${item.status} · ${topic} — ${operator}`;
    })
    .join("\n\n");
  return {
    summary: apiSummary || `Обращений: ${items.length}. Последнее: ${latest.channel} · ${latest.status}.`,
    detailedSummary: detailed,
    preview: latest.preview || latest.topic || latest.channel,
  };
}

function ClientInfoField({
  t,
  label,
  value,
  children,
}: {
  t: ArmTheme;
  label: string;
  value?: string;
  children?: ReactNode;
}): JSX.Element {
  return (
    <div>
      <Text style={{ fontSize: 11, color: t.text.tertiary }}>{label}</Text>
      {children ?? <Text style={{ fontSize: 12, marginTop: 2, lineHeight: 1.35 }}>{value}</Text>}
    </div>
  );
}

function EntryPointValue({
  t,
  scheme,
  entryPath,
  entryChannel,
}: {
  t: ArmTheme;
  scheme: SchemePalette;
  entryPath: string;
  entryChannel: string;
}): JSX.Element {
  const [hovered, setHovered] = useState(false);
  const href = entryPath.startsWith("http") ? entryPath : `https://belarusbank.by${entryPath}`;

  return (
    <Text style={{ fontSize: 12, marginTop: 2, lineHeight: 1.35 }}>
      <span
        onMouseEnter={() => setHovered(true)}
        onMouseLeave={() => setHovered(false)}
        style={{ display: "inline" }}
      >
        <Link
          href={href}
          style={{
            color: scheme.accentControl,
            textDecoration: hovered ? "underline" : "none",
          }}
        >
          {entryPath}
        </Link>
      </span>
      <span style={{ color: t.text.secondary }}> · {entryChannel}</span>
    </Text>
  );
}

function ClientInfoCard({
  t,
  scheme,
  client,
  isExpanded,
  onToggle,
  disabled,
}: {
  t: ArmTheme;
  scheme: SchemePalette;
  client: ClientInfoData;
  isExpanded: boolean;
  onToggle: () => void;
  disabled?: boolean;
}): JSX.Element {
  const [phoneRevealed, setPhoneRevealed] = useState(false);
  const surface = neutralCardSurface(t, isExpanded);

  return (
    <div
      role="button"
      tabIndex={0}
      aria-label={`Клиент: ${client.name}`}
      aria-expanded={isExpanded}
      style={{ marginTop: 8, outline: "none", cursor: "pointer" }}
      onClick={() => onToggle()}
      onKeyDown={(event) => {
        if (event.key === "Enter" || event.key === " ") {
          event.preventDefault();
          onToggle();
        }
      }}
    >
      <Card
        style={{
          background: surface.background,
          border: `1px solid ${surface.border}`,
        }}
      >
        <CardBody>
          {isExpanded ? (
            <Stack gap={10}>
              <Text weight="semibold">{client.name}</Text>
              <Grid columns={2} style={{ gap: 10 }}>
                <ClientInfoField t={t} label="№ диалога" value={client.dialogNo} />
                <ClientInfoField t={t} label="ID посетителя" value={client.visitorId} />
              </Grid>
              <ClientInfoField t={t} label="Время визита" value={client.visitTime} />
              <ClientInfoField t={t} label="Точка входа">
                <EntryPointValue t={t} scheme={scheme} entryPath={client.entryPath} entryChannel={client.entryChannel} />
              </ClientInfoField>
              <ClientInfoField t={t} label="Браузер / устройство" value={`${client.browser} · ${client.device}`} />
              <ClientInfoField t={t} label="Канал" value={client.channel} />
              <ClientInfoField t={t} label="E-mail" value={client.email} />
              <ClientInfoField t={t} label="Телефон">
                <Row style={{ gap: 6, alignItems: "center", marginTop: 2, flexWrap: "wrap" }}>
                  <Text style={{ fontSize: 12 }}>{phoneRevealed ? client.phoneFull : client.phoneMasked}</Text>
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={(e) => {
                      e.stopPropagation();
                      setPhoneRevealed((prev) => !prev);
                    }}
                  >
                    {phoneRevealed ? "Скрыть" : "Показать"}
                  </Button>
                </Row>
              </ClientInfoField>
              <Button
                variant="ghost"
                size="sm"
                disabled={disabled}
                onClick={(e) => e.stopPropagation()}
              >
                Изменить
              </Button>
            </Stack>
          ) : (
            <div>
              <Text weight="semibold">{client.name}</Text>
              <Text style={{ fontSize: 12, color: t.text.secondary, marginTop: 4 }}>
                {client.phoneMasked}
              </Text>
            </div>
          )}
        </CardBody>
      </Card>
    </div>
  );
}

function ClientSummaryCard({
  t,
  scheme: _scheme,
  data,
  isExpanded,
  onToggle,
  disabled: _disabled,
}: {
  t: ArmTheme;
  scheme: SchemePalette;
  data: SummaryHistoryData;
  isExpanded: boolean;
  onToggle: () => void;
  disabled?: boolean;
}): JSX.Element {
  const surface = neutralCardSurface(t, isExpanded);

  return (
    <div
      role="button"
      tabIndex={0}
      aria-label="Summary клиента"
      aria-expanded={isExpanded}
      style={{ marginTop: 8, outline: "none", cursor: "pointer" }}
      onClick={() => onToggle()}
      onKeyDown={(event) => {
        if (event.key === "Enter" || event.key === " ") {
          event.preventDefault();
          onToggle();
        }
      }}
    >
      <Card
        style={{
          background: surface.background,
          border: `1px solid ${surface.border}`,
        }}
      >
        <CardBody>
          {isExpanded ? (
            <Stack gap={8}>
              <Text weight="semibold" style={{ fontSize: 11, fontWeight: 700, color: t.text.secondary }}>
                Краткий summary
              </Text>
              <Text style={{ fontSize: 12, lineHeight: 1.5, color: t.text.primary }}>{data.summary}</Text>
              <div style={{ height: 1, background: t.stroke.tertiary }} />
              <Text weight="semibold" style={{ fontSize: 11, fontWeight: 700, color: t.text.secondary }}>
                Детальный summary
              </Text>
              <Text style={{ fontSize: 12, lineHeight: 1.55, color: t.text.primary, whiteSpace: "pre-line" }}>
                {data.detailedSummary}
              </Text>
            </Stack>
          ) : (
            <Text style={{ fontSize: 12, lineHeight: 1.4, color: t.text.secondary }}>
              {data.preview}
            </Text>
          )}
        </CardBody>
      </Card>
    </div>
  );
}

function SuflerHintCard({
  t,
  scheme,
  hint,
  isExpanded,
  onToggle,
  onInsert,
  disabled,
}: {
  t: ArmTheme;
  scheme: SchemePalette;
  hint: SuflerHintData;
  isExpanded: boolean;
  onToggle: () => void;
  onInsert: (answerText: string) => void;
  disabled?: boolean;
}): JSX.Element {
  const shade = relevanceShade(t, hint.relevance);

  return (
    <div
      role="button"
      tabIndex={0}
      aria-label={`Подсказка: ${hint.title}`}
      aria-expanded={isExpanded}
      style={{ marginTop: 8, outline: "none", cursor: "pointer" }}
      onClick={() => onToggle()}
      onKeyDown={(event) => {
        if (event.key === "Enter" || event.key === " ") {
          event.preventDefault();
          onToggle();
        }
      }}
    >
      <Card
        style={{
          background: shade.background,
          border: `1px solid ${shade.border}`,
          borderLeft: `3px solid ${shade.borderLeft}`,
        }}
      >
        <CardHeader trailing={<Pill tone={shade.tone}>{hint.relevance}</Pill>}>
          {hint.title}
        </CardHeader>
        <CardBody>
          {isExpanded ? (
            <Text style={{ fontSize: 12, lineHeight: 1.5, color: t.text.primary, marginBottom: 12 }}>
              {hint.answerText}
            </Text>
          ) : null}
          <Row gap={6} wrap>
            <Button
              variant={isExpanded || hint.highlighted ? "primary" : "secondary"}
              size="sm"
              onClick={(e) => {
                e.stopPropagation();
                onInsert(hint.answerText);
              }}
              disabled={disabled}
            >
              Вставить в ответ
            </Button>
            <Button variant="ghost" size="sm" onClick={(e) => e.stopPropagation()}>
              {hint.suzTitle} ↗
            </Button>
          </Row>
          {isExpanded && hint.operatorTip ? (
            <div
              style={{ marginTop: 18, marginBottom: 16 }}
              onClick={(e) => e.stopPropagation()}
            >
              <Callout tone="info" title="Совет оператору">
                <Text style={{ fontSize: 12, lineHeight: 1.45 }}>{hint.operatorTip}</Text>
                <Text style={{ fontSize: 10, color: t.text.tertiary, marginTop: 4 }}>
                  Не вставляется в ответ клиенту
                </Text>
              </Callout>
            </div>
          ) : null}
          {isExpanded ? (
            <div onClick={(e) => e.stopPropagation()}>
              <SuflerFeedbackRow t={t} scheme={scheme} cardId={hint.id} disabled={disabled} />
            </div>
          ) : null}
        </CardBody>
      </Card>
    </div>
  );
}

function ConfirmDialog({
  t,
  titleId,
  title,
  description,
  confirmLabel,
  onCancel,
  onConfirm,
}: {
  t: ArmTheme;
  titleId: string;
  title: string;
  description: string;
  confirmLabel: string;
  onCancel: () => void;
  onConfirm: () => void;
}): JSX.Element {
  return (
    <div
      role="presentation"
      style={{
        position: "absolute",
        inset: 0,
        background: "rgba(15, 28, 22, 0.45)",
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        zIndex: 40,
        padding: 24,
      }}
      onClick={onCancel}
    >
      <div
        role="dialog"
        aria-modal="true"
        aria-labelledby={titleId}
        style={{
          width: "100%",
          maxWidth: 420,
          background: t.bg.elevated,
          border: `1px solid ${t.stroke.secondary}`,
          borderRadius: 12,
          padding: "20px 22px",
          boxShadow: "0 12px 40px rgba(0,0,0,0.18)",
        }}
        onClick={(e) => e.stopPropagation()}
      >
        <Text
          id={titleId}
          weight="semibold"
          style={{ fontSize: 16, marginBottom: 10, color: t.text.primary }}
        >
          {title}
        </Text>
        <Text style={{ fontSize: 13, color: t.text.secondary, lineHeight: 1.45, marginBottom: 18 }}>
          {description}
        </Text>
        <Row style={{ gap: 8, justifyContent: "flex-end" }}>
          <Button variant="secondary" onClick={onCancel}>
            Отмена
          </Button>
          <Button variant="primary" onClick={onConfirm}>
            {confirmLabel}
          </Button>
        </Row>
      </div>
    </div>
  );
}

function PromptDialog({
  t,
  scheme,
  titleId,
  title,
  description,
  label,
  value,
  placeholder,
  confirmLabel,
  multiline = false,
  onChange,
  onCancel,
  onConfirm,
}: {
  t: ArmTheme;
  scheme: SchemePalette;
  titleId: string;
  title: string;
  description?: string;
  label: string;
  value: string;
  placeholder?: string;
  confirmLabel: string;
  multiline?: boolean;
  onChange: (next: string) => void;
  onCancel: () => void;
  onConfirm: () => void;
}): JSX.Element {
  const canSubmit = value.trim().length > 0;
  return (
    <div
      role="presentation"
      style={{
        position: "absolute",
        inset: 0,
        background: "rgba(15, 28, 22, 0.45)",
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        zIndex: 40,
        padding: 24,
      }}
      onClick={onCancel}
    >
      <div
        role="dialog"
        aria-modal="true"
        aria-labelledby={titleId}
        style={{
          width: "100%",
          maxWidth: 460,
          background: t.bg.elevated,
          border: `1px solid ${t.stroke.secondary}`,
          borderRadius: 12,
          padding: "20px 22px",
          boxShadow: "0 12px 40px rgba(0,0,0,0.18)",
        }}
        onClick={(e) => e.stopPropagation()}
      >
        <Text
          id={titleId}
          weight="semibold"
          style={{ fontSize: 16, marginBottom: 8, color: t.text.primary }}
        >
          {title}
        </Text>
        {description ? (
          <Text style={{ fontSize: 13, color: t.text.secondary, lineHeight: 1.45, marginBottom: 14 }}>
            {description}
          </Text>
        ) : null}
        <Text style={{ fontSize: 12, color: t.text.secondary, marginBottom: 6 }}>{label}</Text>
        {multiline ? (
          <TextArea
            value={value}
            onChange={onChange}
            placeholder={placeholder}
            style={{
              minHeight: 110,
              marginBottom: 16,
              borderColor: scheme.accentWeak,
            }}
          />
        ) : (
          <input
            value={value}
            onChange={(event) => onChange(event.target.value)}
            placeholder={placeholder}
            autoFocus
            onKeyDown={(event) => {
              if (event.key === "Enter" && canSubmit) {
                event.preventDefault();
                onConfirm();
              }
            }}
            style={{
              width: "100%",
              boxSizing: "border-box",
              marginBottom: 16,
              padding: "10px 12px",
              borderRadius: 8,
              border: `1px solid ${t.stroke.secondary}`,
              background: t.bg.editor,
              color: t.text.primary,
              fontFamily: "inherit",
              fontSize: 13,
              outline: "none",
            }}
          />
        )}
        <Row style={{ gap: 8, justifyContent: "flex-end" }}>
          <Button variant="secondary" onClick={onCancel}>
            Отмена
          </Button>
          <Button variant="primary" disabled={!canSubmit} onClick={onConfirm}>
            {confirmLabel}
          </Button>
        </Row>
      </div>
    </div>
  );
}
function clampWidth(value: number, min: number, max: number): number {
  return Math.max(min, Math.min(max, Math.round(value)));
}

function startColumnResize(
  event: { clientX: number; preventDefault: () => void },
  initialWidth: number,
  setWidth: (next: number) => void,
  min: number,
  max: number,
  invert = false,
): void {
  event.preventDefault();
  const startX = event.clientX;
  const handleMove = (moveEvent: MouseEvent) => {
    const delta = moveEvent.clientX - startX;
    setWidth(clampWidth(invert ? initialWidth - delta : initialWidth + delta, min, max));
  };
  const handleUp = () => {
    window.removeEventListener("mousemove", handleMove);
    window.removeEventListener("mouseup", handleUp);
    document.body.style.cursor = "";
    document.body.style.userSelect = "";
  };
  document.body.style.cursor = "col-resize";
  document.body.style.userSelect = "none";
  window.addEventListener("mousemove", handleMove);
  window.addEventListener("mouseup", handleUp);
}

function ColumnResizeHandle({
  t,
  label,
  onMouseDown,
}: {
  t: ArmTheme;
  label: string;
  onMouseDown: (event: { clientX: number; preventDefault: () => void }) => void;
}): JSX.Element {
  return (
    <div
      role="separator"
      aria-label={label}
      title="Перетащите для изменения ширины"
      onMouseDown={onMouseDown}
      style={{
        width: 12,
        flexShrink: 0,
        alignSelf: "stretch",
        cursor: "col-resize",
        position: "relative",
        zIndex: 5,
        touchAction: "none",
        background: t.fill.secondary,
        borderLeft: `1px solid ${t.stroke.secondary}`,
        borderRight: `1px solid ${t.stroke.secondary}`,
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
      }}
    >
      <div aria-hidden style={{ display: "flex", gap: 2, alignItems: "center", height: 24 }}>
        {[0, 1, 2].map((i) => (
          <div
            key={i}
            style={{
              width: 2,
              height: 16,
              borderRadius: 1,
              background: t.stroke.secondary,
            }}
          />
        ))}
      </div>
    </div>
  );
}
const QUEUE_CARD_COLLAPSE_SIZE = 22;
const QUEUE_CARD_COLLAPSE_INSET = 8;
const QUEUE_CARD_RIGHT_PAD = QUEUE_CARD_COLLAPSE_SIZE + QUEUE_CARD_COLLAPSE_INSET + 6;

function QueueCardCollapseButton({
  t,
  onCollapse,
}: {
  t: ArmTheme;
  onCollapse: () => void;
}): JSX.Element {
  return (
    <button
      type="button"
      title="Свернуть карточку"
      aria-label="Свернуть карточку"
      onClick={(event) => {
        event.stopPropagation();
        onCollapse();
      }}
      style={{
        position: "absolute",
        top: QUEUE_CARD_COLLAPSE_INSET,
        right: QUEUE_CARD_COLLAPSE_INSET,
        width: QUEUE_CARD_COLLAPSE_SIZE,
        height: QUEUE_CARD_COLLAPSE_SIZE,
        border: `1px solid ${t.stroke.secondary}`,
        borderRadius: RADIUS_SM,
        background: t.fill.secondary,
        color: t.text.secondary,
        fontSize: 13,
        lineHeight: 1,
        cursor: "pointer",
        padding: 0,
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        fontFamily: "inherit",
        flexShrink: 0,
        zIndex: 1,
      }}
    >
      —
    </button>
  );
}

function QueueSectionHeader({
  t,
  scheme: _scheme,
  title,
  count,
  expanded,
  onToggle,
}: {
  t: ArmTheme;
  scheme: SchemePalette;
  title: string;
  count: number;
  expanded: boolean;
  onToggle: () => void;
}): JSX.Element {
  return (
    <button
      type="button"
      onClick={onToggle}
      aria-expanded={expanded}
      style={{
        display: "flex",
        alignItems: "center",
        justifyContent: "space-between",
        width: "100%",
        padding: "6px 4px",
        marginBottom: expanded ? 6 : 2,
        border: "none",
        background: "transparent",
        cursor: "pointer",
        fontFamily: "inherit",
        borderRadius: RADIUS_SM,
      }}
    >
      <Row style={{ gap: 6, alignItems: "center", minWidth: 0 }}>
        <Text
          aria-hidden
          style={{
            fontSize: 10,
            color: t.text.secondary,
            width: 14,
            textAlign: "center",
            flexShrink: 0,
            lineHeight: 1,
            fontWeight: 700,
          }}
        >
          {expanded ? "▼" : "▶"}
        </Text>
        <Text weight="semibold" style={{ fontSize: 12, color: t.text.primary, textAlign: "left" }}>
          {title} ({count})
        </Text>
      </Row>
    </button>
  );
}

function QueueListRow({
  item,
  t,
  selected,
  onClick,
}: {
  item: QueueItem;
  t: ArmTheme;
  selected: boolean;
  onClick: () => void;
}): JSX.Element {
  const showTimer = item.wait && item.wait !== "—";

  return (
    <div
      role="button"
      tabIndex={0}
      aria-pressed={selected}
      onClick={onClick}
      onKeyDown={(e) => {
        if (e.key === "Enter" || e.key === " ") {
          e.preventDefault();
          onClick();
        }
      }}
      style={{
        display: "flex",
        alignItems: "flex-start",
        justifyContent: "space-between",
        gap: 8,
        padding: "5px 8px",
        borderBottom: `1px solid ${t.stroke.secondary}`,
        background: selected ? t.fill.tertiary : "transparent",
        cursor: "pointer",
        transition: "background 160ms ease",
      }}
    >
      <Row style={{ gap: 6, alignItems: "flex-start", minWidth: 0, flex: 1 }}>
        {item.urgent && (
          <span
            style={{
              width: 6,
              height: 6,
              borderRadius: "50%",
              background: slaToneColor(item.slaTone),
              display: "inline-block",
              flexShrink: 0,
              marginTop: 5,
            }}
          />
        )}
        <div style={{ minWidth: 0, flex: 1 }}>
          <Text
            style={{
              fontSize: 12,
              color: selected ? t.text.primary : t.text.secondary,
              overflow: "hidden",
              textOverflow: "ellipsis",
              whiteSpace: "nowrap",
            }}
          >
            {item.name}
          </Text>
          {item.readOnly ? (
            <Row style={{ gap: 4, marginTop: 2 }}>
              <Pill tone="info" size="sm">
                только просмотр
              </Pill>
            </Row>
          ) : null}
          {item.operatorName ? (
            <Text
              style={{
                fontSize: 10,
                color: t.text.tertiary,
                marginTop: 2,
                overflow: "hidden",
                textOverflow: "ellipsis",
                whiteSpace: "nowrap",
              }}
            >
              {item.operatorName}
            </Text>
          ) : null}
        </div>
      </Row>
      {showTimer ? (
        item.slaTone ? (
          <SlaWaitPill wait={item.wait} slaTone={item.slaTone} />
        ) : (
          <Pill tone={item.urgent ? "warning" : "neutral"} size="sm">
            {item.wait}
          </Pill>
        )
      ) : null}
    </div>
  );
}

function QueueCard({
  item,
  t,
  scheme,
  selected,
  onSelect,
  onCollapse,
}: {
  item: QueueItem;
  t: ArmTheme;
  scheme: SchemePalette;
  selected: boolean;
  onSelect: () => void;
  onCollapse: () => void;
}): JSX.Element {
  const showTimer = item.wait && item.wait !== "—";
  const hasMetaRow = showTimer || item.readOnly;

  return (
    <div
      role="button"
      tabIndex={0}
      aria-pressed={selected}
      onClick={onSelect}
      onKeyDown={(e) => {
        if (e.key === "Enter" || e.key === " ") {
          e.preventDefault();
          onSelect();
        }
      }}
      style={{
        position: "relative",
        padding: `10px ${QUEUE_CARD_RIGHT_PAD}px 10px 12px`,
        borderRadius: RADIUS_SM,
        border: `1px solid ${selected ? scheme.accent : t.stroke.secondary}`,
        background: selected ? t.fill.tertiary : t.bg.editor,
        cursor: "pointer",
        transition: "background 160ms ease",
      }}
    >
      <QueueCardCollapseButton t={t} onCollapse={onCollapse} />
      {hasMetaRow ? (
        <Row
          style={{
            alignItems: "center",
            gap: 6,
            marginBottom: 6,
            minHeight: QUEUE_CARD_COLLAPSE_SIZE,
            flexWrap: "wrap",
          }}
        >
          {showTimer ? (
            item.slaTone ? (
              <SlaWaitPill wait={item.wait} slaTone={item.slaTone} />
            ) : (
              <Pill tone={item.urgent ? "warning" : "neutral"} size="sm">
                {item.wait}
              </Pill>
            )
          ) : null}
          {item.readOnly ? (
            <Pill tone="info" size="sm">
              только просмотр
            </Pill>
          ) : null}
        </Row>
      ) : null}
      <Row style={{ gap: 8, alignItems: "flex-start", minWidth: 0 }}>
        {item.urgent && (
          <span
            style={{
              width: 8,
              height: 8,
              borderRadius: "50%",
              background: slaToneColor(item.slaTone),
              display: "inline-block",
              flexShrink: 0,
              marginTop: 4,
            }}
          />
        )}
        <div style={{ minWidth: 0, flex: 1 }}>
          <Text
            weight="semibold"
            style={{
              fontSize: 13,
              overflow: "hidden",
              textOverflow: "ellipsis",
              whiteSpace: "nowrap",
            }}
          >
            {item.name}
          </Text>
          {item.operatorName ? (
            <Text style={{ fontSize: 11, color: t.text.secondary, marginTop: 2 }}>{item.operatorName}</Text>
          ) : null}
        </div>
      </Row>
      <div style={{ overflow: "hidden" }}>
        <Row style={{ gap: 6, marginTop: 6, flexWrap: "wrap" }}>
          <Pill tone="info" size="sm">
            {item.channel}
          </Pill>
          {item.result && (
            <Pill
              size="sm"
              tone={
                item.result === "offline" || item.result === "closed" ? "warning" : "neutral"
              }
            >
              {item.result === "offline"
                ? "offline"
                : item.result === "closed"
                  ? "закрыт"
                  : "отказ"}
            </Pill>
          )}
          <Text style={{ fontSize: 11, color: t.text.secondary }}>{item.dept}</Text>
        </Row>
        <Text
          style={{
            fontSize: 12,
            color: t.text.secondary,
            marginTop: 6,
            overflow: "hidden",
            textOverflow: "ellipsis",
            whiteSpace: "nowrap",
          }}
        >
          {item.preview}
        </Text>
      </div>
    </div>
  );
}

function AvatarCircle({
  initials,
  background,
  color = "#fff",
}: {
  initials: string;
  background: string;
  color?: string;
}): JSX.Element {
  return (
    <div
      style={{
        width: 28,
        height: 28,
        borderRadius: 14,
        background,
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        fontSize: 10,
        fontWeight: 600,
        color,
        flexShrink: 0,
        marginTop: 2,
      }}
    >
      {initials}
    </div>
  );
}

function ReadReceiptMarks({
  color,
  status,
}: {
  color: string;
  status: ReceiptStatus;
}): JSX.Element {
  return (
    <span
      aria-label={status === "read" ? "Прочитано" : "Доставлено"}
      title={status === "read" ? "Прочитано" : "Доставлено"}
      style={{
        display: "inline-flex",
        alignItems: "center",
        marginLeft: 3,
        color,
        fontSize: 11,
        lineHeight: 1,
        fontWeight: 700,
        gap: 0,
      }}
    >
      <span aria-hidden style={{ marginRight: status === "read" ? -6 : 0 }}>
        ✓
      </span>
      {status === "read" ? <span aria-hidden>✓</span> : null}
    </span>
  );
}

function MessageBubble({
  t,
  scheme,
  side,
  text,
  time,
  label,
  avatarInitials,
  avatarColor,
  receiptStatus,
  quotedText,
  attachmentName,
  attachmentHref,
  isDeleted,
  editedAt,
  onQuote,
  onEdit,
  onDelete,
}: {
  t: ArmTheme;
  scheme: SchemePalette;
  side: "client" | "operator" | "system";
  text: string;
  time?: string;
  label?: string;
  avatarInitials?: string;
  avatarColor?: string;
  receiptStatus?: ReceiptStatus;
  quotedText?: string;
  attachmentName?: string;
  attachmentHref?: string;
  isDeleted?: boolean;
  editedAt?: string | null;
  onQuote?: () => void;
  onEdit?: () => void;
  onDelete?: () => void;
}): JSX.Element {
  if (side === "system") {
    return (
      <Text
        style={{
          textAlign: "center",
          fontSize: 11,
          color: t.text.tertiary,
          padding: "8px 0",
        }}
      >
        {text}
      </Text>
    );
  }
  const isOp = side === "operator";
  const avatarBg = avatarColor ?? (isOp ? scheme.accentControl : scheme.accentWeak);
  const avatarFg = isOp ? "#fff" : scheme.accentControl;
  const displayText = isDeleted ? "Сообщение удалено" : text;
  const hasActions = !!(onQuote || onEdit || onDelete);
  return (
    <div
      style={{
        display: "flex",
        justifyContent: isOp ? "flex-end" : "flex-start",
        gap: 8,
        alignItems: "flex-start",
      }}
    >
      {!isOp && avatarInitials ? (
        <AvatarCircle initials={avatarInitials} background={avatarBg} color={avatarFg} />
      ) : null}
      <div
        style={{
          maxWidth: "78%",
          padding: "10px 14px 8px",
          borderRadius: 12,
          borderBottomRightRadius: isOp ? 4 : 12,
          borderBottomLeftRadius: isOp ? 12 : 4,
          background: isOp ? scheme.headerBg : t.bg.editor,
          border: `1px solid ${isOp ? scheme.accent : t.stroke.secondary}`,
          display: "flex",
          flexDirection: "column",
          gap: 0,
          opacity: isDeleted ? 0.65 : 1,
        }}
      >
        {label ? (
          <Text
            style={{
              fontSize: 11,
              lineHeight: 1.3,
              color: t.text.tertiary,
              marginBottom: 6,
            }}
          >
            {label}
          </Text>
        ) : null}
        {quotedText ? (
          <div
            style={{
              fontSize: 11,
              lineHeight: 1.35,
              color: t.text.secondary,
              borderLeft: `3px solid ${scheme.accentWeak}`,
              paddingLeft: 8,
              marginBottom: 8,
              overflow: "hidden",
              textOverflow: "ellipsis",
              whiteSpace: "nowrap",
            }}
          >
            {quotedText}
          </div>
        ) : null}
        <Text
          style={{
            fontSize: 13,
            lineHeight: 1.45,
            color: t.text.primary,
            fontWeight: 600,
            fontStyle: isDeleted ? "italic" : "normal",
          }}
        >
          {displayText}
        </Text>
        {attachmentName ? (
          attachmentHref ? (
            <a
              href={attachmentHref}
              target="_blank"
              rel="noreferrer"
              style={{
                fontSize: 11,
                color: scheme.accentControl,
                marginTop: 6,
                textDecoration: "underline",
              }}
            >
              📎 {attachmentName}
            </a>
          ) : (
            <Text style={{ fontSize: 11, color: t.text.secondary, marginTop: 6 }}>
              📎 {attachmentName}
            </Text>
          )
        ) : null}
        {time || hasActions ? (
          <div
            style={{
              display: "flex",
              justifyContent: "flex-end",
              alignItems: "center",
              marginTop: 8,
              fontSize: 10,
              lineHeight: 1,
              color: t.text.tertiary,
              gap: 6,
              flexWrap: "wrap",
            }}
          >
            {hasActions ? (
              <Row style={{ gap: 4, marginRight: "auto" }}>
                {onQuote && !isDeleted ? (
                  <Button variant="ghost" size="sm" style={{ fontSize: 10, padding: "0 4px" }} onClick={onQuote}>
                    Ответить
                  </Button>
                ) : null}
                {onEdit && !isDeleted ? (
                  <Button variant="ghost" size="sm" style={{ fontSize: 10, padding: "0 4px" }} onClick={onEdit}>
                    ✎
                  </Button>
                ) : null}
                {onDelete && !isDeleted ? (
                  <Button variant="ghost" size="sm" style={{ fontSize: 10, padding: "0 4px" }} onClick={onDelete}>
                    ✕
                  </Button>
                ) : null}
              </Row>
            ) : null}
            {editedAt && !isDeleted ? (
              <span style={{ fontStyle: "italic", marginRight: 2 }}>изм.</span>
            ) : null}
            {time ? <span>{time}</span> : null}
            {receiptStatus && isOp && !isDeleted ? (
              <ReadReceiptMarks color={scheme.accentControl} status={receiptStatus} />
            ) : null}
          </div>
        ) : null}
      </div>
      {isOp && avatarInitials ? (
        <AvatarCircle initials={avatarInitials} background={avatarBg} color={avatarFg} />
      ) : null}
    </div>
  );
}

function ArmOverlayMenu({
  t,
  scheme,
  open,
  armRole,
  activeId,
  onSelect,
  onClose,
}: {
  t: ArmTheme;
  scheme: SchemePalette;
  open: boolean;
  armRole: ArmRole;
  activeId: ArmStatsTab;
  onSelect: (id: ArmStatsTab) => void;
  onClose: () => void;
}): JSX.Element {
  const items = armMenuItemsForRole(armRole);
  return (
    <div
      aria-hidden={!open}
      style={{
        position: "absolute",
        inset: 0,
        zIndex: 40,
        pointerEvents: open ? "auto" : "none",
      }}
    >
      <button
        type="button"
        aria-label="Закрыть меню"
        onClick={onClose}
        style={{
          position: "absolute",
          inset: 0,
          border: "none",
          margin: 0,
          padding: 0,
          background: open ? "rgba(20, 40, 30, 0.28)" : "transparent",
          opacity: open ? 1 : 0,
          transition: "opacity 0.22s ease",
          cursor: "pointer",
        }}
      />
      <aside
        id="arm-stats-drawer"
        role="dialog"
        aria-modal="true"
        aria-label="Меню АРМ"
        style={{
          position: "absolute",
          top: 0,
          left: 0,
          bottom: 0,
          width: "min(300px, 86vw)",
          display: "flex",
          flexDirection: "column",
          background: t.bg.elevated,
          borderRight: `1px solid ${scheme.accentWeak}`,
          boxShadow: open ? "8px 0 28px rgba(0,0,0,0.16)" : "none",
          transform: open ? "translateX(0)" : "translateX(-105%)",
          transition: "transform 0.26s cubic-bezier(0.22, 1, 0.36, 1)",
          overflow: "hidden",
        }}
      >
        <div
          style={{
            display: "flex",
            alignItems: "center",
            justifyContent: "space-between",
            gap: 10,
            padding: "14px 16px",
            background: scheme.headerBg,
            borderBottom: `1px solid ${scheme.accent}`,
          }}
        >
          <div>
            <Text weight="semibold" style={{ fontSize: 20, letterSpacing: "-0.02em" }}>Меню АРМ</Text>
          </div>
          <button
            type="button"
            aria-label="Закрыть"
            onClick={onClose}
            style={{
              width: 32,
              height: 32,
              border: `1px solid ${t.stroke.secondary}`,
              borderRadius: RADIUS_SM,
              background: t.fill.secondary,
              color: t.text.secondary,
              cursor: "pointer",
              fontSize: 18,
              lineHeight: 1,
              fontFamily: "inherit",
            }}
          >
            ×
          </button>
        </div>
        <nav
          aria-label="Разделы меню"
          style={{
            display: "flex",
            flexDirection: "column",
            gap: 8,
            padding: 12,
            overflowY: "auto",
            flex: 1,
            minHeight: 0,
          }}
        >
          {items.map((item) => {
            const active = activeId === item.id;
            return (
              <button
                key={item.id}
                type="button"
                onClick={() => onSelect(item.id)}
                style={{
                  display: "flex",
                  flexDirection: "column",
                  alignItems: "flex-start",
                  gap: 3,
                  width: "100%",
                  padding: "12px 14px",
                  border: `1px solid ${active ? scheme.accent : t.stroke.secondary}`,
                  borderRadius: 10,
                  background: active ? t.fill.tertiary : t.bg.editor,
                  color: t.text.primary,
                  textAlign: "left",
                  cursor: "pointer",
                  fontFamily: "inherit",
                  boxShadow: active ? `inset 3px 0 0 ${scheme.accentControl}` : undefined,
                  transition: "background 0.15s ease, border-color 0.15s ease",
                }}
              >
                <span style={{ fontSize: 14, fontWeight: 700 }}>{item.label}</span>
                <span style={{ fontSize: 11, color: t.text.secondary, lineHeight: 1.35 }}>{item.hint}</span>
              </button>
            );
          })}
        </nav>
      </aside>
    </div>
  );
}

export function ArmOperatorView({
  t,
  scheme,
  selectedQueue,
  onSelectQueue,
  reply,
  suflerSuggestionText,
  onReplyChange,
  onInsertSufler,
  toast,
  onClearToast,
  presence,
  onPresenceChange,
  viewMode,
  onViewModeChange,
  closeTopic,
  onCloseTopicChange,
  operatorName = "Иванов И.И.",
  statsDrawerOpen: statsDrawerOpenProp,
  onStatsDrawerOpenChange,
}: {
  t: ArmTheme;
  scheme: SchemePalette;
  selectedQueue: string;
  onSelectQueue: (id: string) => void;
  reply: string;
  suflerSuggestionText: string;
  onReplyChange: (v: string) => void;
  onInsertSufler: (answerText: string) => void;
  toast: string | null;
  onClearToast: () => void;
  presence: OperatorPresence;
  onPresenceChange: (next: OperatorPresence) => void;
  viewMode: ArmView;
  onViewModeChange: (next: ArmView) => void;
  closeTopic: string;
  onCloseTopicChange: (next: string) => void;
  /** Current ARM operator display name (accept + message labels). */
  operatorName?: string;
  statsDrawerOpen?: boolean;
  onStatsDrawerOpenChange?: (open: boolean) => void;
}): JSX.Element {
  const operatorInitials = initialsFromDisplayName(operatorName);
  const [armRole, setArmRole] = useState<ArmRole>("operator");
  const [closedDialogIds, setClosedDialogIds] = useState<Record<string, boolean>>({});
  const [blockedDialogIds, setBlockedDialogIds] = useState<Record<string, boolean>>({});
  const [summaryHistory, setSummaryHistory] = useState<SummaryHistoryData>(EMPTY_SUMMARY_HISTORY);
  const [directoryOperators, setDirectoryOperators] = useState<string[]>([]);
  const [liveWaiting, setLiveWaiting] = useState<QueueItem[]>([]);
  const [liveShared, setLiveShared] = useState<QueueItem[]>([]);
  const [liveMine, setLiveMine] = useState<QueueItem[]>([]);
  const [liveColleagues, setLiveColleagues] = useState<QueueItem[]>([]);
  const [liveOffline, setLiveOffline] = useState<QueueItem[]>([]);
  const [liveClosed, setLiveClosed] = useState<QueueItem[]>([]);
  const [liveInitiated, setLiveInitiated] = useState<QueueItem[]>([]);
  const [liveMessages, setLiveMessages] = useState<OnlineChatMessage[]>([]);
  const [clientDraft, setClientDraft] = useState("");
  const [quoteMessage, setQuoteMessage] = useState<OnlineChatMessage | null>(null);
  const [showTemplates, setShowTemplates] = useState(false);
  const [transferDialogOpen, setTransferDialogOpen] = useState(false);
  const [transferOperatorName, setTransferOperatorName] = useState("");
  const [editMessageTarget, setEditMessageTarget] = useState<OnlineChatMessage | null>(null);
  const [editMessageText, setEditMessageText] = useState("");
  const [deleteMessageTarget, setDeleteMessageTarget] = useState<OnlineChatMessage | null>(null);
  const [clientBlocks, setClientBlocks] = useState<{ id: string; phone_normalized: string }[]>([]);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const messagesScrollRef = useRef<HTMLDivElement>(null);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const acceptedLiveRef = useRef<Record<string, boolean>>({});
  const acceptInFlightRef = useRef<Record<string, boolean>>({});
  const readMessageIdsRef = useRef<Set<string>>(new Set());
  const selectedQueueRef = useRef(selectedQueue);
  selectedQueueRef.current = selectedQueue;

  const scrollMessagesToEnd = useCallback((behavior: ScrollBehavior = "smooth") => {
    const scroller = messagesScrollRef.current;
    if (scroller) {
      scroller.scrollTo({ top: scroller.scrollHeight, behavior });
      return;
    }
    messagesEndRef.current?.scrollIntoView({ behavior, block: "end" });
  }, []);

  const refreshLiveQueues = useCallback(async () => {
    try {
      const [
        waiting,
        activeDialogs,
        closedDialogs,
        initiatedDialogs,
        offlineWaiting,
        offlineActive,
      ] = await Promise.all([
        listDialogs("waiting"),
        listDialogs("active"),
        listDialogs("closed"),
        listDialogs(undefined, { initiated_by: "operator" }),
        listDialogs("waiting", { client_online: false }),
        listDialogs("active", { client_online: false }),
      ]);

      // Общая очередь — неназначенные (status=waiting).
      const sharedOnline = waiting.filter((dialog) => dialog.client_online !== false);
      setLiveShared(
        sharedOnline.map((dialog, index) => dialogToQueueItem(dialog, { active: index === 0 })),
      );

      const mineActive = activeDialogs.filter(
        (dialog) => !dialog.operator_name || dialog.operator_name === operatorName,
      );
      // Ожидают ответа — мои active, где последнее сообщение от клиента.
      const awaitingReply = mineActive.filter((dialog) => dialog.needs_reply);
      // В диалоге со мной — мои active без неотвеченного сообщения клиента.
      const mineIdle = mineActive.filter((dialog) => !dialog.needs_reply);
      setLiveWaiting(
        awaitingReply.map((dialog, index) => dialogToQueueItem(dialog, { active: index === 0 })),
      );
      setLiveMine(mineIdle.map((dialog, index) => dialogToQueueItem(dialog, { active: index === 0 })));

      setLiveColleagues(
        activeDialogs
          .filter((dialog) => dialog.operator_name && dialog.operator_name !== operatorName)
          .map((dialog) => ({ ...dialogToQueueItem(dialog), readOnly: true })),
      );

      const offlineMerged = [...offlineWaiting, ...offlineActive];
      const offlineUnique = Array.from(
        new Map(offlineMerged.map((dialog) => [dialog.id, dialog])).values(),
      );
      setLiveOffline(
        offlineUnique.map((dialog) => ({
          ...dialogToQueueItem(dialog),
          result: "offline" as const,
        })),
      );

      setLiveClosed(
        closedDialogs.slice(0, 20).map((dialog) => ({
          ...dialogToQueueItem(dialog),
          result: "closed" as const,
        })),
      );

      setLiveInitiated(
        initiatedDialogs
          .filter((dialog) => !dialog.operator_name || dialog.operator_name === operatorName)
          .map((dialog) => dialogToQueueItem(dialog)),
      );
    } catch {
      /* Backend may be offline in pure UI/story mode — keep mock queues. */
    }
  }, [operatorName]);

  useEffect(() => {
    void refreshLiveQueues();
    const timer = window.setInterval(() => {
      void refreshLiveQueues();
    }, 4000);
    let socket: WebSocket | null = null;
    try {
      socket = new WebSocket(onlineChatArmWsUrl());
      socket.onmessage = (event) => {
        void refreshLiveQueues();
        try {
          const data = JSON.parse(event.data) as {
            type?: string;
            payload?: OnlineChatMessage & {
              dialog_id?: string;
              message_ids?: string[];
              messages?: OnlineChatMessage[];
              speaker?: string;
              text?: string;
            };
          };
          const dialogId = data.payload?.dialog_id;
          if (data.type === "typing.start") {
            if (
              data.payload?.speaker === "client" &&
              dialogId === selectedQueueRef.current
            ) {
              const draftPayload = data.payload as { draft?: string; text?: string };
              setClientDraft(draftPayload.draft || draftPayload.text || "…");
            }
            return;
          }
          if (data.type === "typing.stop") {
            if (dialogId === selectedQueueRef.current) setClientDraft("");
            return;
          }
          if (data.type === "messages.read" && data.payload?.message_ids?.length) {
            const ids = data.payload.message_ids;
            ids.forEach((id) => readMessageIdsRef.current.add(id));
            if (!dialogId || dialogId === selectedQueueRef.current) {
              setLiveMessages((prev) =>
                prev.map((item) =>
                  ids.includes(item.id)
                    ? { ...item, receipt_status: "read" as ReceiptStatus }
                    : item,
                ),
              );
            }
            return;
          }
          if (dialogId && dialogId !== selectedQueueRef.current) return;
          if (data.type === "message.created" && data.payload?.id) {
            const incoming = data.payload as OnlineChatMessage;
            const withReceipt =
              incoming.receipt_status === "read" ||
              readMessageIdsRef.current.has(incoming.id)
                ? { ...incoming, receipt_status: "read" as ReceiptStatus }
                : incoming;
            setLiveMessages((prev) => {
              if (prev.some((item) => item.id === withReceipt.id)) {
                return prev.map((item) =>
                  item.id === withReceipt.id ? { ...item, ...withReceipt } : item,
                );
              }
              return [...prev, withReceipt];
            });
            if (incoming.speaker === "client" && dialogId) {
              void markDialogRead(dialogId, "operator").catch(() => {});
            }
            return;
          }
          if (data.type === "message.updated" && data.payload?.id) {
            const updated = data.payload as OnlineChatMessage;
            setLiveMessages((prev) =>
              prev.map((item) =>
                item.id === updated.id
                  ? {
                      ...item,
                      ...updated,
                      receipt_status:
                        updated.receipt_status ||
                        (readMessageIdsRef.current.has(updated.id)
                          ? "read"
                          : item.receipt_status),
                    }
                  : item,
              ),
            );
            return;
          }
        } catch {
          /* ignore malformed events */
        }
      };
    } catch {
      /* WebSocket unavailable */
    }
    return () => {
      window.clearInterval(timer);
      socket?.close();
    };
  }, [refreshLiveQueues]);

  const liveMode =
    liveWaiting.length > 0 ||
    liveShared.length > 0 ||
    liveMine.length > 0 ||
    liveColleagues.length > 0 ||
    liveOffline.length > 0 ||
    liveClosed.length > 0 ||
    liveInitiated.length > 0;

  const liveSectionItems: Partial<Record<QueueSectionId, QueueItem[]>> = useMemo(
    () => ({
      waiting: liveWaiting,
      mine: liveMine,
      colleagues: liveColleagues,
      offline: liveOffline,
      closed: liveClosed,
      shared: liveShared,
      initiated: liveInitiated,
    }),
    [
      liveWaiting,
      liveShared,
      liveMine,
      liveColleagues,
      liveOffline,
      liveClosed,
      liveInitiated,
    ],
  );

  const visibleSections = useMemo(() => {
    const sections = queueSectionsForRole(armRole);
    return sections.map((section) => {
      if (liveMode) {
        const items = liveSectionItems[section.id];
        if (items !== undefined) {
          return {
            ...section,
            items,
            count: items.length,
            defaultExpanded: items.length > 0 ? true : section.defaultExpanded,
          };
        }
      }
      if (section.id === "shared") {
        return section;
      }
      if (section.id === "mine") {
        return section;
      }
      return section;
    });
  }, [armRole, liveMode, liveSectionItems]);

  const remainingDialogs = visibleSections
    .flatMap((section) => section.items)
    .filter((item) => !closedDialogIds[item.id]);
  const active =
    remainingDialogs.find((q) => q.id === selectedQueue) ??
    (liveMode ? remainingDialogs.find((q) => q.live) : undefined) ??
    remainingDialogs[0] ??
    null;
  const hasActiveDialog = !!active;
  const isReadOnly = viewMode === "colleague";
  const isClientBlocked = !!(active && blockedDialogIds[active.id]);
  const composerLocked = isReadOnly || isClientBlocked || !hasActiveDialog;

  useEffect(() => {
    if (!hasActiveDialog) return;
    scrollMessagesToEnd(liveMessages.length <= 1 ? "auto" : "smooth");
  }, [liveMessages, clientDraft, active?.id, hasActiveDialog, scrollMessagesToEnd]);

  const clientForCard: ClientInfoData = active?.live
    ? {
        ...ACTIVE_CLIENT,
        name: active.name,
        phoneFull: active.phone || "—",
        phoneMasked: active.phone ? maskPhone(active.phone) : "—",
        dialogNo: active.refCode ? `№ ${active.refCode}` : `№ ${dialogRefCode({ id: active.id })}`,
        email: "—",
        channel: active.channel,
        entryChannel: "Виджет сайта",
        visitorId: active.id.slice(0, 12),
      }
    : ACTIVE_CLIENT;

  useEffect(() => {
    if (!active?.live) {
      setLiveMessages([]);
      setClientDraft("");
      setQuoteMessage(null);
      return;
    }
    let cancelled = false;
    const dialogId = active.id;
    void getDialog(dialogId)
      .then((dialog) => {
        if (!cancelled) {
          const messages = dialog.messages ?? [];
          for (const message of messages) {
            if (message.receipt_status === "read") {
              readMessageIdsRef.current.add(message.id);
            }
          }
          setLiveMessages(messages);
          void markDialogRead(dialogId, "operator").catch(() => {});
        }
      })
      .catch(() => {
        if (!cancelled) setLiveMessages([]);
      });

    const needsAccept =
      liveShared.some((item) => item.id === dialogId) &&
      !acceptedLiveRef.current[dialogId] &&
      !acceptInFlightRef.current[dialogId];

    if (needsAccept) {
      acceptInFlightRef.current[dialogId] = true;
      void acceptDialog(dialogId, operatorName)
        .then((dialog) => {
          acceptedLiveRef.current[dialogId] = true;
          acceptInFlightRef.current[dialogId] = false;
          void refreshLiveQueues();
          if (!cancelled) setLiveMessages(dialog.messages ?? []);
        })
        .catch(() => {
          acceptInFlightRef.current[dialogId] = false;
        });
    }

    return () => {
      cancelled = true;
    };
  }, [active?.id, active?.live, liveShared, refreshLiveQueues, operatorName]);

  useEffect(() => {
    void operatorsApi
      .list()
      .then((items) => {
        setDirectoryOperators(
          items
            .filter((item) => item.is_active !== false)
            .map((item) => item.name)
            .filter(Boolean),
        );
      })
      .catch(() => setDirectoryOperators([]));
  }, []);

  useEffect(() => {
    if (!active?.live || !active.id) {
      setSummaryHistory(EMPTY_SUMMARY_HISTORY);
      return;
    }
    let cancelled = false;
    void fetchClientHistory({ dialogId: active.id })
      .then((response) => {
        if (cancelled) return;
        setSummaryHistory(historyToSummary(response.items ?? [], response.summary ?? ""));
      })
      .catch(() => {
        if (!cancelled) setSummaryHistory(EMPTY_SUMMARY_HISTORY);
      });
    return () => {
      cancelled = true;
    };
  }, [active?.id, active?.live]);

  const handleSelectQueue = (id: string) => {
    onSelectQueue(id);
    const section = findSectionForQueueItem(id, visibleSections);
    if (section?.id === "colleagues") {
      onViewModeChange("colleague");
    } else {
      onViewModeChange("active");
    }
  };

  useEffect(() => {
    if (armRole === "admin") {
      const isColleagueItem = COLLEAGUE_DIALOGUES.some((item) => item.id === selectedQueue);
      if (isColleagueItem || viewMode === "colleague") {
        onViewModeChange("active");
        onSelectQueue(MY_DIALOGUES[0]?.id ?? QUEUE[0].id);
      }
    }
  }, [armRole, selectedQueue, viewMode, onViewModeChange, onSelectQueue]);

  const [armOpen, setArmOpen] = useState(true);
  const [leftWidth, setLeftWidth] = useState(ARM_LEFT_WIDTH_DEFAULT);
  const [rightWidth, setRightWidth] = useState(ARM_RIGHT_WIDTH_DEFAULT);
  const [leftPanelCollapsed, setLeftPanelCollapsed] = useState(false);
  const [canvasBuild, setCanvasBuild] = useState("");
  const [statsDrawerOpenLocal, setStatsDrawerOpenLocal] = useState(false);
  const statsDrawerOpen = statsDrawerOpenProp ?? statsDrawerOpenLocal;
  const setStatsDrawerOpen = onStatsDrawerOpenChange ?? setStatsDrawerOpenLocal;
  const [statsTab, setStatsTab] = useState<ArmStatsTab>("dialogs");

  useEffect(() => {
    if (canvasBuild !== CANVAS_MOCKUP_VERSION) {
      setCanvasBuild(CANVAS_MOCKUP_VERSION);
      setStatsDrawerOpen(false);
      setStatsTab("dialogs");
    }
  }, [canvasBuild, setCanvasBuild, setStatsDrawerOpen, setStatsTab]);

  useEffect(() => {
    const allowed = armMenuItemsForRole(armRole).some((item) => item.id === statsTab);
    if (!allowed) setStatsTab(firstArmStatsTabForRole(armRole));
  }, [armRole, statsTab]);
  const [expandedSections, setExpandedSections] = useState<Record<QueueSectionId, boolean>>(
    defaultExpandedSections(),
  );
  const [collapsedCards, setCollapsedCards] = useState<Record<string, boolean>>({});
  const [expandedHintIds, setExpandedHintIds] = useState<Record<string, boolean>>({});
  const [expandedClientCard, setExpandedClientCard] = useState(false);
  const [expandedSummaryCard, setExpandedSummaryCard] = useState(false);
  const [spellWarning, setSpellWarning] = useState(false);
  const [composerNotice, setComposerNotice] = useState<string | null>(null);
  const [aiImproveModal, setAiImproveModal] = useState<AiImproveModalState | null>(null);
  const [closeDialogConfirmOpen, setCloseDialogConfirmOpen] = useState(false);
  const [blockClientConfirmOpen, setBlockClientConfirmOpen] = useState(false);

  useEffect(() => {
    setExpandedSections((prev) => {
      const next = { ...prev };
      if (liveWaiting.length > 0) next.waiting = true;
      if (liveShared.length > 0) next.shared = true;
      return next;
    });
  }, [liveWaiting.length, liveShared.length]);

  useEffect(() => {
    if (armRole !== "admin") return;
    void listClientBlocks(true)
      .then((blocks) =>
        setClientBlocks(blocks.map((block) => ({ id: block.id, phone_normalized: block.phone_normalized }))),
      )
      .catch(() => {});
  }, [armRole]);

  useEffect(() => {
    if (liveMine.length === 0) return;
    setExpandedSections((prev) => (prev.mine ? prev : { ...prev, mine: true }));
  }, [liveMine.length]);

  useEffect(() => {
    if (!liveMode) return;
    if (selectedQueue && remainingDialogs.some((item) => item.id === selectedQueue)) return;
    const firstLive = remainingDialogs.find((item) => item.live);
    if (firstLive) onSelectQueue(firstLive.id);
  }, [liveMode, selectedQueue, remainingDialogs, onSelectQueue]);

  const clearComposerNotice = () => setComposerNotice(null);

  const visibleQueueSections = visibleSections.map((section) => {
    const items = section.items.filter((item) => !closedDialogIds[item.id]);
    return { ...section, items, count: items.length };
  });

  useEffect(() => {
    if (selectedQueue && !closedDialogIds[selectedQueue]) return;
    const next = remainingDialogs.find((item) => !closedDialogIds[item.id]);
    if (next) {
      if (next.id !== selectedQueue) onSelectQueue(next.id);
      return;
    }
    if (selectedQueue) onSelectQueue("");
  }, [selectedQueue, closedDialogIds, onSelectQueue, remainingDialogs]);

  const handleConfirmCloseDialog = () => {
    if (!active) {
      setCloseDialogConfirmOpen(false);
      return;
    }
    const topic = closeTopic.trim();
    if (!topic) {
      setCloseDialogConfirmOpen(false);
      setComposerNotice("Выберите тематику закрытия перед завершением диалога.");
      return;
    }
    const closingId = active.id;
    const closedName = active.name;
    const wasLive = !!active.live;
    setCloseDialogConfirmOpen(false);
    setClosedDialogIds((prev) => ({ ...prev, [closingId]: true }));
    setBlockedDialogIds((prev) => {
      if (!prev[closingId]) return prev;
      const next = { ...prev };
      delete next[closingId];
      return next;
    });
    if (wasLive) {
      void closeDialogRemote(closingId, topic)
        .then(() => void refreshLiveQueues())
        .catch(() => {
          setComposerNotice("Не удалось закрыть диалог на сервере. Попробуйте ещё раз.");
        });
    }
    const nextDialog = remainingDialogs.find((item) => item.id !== closingId);
    if (nextDialog) {
      onSelectQueue(nextDialog.id);
      setComposerNotice(`Диалог с ${closedName} закрыт · ${topic}.`);
    } else {
      onSelectQueue("");
      setComposerNotice(`Диалог закрыт · ${topic}. Очередь пуста.`);
    }
  };

  const handleConfirmBlockClient = () => {
    if (!active) {
      setBlockClientConfirmOpen(false);
      return;
    }
    setBlockClientConfirmOpen(false);
    setBlockedDialogIds((prev) => ({ ...prev, [active.id]: true }));
    if (active.live) {
      void blockDialogRemote(active.id, { blocked_by: operatorName })
        .then(() => void refreshLiveQueues())
        .catch(() => {});
    }
    setComposerNotice(`Клиент ${active.name} заблокирован.`);
  };

  const deliverReply = (notice: string) => {
    const text = reply.trim();
    if (!text || !active || composerLocked) return;
    const replyToId = quoteMessage?.id;
    if (active.live) {
      void sendOperatorMessage(active.id, text, {
        reply_to_id: replyToId,
        operator_name: operatorName,
        response_origin: suflerSuggestionText ? 'sufler' : undefined,
        sufler_suggestion_text: suflerSuggestionText || undefined,
      })
        .then((message) => {
          const withReceipt =
            message.receipt_status === "read" ||
            readMessageIdsRef.current.has(message.id)
              ? { ...message, receipt_status: "read" as ReceiptStatus }
              : message;
          setLiveMessages((prev) => {
            if (prev.some((item) => item.id === withReceipt.id)) {
              return prev.map((item) =>
                item.id === withReceipt.id ? { ...item, ...withReceipt } : item,
              );
            }
            return [...prev, withReceipt];
          });
          onReplyChange("");
          setQuoteMessage(null);
          setSpellWarning(false);
          setComposerNotice(notice);
          void refreshLiveQueues();
        })
        .catch(() => {
          setComposerNotice("Не удалось отправить сообщение.");
        });
      return;
    }
    onReplyChange("");
    setQuoteMessage(null);
    setSpellWarning(false);
    setComposerNotice(notice);
  };

  const transferOperatorOptions = useMemo(() => {
    const names = new Set<string>(
      directoryOperators.length ? directoryOperators : TRANSFER_OPERATORS,
    );
    for (const item of liveColleagues) {
      if (item.operatorName) names.add(item.operatorName);
    }
    names.delete(operatorName);
    return Array.from(names)
      .sort((a, b) => a.localeCompare(b, "ru"))
      .map((name) => ({ value: name, label: name }));
  }, [directoryOperators, liveColleagues, operatorName]);

  const openTransferDialog = () => {
    if (!active?.live || composerLocked) return;
    setTransferOperatorName(transferOperatorOptions[0]?.value ?? "");
    setTransferDialogOpen(true);
  };

  const handleConfirmTransferDialog = () => {
    if (!active?.live) return;
    const toName = transferOperatorName.trim();
    if (!toName) return;
    setTransferDialogOpen(false);
    void transferDialogRemote(active.id, toName, operatorName)
      .then(() => {
        setComposerNotice(`Диалог переведён на ${toName}.`);
        void refreshLiveQueues();
      })
      .catch(() => {
        setComposerNotice("Не удалось перевести диалог.");
      });
  };

  const handleFilePick = (file: File) => {
    if (!active?.live || composerLocked) return;
    void uploadOperatorAttachment(active.id, file, operatorName)
      .then((message) => {
        setLiveMessages((prev) =>
          prev.some((item) => item.id === message.id) ? prev : [...prev, message],
        );
        setComposerNotice(`Файл «${file.name}» отправлен.`);
        void refreshLiveQueues();
      })
      .catch(() => {
        setComposerNotice("Не удалось отправить файл.");
      });
  };

  const openEditMessage = (message: OnlineChatMessage) => {
    if (!active?.live) return;
    setEditMessageTarget(message);
    setEditMessageText(message.raw_text || message.text);
  };

  const handleConfirmEditMessage = () => {
    if (!active?.live || !editMessageTarget) return;
    const nextText = editMessageText.trim();
    if (!nextText || nextText === (editMessageTarget.raw_text || editMessageTarget.text)) {
      setEditMessageTarget(null);
      return;
    }
    const messageId = editMessageTarget.id;
    setEditMessageTarget(null);
    void editMessageRemote(active.id, messageId, nextText)
      .then((updated) => {
        setLiveMessages((prev) =>
          prev.map((item) => (item.id === updated.id ? updated : item)),
        );
      })
      .catch(() => {
        setComposerNotice("Не удалось изменить сообщение.");
      });
  };

  const openDeleteMessage = (message: OnlineChatMessage) => {
    if (!active?.live) return;
    setDeleteMessageTarget(message);
  };

  const handleConfirmDeleteMessage = () => {
    if (!active?.live || !deleteMessageTarget) return;
    const messageId = deleteMessageTarget.id;
    setDeleteMessageTarget(null);
    void deleteMessageRemote(active.id, messageId)
      .then((deleted) => {
        setLiveMessages((prev) =>
          prev.map((item) =>
            item.id === deleted.id ? { ...item, is_deleted: true, text: "" } : item,
          ),
        );
      })
      .catch(() => {
        setComposerNotice("Не удалось удалить сообщение.");
      });
  };

  const activePhoneBlock = useMemo(() => {
    if (!active?.phone || armRole !== "admin") return null;
    const digits = active.phone.replace(/\D/g, "");
    return clientBlocks.find((block) => block.phone_normalized.replace(/\D/g, "") === digits) ?? null;
  }, [active?.phone, armRole, clientBlocks]);

  const handleLiftBlock = () => {
    if (!activePhoneBlock) return;
    void liftClientBlock(activePhoneBlock.id, operatorName)
      .then(() => {
        setClientBlocks((prev) => prev.filter((block) => block.id !== activePhoneBlock.id));
        setComposerNotice("Блокировка клиента снята.");
      })
      .catch(() => {
        setComposerNotice("Не удалось снять блокировку.");
      });
  };

  const spellErrors = reply.trim().length > 0 ? findSpellErrors(reply) : [];

  const handleAiImprove = () => {
    setComposerNotice(null);
    const trimmed = reply.trim();
    if (trimmed.length === 0) return;
    const errors = findSpellErrors(reply);
    const improved = errors.length > 0 ? applySpellFixes(reply, errors) : polishTextDemo(reply);
    setAiImproveModal({ original: reply, improved });
  };

  const handleAcceptAiImprove = () => {
    if (!aiImproveModal) return;
    onReplyChange(aiImproveModal.improved);
    setAiImproveModal(null);
    setSpellWarning(false);
  };

  const handleDismissAiImprove = () => {
    setAiImproveModal(null);
  };
  const boundedLeftWidth = clampWidth(leftWidth, ARM_LEFT_WIDTH_MIN, ARM_LEFT_WIDTH_MAX);
  const boundedRightWidth = clampWidth(rightWidth, ARM_RIGHT_WIDTH_MIN, ARM_RIGHT_WIDTH_MAX);

  const toggleSection = (sectionId: QueueSectionId) => {
    setExpandedSections((prev) => {
      const section = visibleSections.find((s) => s.id === sectionId);
      if (!section) return prev;
      return { ...prev, [sectionId]: !isSectionExpanded(prev, section) };
    });
  };
  const collapseCard = (cardId: string) => {
    setCollapsedCards((prev) => ({ ...prev, [cardId]: true }));
  };
  const expandCard = (cardId: string) => {
    setCollapsedCards((prev) => {
      const next = { ...prev };
      delete next[cardId];
      return next;
    });
  };
  const collapseAllQueue = () => {
    setExpandedSections(allSectionsCollapsedState(visibleSections));
    setCollapsedCards({});
  };
  const expandAllQueue = () => {
    setExpandedSections(allSectionsExpandedState(visibleSections));
    setCollapsedCards({});
  };
  const allSectionsCollapsed = areAllSectionsCollapsed(expandedSections, visibleSections);

  if (!armOpen) {
    return (
      <Button variant="secondary" onClick={() => setArmOpen(true)}>
        Открыть окно · АРМ оператора
      </Button>
    );
  }

  return (
    <div
      style={{
        display: "flex",
        flexDirection: "column",
        height: "100%",
        flex: 1,
        minHeight: 0,
        minWidth: 900,
        position: "relative",
      }}
    >
      <div
        style={{
          position: "relative",
          ...panelStyle(t),
          padding: "10px 16px",
          borderRadius: `${RADIUS_MD} ${RADIUS_MD} 0 0`,
          borderBottom: `1px solid ${scheme.accent}`,
          background: scheme.headerBg,
          zIndex: 5,
          display: "flex",
          alignItems: "center",
          gap: 12,
        }}
      >
        <Row
          style={{
            gap: 6,
            flexWrap: "wrap",
            alignItems: "center",
            minWidth: 0,
            flex: 1,
          }}
        >
          {OPERATOR_STATUSES.map((status) => (
            <OperatorStatusPill
              key={status.id}
              t={t}
              status={status}
              active={presence === status.id}
              size="md"
              onClick={() => onPresenceChange(status.id)}
            />
          ))}
        </Row>
      </div>

      <div style={{ display: "flex", flex: 1, minHeight: 0, position: "relative", overflow: "hidden" }}>
        <ArmOverlayMenu
          t={t}
          scheme={scheme}
          open={statsDrawerOpen}
          armRole={armRole}
          activeId={statsTab}
          onSelect={(id) => {
            setStatsTab(id);
            setComposerNotice(`Раздел «${ARM_MENU_ITEMS.find((item) => item.id === id)?.label ?? id}» пока недоступен.`);
            setStatsDrawerOpen(false);
          }}
          onClose={() => setStatsDrawerOpen(false)}
        />
        {/* Queues */}
        {leftPanelCollapsed ? (
          <div
            style={{
              width: 28,
              flexShrink: 0,
              ...panelStyle(t, { borderRadius: 0, borderRight: "none" }),
              display: "flex",
              flexDirection: "column",
              alignItems: "center",
              paddingTop: 12,
            }}
          >
            <button
              type="button"
              title="Развернуть панель очереди"
              aria-label="Развернуть панель очереди"
              onClick={() => setLeftPanelCollapsed((collapsed) => !collapsed)}
              style={{
                border: "none",
                background: "transparent",
                color: scheme.accentControl,
                fontSize: 12,
                cursor: "pointer",
                padding: "4px 2px",
                fontFamily: "inherit",
              }}
            >
              »»
            </button>
          </div>
        ) : (
          <div
            style={{
              width: boundedLeftWidth,
              flexShrink: 0,
              minHeight: 0,
              alignSelf: "stretch",
              ...panelStyle(t, { borderRadius: 0, borderRight: "none" }),
              display: "flex",
              flexDirection: "column",
              overflow: "hidden",
            }}
          >
            <div style={{ padding: "12px 12px 8px", flexShrink: 0 }}>
            <Row style={{ justifyContent: "space-between", alignItems: "center", marginBottom: 8, gap: 4 }}>
              <button
                type="button"
                title={allSectionsCollapsed ? "Развернуть все" : "Свернуть все"}
                aria-label={allSectionsCollapsed ? "Развернуть все секции" : "Свернуть все секции"}
                onClick={() => (allSectionsCollapsed ? expandAllQueue() : collapseAllQueue())}
                style={{
                  border: `1px solid ${scheme.accentWeak}`,
                  background: `linear-gradient(180deg, ${t.bg.elevated} 0%, ${t.fill.secondary} 100%)`,
                  color: scheme.accentControl,
                  fontSize: 12,
                  fontWeight: 650,
                  cursor: "pointer",
                  padding: "6px 12px",
                  fontFamily: "inherit",
                  borderRadius: 999,
                  display: "inline-flex",
                  alignItems: "center",
                  gap: 7,
                  lineHeight: 1.2,
                  boxShadow: "0 1px 2px rgba(0,0,0,0.06)",
                }}
              >
                <span
                  aria-hidden
                  style={{
                    width: 18,
                    height: 18,
                    borderRadius: 999,
                    display: "inline-grid",
                    placeItems: "center",
                    background: scheme.accentWeak,
                    color: scheme.accentControl,
                    fontSize: 12,
                    lineHeight: 1,
                  }}
                >
                  {allSectionsCollapsed ? "+" : "−"}
                </span>
                {allSectionsCollapsed ? "Развернуть все" : "Свернуть все"}
              </button>
              <button
                type="button"
                title="Свернуть панель очереди"
                aria-label="Свернуть панель очереди"
                onClick={() => setLeftPanelCollapsed((collapsed) => !collapsed)}
                style={{
                  border: "none",
                  background: "transparent",
                  color: t.text.tertiary,
                  fontSize: 12,
                  cursor: "pointer",
                  padding: "2px 4px",
                  fontFamily: "inherit",
                  flexShrink: 0,
                }}
              >
                ««
              </button>
            </Row>
            </div>
            <div style={{ flex: 1, minHeight: 0, overflowY: "auto", padding: "0 12px 12px" }}>
            <Stack style={{ gap: 12 }}>
              {visibleQueueSections.map((section) => {
                const sectionExpanded = isSectionExpanded(expandedSections, section);
                return (
                  <div key={section.id}>
                    <QueueSectionHeader
                      t={t}
                      scheme={scheme}
                      title={section.title}
                      count={section.count}
                      expanded={sectionExpanded}
                      onToggle={() => toggleSection(section.id)}
                    />
                    {sectionExpanded ? (
                      <Stack style={{ gap: 8 }}>
                        {section.items.map((q) => {
                          const cardCollapsed = !!collapsedCards[q.id];

                          if (cardCollapsed) {
                            return (
                              <QueueListRow
                                key={q.id}
                                item={q}
                                t={t}
                                selected={q.id === selectedQueue}
                                onClick={() => {
                                  handleSelectQueue(q.id);
                                  expandCard(q.id);
                                }}
                              />
                            );
                          }

                          return (
                            <QueueCard
                              key={q.id}
                              item={q}
                              t={t}
                              scheme={scheme}
                              selected={q.id === selectedQueue}
                              onSelect={() => handleSelectQueue(q.id)}
                              onCollapse={() => collapseCard(q.id)}
                            />
                          );
                        })}
                      </Stack>
                    ) : null}
                  </div>
                );
              })}
            </Stack>
            </div>
          </div>
        )}

        {!leftPanelCollapsed ? (
          <ColumnResizeHandle
            t={t}
            label="Изменить ширину панели очереди"
            onMouseDown={(event) =>
              startColumnResize(event, boundedLeftWidth, setLeftWidth, ARM_LEFT_WIDTH_MIN, ARM_LEFT_WIDTH_MAX)
            }
          />
        ) : null}

        {/* Chat */}
        <div
          style={{
            flex: 1,
            minWidth: 0,
            minHeight: 0,
            position: "relative",
            ...panelStyle(t, { borderRadius: 0 }),
            display: "flex",
            flexDirection: "column",
          }}
        >
          {!hasActiveDialog || !active ? (
            <div
              style={{
                flex: 1,
                display: "flex",
                flexDirection: "column",
                alignItems: "center",
                justifyContent: "center",
                padding: 24,
                gap: 12,
              }}
            >
              <Text style={{ color: t.text.secondary, fontSize: 14, textAlign: "center" }}>
                Нет активного диалога. Выберите обращение из очереди слева.
              </Text>
              {composerNotice ? (
                <div style={{ width: "100%", maxWidth: 420 }}>
                  <AutoFadeNotice message={composerNotice} onDone={clearComposerNotice} />
                </div>
              ) : null}
            </div>
          ) : (
            <>
          <div style={{ padding: "12px 16px", borderBottom: `1px solid ${t.stroke.secondary}`, flexShrink: 0 }}>
            <Row style={{ justifyContent: "space-between", alignItems: "flex-start", gap: 12 }}>
              <div style={{ minWidth: 0 }}>
                <Row style={{ gap: 8, alignItems: "center", flexWrap: "wrap" }}>
                  <Text weight="semibold">{active.name}</Text>
                  {isClientBlocked ? (
                    <Pill tone="warning" size="sm">
                      Клиент заблокирован
                    </Pill>
                  ) : null}
                </Row>
                <Row style={{ gap: 8, marginTop: 4 }}>
                  <Pill tone="info" size="sm">
                    {active.channel}
                  </Pill>
                </Row>
              </div>
              {isReadOnly ? (
                <div
                  style={{
                    flex: 1,
                    display: "flex",
                    justifyContent: "center",
                    alignItems: "flex-start",
                    minWidth: 0,
                    paddingTop: 2,
                  }}
                >
                  <Callout tone="warning" style={{ fontSize: 12, maxWidth: 420, width: "100%" }}>
                    Режим просмотра: диалог коллеги без возможности отправки.
                  </Callout>
                </div>
              ) : (
                <Spacer />
              )}
              <Stack gap={6} style={{ alignItems: "flex-end", flexShrink: 0 }}>
                {active.slaTone ? (
                  <SlaWaitPill wait={`SLA ${active.wait}`} slaTone={active.slaTone} />
                ) : (
                  <Pill tone={active.urgent ? "warning" : "neutral"} size="sm">
                    SLA {active.wait}
                  </Pill>
                )}
                <Text style={{ fontSize: 12, color: t.text.secondary, textAlign: "right" }}>
                  {viewMode === "colleague"
                    ? `Просмотр · ${active.operatorName ?? "коллега"}`
                    : "Мой диалог"}
                </Text>
              </Stack>
            </Row>
            {isClientBlocked ? (
              <Callout tone="warning" style={{ marginTop: 10, fontSize: 12 }}>
                Пользователь заблокирован. Отправка сообщений недоступна.
              </Callout>
            ) : null}
          </div>
          <div style={{ padding: "8px 16px", borderBottom: `1px solid ${t.stroke.tertiary}`, flexShrink: 0 }}>
            <Row style={{ gap: 8, alignItems: "center", flexWrap: "wrap" }}>
              <Text style={{ fontSize: 12, color: t.text.secondary }}>Тематика закрытия:</Text>
              <div style={{ minWidth: 220, flex: "1 1 220px", maxWidth: 320 }}>
                <Select
                  value={closeTopic}
                  onChange={onCloseTopicChange}
                  options={CLOSE_TOPICS.map((topic) => ({ value: topic, label: topic }))}
                />
              </div>
              <Spacer />
              <Button
                variant="ghost"
                size="sm"
                style={{ color: t.text.tertiary, fontSize: 11 }}
                disabled={isReadOnly || isClientBlocked}
                onClick={() => setBlockClientConfirmOpen(true)}
              >
                {isClientBlocked ? "Заблокирован" : "Заблокировать"}
              </Button>
              {activePhoneBlock ? (
                <Button
                  variant="ghost"
                  size="sm"
                  style={{ color: t.text.tertiary, fontSize: 11 }}
                  onClick={handleLiftBlock}
                >
                  Снять блокировку
                </Button>
              ) : null}
              <Button
                variant="primary"
                size="sm"
                disabled={isReadOnly}
                onClick={() => setCloseDialogConfirmOpen(true)}
              >
                Закрыть диалог
              </Button>
            </Row>
          </div>
          <div
            ref={messagesScrollRef}
            style={{
              flex: 1,
              minHeight: 0,
              padding: "16px 16px 20px",
              overflowY: "auto",
              overflowX: "hidden",
              display: "flex",
              flexDirection: "column",
              gap: 10,
            }}
          >
            {active.live ? (
              liveMessages.length > 0 ? (
                liveMessages.map((message) => {
                  if (message.speaker === "system") {
                    return (
                      <MessageBubble
                        key={message.id}
                        t={t}
                        scheme={scheme}
                        side="system"
                        text={message.text}
                      />
                    );
                  }
                  if (message.speaker === "operator") {
                    return (
                      <MessageBubble
                        key={message.id}
                        t={t}
                        scheme={scheme}
                        side="operator"
                        label={`${operatorName} · оператор`}
                        avatarInitials={operatorInitials}
                        text={message.text}
                        time={messageTimeLabel(message.created_at)}
                        quotedText={message.quoted_text}
                        attachmentName={message.attachment_name}
                        attachmentHref={
                          message.attachment_name && active?.id
                            ? attachmentDownloadUrl(active.id, message.id)
                            : undefined
                        }
                        isDeleted={message.is_deleted}
                        editedAt={message.edited_at}
                        receiptStatus={
                          message.is_deleted
                            ? undefined
                            : message.receipt_status === "read" ||
                                readMessageIdsRef.current.has(message.id)
                              ? "read"
                              : "delivered"
                        }
                        onEdit={
                          !isReadOnly && !message.is_deleted
                            ? () => openEditMessage(message)
                            : undefined
                        }
                        onDelete={
                          !isReadOnly && !message.is_deleted
                            ? () => openDeleteMessage(message)
                            : undefined
                        }
                      />
                    );
                  }
                  if (message.speaker === "bot") {
                    return (
                      <MessageBubble
                        key={message.id}
                        t={t}
                        scheme={scheme}
                        side="operator"
                        label="Виртуальный помощник · бот"
                        avatarInitials="Б"
                        text={message.text}
                        time={messageTimeLabel(message.created_at)}
                        receiptStatus={message.receipt_status}
                      />
                    );
                  }
                  return (
                    <MessageBubble
                      key={message.id}
                      t={t}
                      scheme={scheme}
                      side="client"
                      label={active.name}
                      avatarInitials={initialsFromDisplayName(active.name)}
                      text={message.text}
                      time={messageTimeLabel(message.created_at)}
                      quotedText={message.quoted_text}
                      editedAt={message.edited_at}
                      attachmentName={message.attachment_name}
                      attachmentHref={
                        message.attachment_name && active?.id
                          ? attachmentDownloadUrl(active.id, message.id)
                          : undefined
                      }
                      isDeleted={message.is_deleted}
                      onQuote={
                        !isReadOnly && !message.is_deleted
                          ? () => setQuoteMessage(message)
                          : undefined
                      }
                    />
                  );
                })
              ) : (
                <Text style={{ fontSize: 12, color: t.text.secondary }}>
                  Загрузка сообщений…
                </Text>
              )
            ) : (
              <>
                <MessageBubble
                  t={t}
                  scheme={scheme}
                  side="system"
                  text={`Оператор ${operatorName} подключился к диалогу`}
                />
                <MessageBubble
                  t={t}
                  scheme={scheme}
                  side="client"
                  label={active.name}
                  avatarInitials={initialsFromDisplayName(active.name)}
                  text={active.preview}
                  time="10:03"
                />
                <MessageBubble
                  t={t}
                  scheme={scheme}
                  side="operator"
                  label={`${operatorName} · оператор`}
                  avatarInitials={operatorInitials}
                  text="Проверяю лимиты по вашей карте, одну минуту."
                  time="10:04"
                  receiptStatus="read"
                />
              </>
            )}
            <div ref={messagesEndRef} aria-hidden style={{ height: 1, flexShrink: 0 }} />
          </div>
          <div
            style={{
              padding: 12,
              borderTop: `1px solid ${t.stroke.secondary}`,
              flexShrink: 0,
              background: t.bg.elevated,
            }}
          >
            <input
              ref={fileInputRef}
              type="file"
              style={{ display: "none" }}
              onChange={(event) => {
                const file = event.target.files?.[0];
                if (file) handleFilePick(file);
                event.target.value = "";
              }}
            />
            <Row style={{ gap: 8, marginBottom: 8, flexWrap: "wrap", alignItems: "center", position: "relative" }}>
              <Button
                variant={showTemplates ? "primary" : "secondary"}
                disabled={composerLocked}
                onClick={() => setShowTemplates((open) => !open)}
              >
                Шаблоны
              </Button>
              {showTemplates && !composerLocked ? (
                <div
                  role="listbox"
                  aria-label="Шаблоны ответов"
                  style={{
                    position: "absolute",
                    bottom: "100%",
                    left: 0,
                    marginBottom: 8,
                    zIndex: 20,
                    width: 360,
                    maxWidth: "min(360px, calc(100vw - 48px))",
                    background: t.bg.elevated,
                    border: `1px solid ${scheme.accentWeak}`,
                    borderRadius: 12,
                    padding: 10,
                    boxShadow: "0 14px 36px rgba(12, 40, 28, 0.16)",
                    overflow: "hidden",
                  }}
                >
                  <div
                    style={{
                      display: "flex",
                      alignItems: "center",
                      justifyContent: "space-between",
                      gap: 8,
                      padding: "2px 6px 10px",
                      borderBottom: `1px solid ${t.stroke.secondary}`,
                      marginBottom: 8,
                    }}
                  >
                    <div>
                      <Text weight="semibold" style={{ fontSize: 13, color: t.text.primary }}>
                        Шаблоны ответов
                      </Text>
                      <Text style={{ fontSize: 11, color: t.text.tertiary, marginTop: 2 }}>
                        Вставка в поле ответа одним кликом
                      </Text>
                    </div>
                    <Button
                      variant="ghost"
                      size="sm"
                      aria-label="Закрыть шаблоны"
                      onClick={() => setShowTemplates(false)}
                    >
                      ✕
                    </Button>
                  </div>
                  <Stack gap={4}>
                    {REPLY_TEMPLATES.map((template, index) => (
                      <button
                        key={template}
                        type="button"
                        role="option"
                        onClick={() => {
                          onReplyChange(template);
                          setShowTemplates(false);
                        }}
                        style={{
                          border: `1px solid ${t.stroke.secondary}`,
                          background: t.bg.editor,
                          textAlign: "left",
                          padding: "10px 12px",
                          borderRadius: 10,
                          cursor: "pointer",
                          fontFamily: "inherit",
                          fontSize: 12,
                          lineHeight: 1.4,
                          color: t.text.primary,
                          display: "flex",
                          gap: 10,
                          alignItems: "flex-start",
                          transition: "background 120ms ease, border-color 120ms ease",
                        }}
                        onMouseEnter={(event) => {
                          event.currentTarget.style.background = scheme.accentWeak;
                          event.currentTarget.style.borderColor = scheme.accent;
                        }}
                        onMouseLeave={(event) => {
                          event.currentTarget.style.background = t.bg.editor;
                          event.currentTarget.style.borderColor = t.stroke.secondary;
                        }}
                      >
                        <span
                          style={{
                            flexShrink: 0,
                            width: 22,
                            height: 22,
                            borderRadius: 7,
                            background: scheme.accent,
                            color: "#fff",
                            fontSize: 11,
                            fontWeight: 700,
                            display: "inline-flex",
                            alignItems: "center",
                            justifyContent: "center",
                            marginTop: 1,
                          }}
                        >
                          {index + 1}
                        </span>
                        <span style={{ minWidth: 0 }}>{template}</span>
                      </button>
                    ))}
                  </Stack>
                </div>
              ) : null}
              <Button
                variant="secondary"
                disabled={composerLocked}
                onClick={() => fileInputRef.current?.click()}
              >
                Файл
              </Button>
              <Button
                variant="secondary"
                disabled={composerLocked || !active?.live}
                onClick={openTransferDialog}
              >
                Перевести
              </Button>
            </Row>
            {clientDraft && active?.live && !composerLocked ? (
              <Callout tone="info" style={{ marginBottom: 8, fontSize: 12 }}>
                Клиент набирает: {clientDraft}
              </Callout>
            ) : null}
            {quoteMessage ? (
              <div
                style={{
                  marginBottom: 8,
                  padding: "6px 10px",
                  borderRadius: RADIUS_SM,
                  background: t.fill.tertiary,
                  border: `1px solid ${t.stroke.secondary}`,
                  display: "flex",
                  alignItems: "center",
                  gap: 8,
                }}
              >
                <Text style={{ fontSize: 12, color: t.text.secondary, flex: 1, minWidth: 0 }}>
                  Ответ на: {quoteMessage.text.slice(0, 120)}
                  {quoteMessage.text.length > 120 ? "…" : ""}
                </Text>
                <Button variant="ghost" size="sm" onClick={() => setQuoteMessage(null)}>
                  ✕
                </Button>
              </div>
            ) : null}
            <div style={{ position: "relative" }}>
              <Stack gap={8}>
                <TextArea
                  placeholder={
                    isClientBlocked
                      ? "Клиент заблокирован — ответ недоступен"
                      : "Введите ответ клиенту…"
                  }
                  style={{ width: "100%", minHeight: 72, overflow: "auto", resize: "vertical" }}
                  rows={3}
                  value={reply}
                  onChange={(v) => {
                    onReplyChange(v);
                    setSpellWarning(false);
                    setComposerNotice(null);
                    if (aiImproveModal && v !== aiImproveModal.original) {
                      setAiImproveModal(null);
                    }
                  }}
                  disabled={composerLocked}
                />
                {!composerLocked ? <SpellCheckHints t={t} text={reply} errors={spellErrors} /> : null}
                <div style={{ position: "relative" }}>
                  {aiImproveModal && !composerLocked ? (
                    <AiImprovePopover
                      t={t}
                      scheme={scheme}
                      state={aiImproveModal}
                      onAccept={handleAcceptAiImprove}
                      onDismiss={handleDismissAiImprove}
                    />
                  ) : null}
                  <Row style={{ gap: 8, justifyContent: "flex-end", alignItems: "center" }}>
                    <Button
                      disabled={composerLocked || reply.trim().length === 0}
                      onClick={handleAiImprove}
                      style={{
                        background: scheme.accentWeak,
                        borderColor: scheme.accent,
                        color: scheme.accentControl,
                        fontWeight: 600,
                      }}
                    >
                      Улучшить с помощью AI
                    </Button>
                    <Button
                      variant="primary"
                      disabled={composerLocked || reply.trim().length === 0}
                      onClick={() => {
                        if (spellErrors.length > 0) {
                          setSpellWarning(true);
                          return;
                        }
                        deliverReply("Сообщение отправлено.");
                      }}
                    >
                      Отправить
                    </Button>
                  </Row>
                </div>
              </Stack>
            </div>
            {spellWarning && spellErrors.length > 0 && !composerLocked ? (
              <Callout tone="warning" style={{ marginTop: 8, fontSize: 12 }}>
                <Text style={{ fontSize: 12, marginBottom: 8 }}>
                  Обнаружены орфографические ошибки ({spellErrors.length}). Исправить или отправить всё равно?
                </Text>
                <Row gap={8} wrap>
                  <Button
                    variant="secondary"
                    size="sm"
                    onClick={() => {
                      onReplyChange(applySpellFixes(reply, spellErrors));
                      setSpellWarning(false);
                    }}
                  >
                    Исправить
                  </Button>
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={() => {
                      deliverReply("Сообщение отправлено (орфография не исправлена).");
                    }}
                  >
                    Отправить всё равно
                  </Button>
                </Row>
              </Callout>
            ) : null}
            {composerNotice ? (
              <AutoFadeNotice message={composerNotice} onDone={clearComposerNotice} />
            ) : null}
            {toast ? <AutoFadeNotice message={toast} onDone={onClearToast} /> : null}
          </div>
            </>
          )}
        </div>

        <ColumnResizeHandle
          t={t}
          label="Изменить ширину панели клиента и суфлёра"
          onMouseDown={(event) =>
            startColumnResize(
              event,
              boundedRightWidth,
              setRightWidth,
              ARM_RIGHT_WIDTH_MIN,
              ARM_RIGHT_WIDTH_MAX,
              true,
            )
          }
        />

        {/* Context + Sufler */}
        <div
          style={{
            width: boundedRightWidth,
            flexShrink: 0,
            minHeight: 0,
            alignSelf: "stretch",
            ...panelStyle(t, { borderRadius: 0, borderLeft: "none" }),
            display: "flex",
            flexDirection: "column",
            overflow: "hidden",
          }}
        >
          <div style={{ flex: 1, minHeight: 0, overflowY: "auto", padding: 12 }}>
          <H3 style={{ fontSize: 15, fontWeight: 700 }}>Summary клиента</H3>
          <ClientSummaryCard
            t={t}
            scheme={scheme}
            data={summaryHistory}
            isExpanded={expandedSummaryCard}
            onToggle={() => setExpandedSummaryCard((open) => !open)}
            disabled={isReadOnly}
          />

          <Divider style={{ margin: "12px 0" }} />
          <H3 style={{ fontSize: 15, fontWeight: 700 }}>Клиент</H3>
          <ClientInfoCard
            t={t}
            scheme={scheme}
            client={clientForCard}
            isExpanded={expandedClientCard}
            onToggle={() => setExpandedClientCard((open) => !open)}
            disabled={isReadOnly}
          />

          <Divider style={{ margin: "12px 0" }} />
          <Row style={{ justifyContent: "space-between", alignItems: "center" }}>
            <H3 style={{ fontSize: 15, fontWeight: 700 }}>Суфлёр</H3>
            <Pill tone="success" size="sm">
              активен
            </Pill>
          </Row>

          <div style={{ position: "relative" }}>
            {SUFLER_HINTS.map((hint) => (
              <SuflerHintCard
                key={hint.id}
                t={t}
                scheme={scheme}
                hint={hint}
                isExpanded={!!expandedHintIds[hint.id]}
                onToggle={() =>
                  setExpandedHintIds((current) => ({
                    ...current,
                    [hint.id]: !current[hint.id],
                  }))
                }
                onInsert={onInsertSufler}
                disabled={isReadOnly}
              />
            ))}
          </div>
          </div>
        </div>
      </div>

      <div
        style={{
          padding: "6px 16px",
          fontSize: 11,
          color: t.text.tertiary,
          borderTop: `1px solid ${t.stroke.secondary}`,
          background: t.fill.secondary,
          flexShrink: 0,
        }}
      >
        Ctrl+Enter — отправить · Ctrl+K — шаблоны · F2 — следующий диалог
      </div>

      {closeDialogConfirmOpen ? (
        <ConfirmDialog
          t={t}
          titleId="close-dialog-title"
          title="Вы точно хотите закрыть данный диалог?"
          description={`Диалог будет завершён с тематикой «${closeTopic}» и исчезнет из очереди. Отменить закрытие после подтверждения будет нельзя.`}
          confirmLabel="Закрыть"
          onCancel={() => setCloseDialogConfirmOpen(false)}
          onConfirm={handleConfirmCloseDialog}
        />
      ) : null}

      {blockClientConfirmOpen ? (
        <ConfirmDialog
          t={t}
          titleId="block-client-title"
          title="Вы точно хотите заблокировать пользователя?"
          description="Клиент будет отмечен как заблокированный. Отправка сообщений в этом диалоге станет недоступна."
          confirmLabel="Заблокировать"
          onCancel={() => setBlockClientConfirmOpen(false)}
          onConfirm={handleConfirmBlockClient}
        />
      ) : null}

      {transferDialogOpen ? (
        <div
          role="presentation"
          style={{
            position: "absolute",
            inset: 0,
            background: "rgba(15, 28, 22, 0.45)",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            zIndex: 40,
            padding: 24,
          }}
          onClick={() => setTransferDialogOpen(false)}
        >
          <div
            role="dialog"
            aria-modal="true"
            aria-labelledby="transfer-dialog-title"
            style={{
              width: "100%",
              maxWidth: 460,
              background: t.bg.elevated,
              border: `1px solid ${t.stroke.secondary}`,
              borderRadius: 12,
              padding: "20px 22px",
              boxShadow: "0 12px 40px rgba(0,0,0,0.18)",
            }}
            onClick={(e) => e.stopPropagation()}
          >
            <Text
              id="transfer-dialog-title"
              weight="semibold"
              style={{ fontSize: 16, marginBottom: 8, color: t.text.primary }}
            >
              Перевести диалог
            </Text>
            <Text style={{ fontSize: 13, color: t.text.secondary, lineHeight: 1.45, marginBottom: 14 }}>
              Выберите оператора отдела, которому нужно передать обращение.
            </Text>
            <Text style={{ fontSize: 12, color: t.text.secondary, marginBottom: 6 }}>
              Оператор
            </Text>
            {transferOperatorOptions.length > 0 ? (
              <Select
                value={transferOperatorName}
                onChange={setTransferOperatorName}
                options={transferOperatorOptions}
                style={{ marginBottom: 16 }}
              />
            ) : (
              <Text style={{ fontSize: 13, color: t.text.tertiary, marginBottom: 16 }}>
                Нет доступных операторов для перевода.
              </Text>
            )}
            <Row style={{ gap: 8, justifyContent: "flex-end" }}>
              <Button variant="secondary" onClick={() => setTransferDialogOpen(false)}>
                Отмена
              </Button>
              <Button
                variant="primary"
                disabled={!transferOperatorName.trim()}
                onClick={handleConfirmTransferDialog}
              >
                Перевести
              </Button>
            </Row>
          </div>
        </div>
      ) : null}

      {editMessageTarget ? (
        <PromptDialog
          t={t}
          scheme={scheme}
          titleId="edit-message-title"
          title="Редактировать сообщение"
          description="Изменённый текст увидит клиент. Сообщение будет помечено как отредактированное."
          label="Текст сообщения"
          value={editMessageText}
          confirmLabel="Сохранить"
          multiline
          onChange={setEditMessageText}
          onCancel={() => setEditMessageTarget(null)}
          onConfirm={handleConfirmEditMessage}
        />
      ) : null}

      {deleteMessageTarget ? (
        <ConfirmDialog
          t={t}
          titleId="delete-message-title"
          title="Удалить сообщение?"
          description="Сообщение будет скрыто в переписке для обеих сторон. Отменить удаление нельзя."
          confirmLabel="Удалить"
          onCancel={() => setDeleteMessageTarget(null)}
          onConfirm={handleConfirmDeleteMessage}
        />
      ) : null}
    </div>
  );
}
