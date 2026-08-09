import { useCallback, useEffect, useMemo, useRef, useState, type CSSProperties, type JSX, type ReactNode } from 'react'
import type { ArmTheme } from './theme'
import {
  acceptDialog,
  blockDialogRemote,
  closeDialogRemote,
  formatWaitMmSs,
  getDialog,
  listDialogs,
  maskPhone,
  onlineChatArmWsUrl,
  sendOperatorMessage,
  type OnlineChatDialog,
  type OnlineChatMessage,
} from '../api/onlineChatApi'
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
type ArmStatsTab = "dialogs" | "history" | "stats" | "employees" | "settings";
type ArmRole = "operator" | "supervisor" | "admin";

const ARM_STATS_RAIL_WIDTH = 52;
const ARM_STATS_DRAWER_WIDTH = ARM_STATS_RAIL_WIDTH;

const ARM_ROLE_LABELS: Record<ArmRole, string> = {
  operator: "Оператор КЦ",
  supervisor: "Супервизор",
  admin: "Администратор",
};

const ARM_STATS_TABS: { id: ArmStatsTab; label: string }[] = [
  { id: "dialogs", label: "Диалоги" },
  { id: "history", label: "История" },
  { id: "stats", label: "Статистика" },
  { id: "employees", label: "Сотрудники" },
  { id: "settings", label: "Настройки" },
];

const ARM_STATS_TAB_ROLES: Record<ArmStatsTab, ArmRole[]> = {
  dialogs: ["operator", "supervisor", "admin"],
  history: ["operator", "supervisor", "admin"],
  stats: ["operator", "supervisor", "admin"],
  employees: ["supervisor", "admin"],
  settings: ["operator", "supervisor", "admin"],
};

function armStatsTabsForRole(role: ArmRole): typeof ARM_STATS_TABS {
  return ARM_STATS_TABS.filter((tab) => ARM_STATS_TAB_ROLES[tab.id].includes(role));
}

function firstArmStatsTabForRole(role: ArmRole): ArmStatsTab {
  return armStatsTabsForRole(role)[0]?.id ?? "dialogs";
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
  result?: "offline" | "lost" | "declined";
  operatorName?: string;
  readOnly?: boolean;
  /** True when item comes from Django online_chat API (not canvas mock). */
  live?: boolean;
  phone?: string;
  firstName?: string;
  lastName?: string;
};

function dialogToQueueItem(
  dialog: OnlineChatDialog,
  options?: { active?: boolean },
): QueueItem {
  return {
    id: dialog.id,
    name: dialog.client_name || "Клиент",
    channel: dialog.channel === "widget" ? "Сайт" : dialog.channel,
    dept: "Розничные продукты",
    preview: dialog.preview || "—",
    wait: formatWaitMmSs(dialog.wait_seconds),
    urgent: dialog.wait_seconds >= 120,
    active: options?.active,
    live: true,
    phone: dialog.client_phone,
    firstName: dialog.client_first_name,
    lastName: dialog.client_last_name,
    operatorName: dialog.operator_name || undefined,
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

const LOST_QUEUE: QueueItem[] = [
  {
    id: "l1",
    name: "ООО «Вектор»",
    channel: "Сайт",
    dept: "Юрлица",
    preview: "Тарифы на РКО для ИП",
    wait: "—",
    urgent: false,
    result: "lost",
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

type QueueSectionId = "waiting" | "mine" | "colleagues" | "offline" | "lost" | "shared";

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
  { id: "lost", title: "Потерянные", count: 1, items: LOST_QUEUE, defaultExpanded: false },
  { id: "shared", title: "Общая очередь", count: 5, items: SHARED_QUEUE, defaultExpanded: false },
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

const ACTIVE_SUMMARY_HISTORY: SummaryHistoryData = {
  summary:
    "Клиент обращался 12.05 (чат, лимит ATM) и 03.04 (Telegram). Текущая тема повторяется — лимиты.",
  detailedSummary:
    "За 90 дней — 3 обращения по теме лимитов и переводов.\n\n12.05.2026 · онлайн-чат · лимит ATM — оператор Сидорова М.В. Разъяснены суточные лимиты карты Visa, клиент подтвердил понимание.\n\n03.04.2026 · Telegram · лимиты переводов — оператор Козлов Д.А. Проверены настройки лимита в мобильном банке.\n\n15.03.2026 · телефония (Oktell) · перевод в РФ — оператор Петрова А.С., длит. 4:12. Рекомендован раздел «Платежи → За рубеж».\n\nПовторная тема: лимиты. Рекомендация: проверить актуальный лимит в мобильном банке перед ответом.",
  preview: "Последнее: лимит ATM · 12.05",
};

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
              background: t.palette.diffStripRemoved,
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
        <Pill tone={item.urgent ? "warning" : "neutral"} size="sm">
          {item.wait}
        </Pill>
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
            <Pill tone={item.urgent ? "warning" : "neutral"} size="sm">
              {item.wait}
            </Pill>
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
              background: t.palette.diffStripRemoved,
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
              tone={item.result === "offline" ? "warning" : item.result === "lost" ? "warning" : "neutral"}
            >
              {item.result === "offline" ? "offline" : item.result === "lost" ? "потерянный" : "отказ"}
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

function ReadReceiptMarks({ color }: { color: string }): JSX.Element {
  return (
    <span
      aria-hidden
      style={{
        display: "inline-flex",
        alignItems: "center",
        marginLeft: 4,
        color,
        fontSize: 11,
        lineHeight: 1,
        letterSpacing: "-0.22em",
        fontWeight: 700,
      }}
    >
      ✓✓
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
}: {
  t: ArmTheme;
  scheme: SchemePalette;
  side: "client" | "operator" | "system";
  text: string;
  time?: string;
  label?: string;
  avatarInitials?: string;
  avatarColor?: string;
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
        <Text
          style={{
            fontSize: 13,
            lineHeight: 1.45,
            color: t.text.primary,
            fontWeight: 600,
          }}
        >
          {text}
        </Text>
        {time ? (
          <div
            style={{
              display: "flex",
              justifyContent: "flex-end",
              alignItems: "center",
              marginTop: 8,
              fontSize: 10,
              lineHeight: 1,
              color: t.text.tertiary,
            }}
          >
            <span>{time}</span>
            {isOp ? <ReadReceiptMarks color={scheme.accentControl} /> : null}
          </div>
        ) : null}
      </div>
      {isOp && avatarInitials ? (
        <AvatarCircle initials={avatarInitials} background={avatarBg} color={avatarFg} />
      ) : null}
    </div>
  );
}

function ArmStatsRailTab({
  t,
  scheme,
  label,
  active,
  onClick,
}: {
  t: ArmTheme;
  scheme: SchemePalette;
  label: string;
  active: boolean;
  onClick: () => void;
}): JSX.Element {
  return (
    <button
      type="button"
      role="tab"
      aria-selected={active}
      title={label}
      onClick={onClick}
      style={{
        border: "none",
        borderLeft: `3px solid ${active ? scheme.accent : "transparent"}`,
        background: active ? t.fill.tertiary : "transparent",
        color: active ? scheme.accentControl : t.text.secondary,
        borderRadius: 0,
        padding: "8px 2px",
        fontSize: 9,
        fontFamily: "inherit",
        cursor: "pointer",
        pointerEvents: "auto",
        lineHeight: 1.1,
        width: "100%",
        display: "flex",
        flexDirection: "column",
        alignItems: "center",
        justifyContent: "center",
        textAlign: "center",
        minHeight: 52,
        flexShrink: 0,
      }}
    >
      <span
        style={{
          writingMode: "vertical-rl",
          textOrientation: "mixed",
          transform: "rotate(180deg)",
          maxHeight: 72,
          overflow: "hidden",
          whiteSpace: "nowrap",
        }}
      >
        {label}
      </span>
    </button>
  );
}

function ArmStatsDrawer({
  t,
  scheme,
  armRole,
  statsTab,
  onTabChange,
  onClose,
}: {
  t: ArmTheme;
  scheme: SchemePalette;
  armRole: ArmRole;
  statsTab: ArmStatsTab;
  onTabChange: (tab: ArmStatsTab) => void;
  onClose: () => void;
}): JSX.Element {
  const visibleTabs = armStatsTabsForRole(armRole);
  const railButtonStyle: CSSProperties = {
    border: "none",
    background: "transparent",
    color: t.text.secondary,
    lineHeight: 1,
    cursor: "pointer",
    padding: "6px 2px",
    fontFamily: "inherit",
    flex: 1,
    minWidth: 0,
  };

  return (
    <div
      id="arm-stats-drawer"
      role="navigation"
      aria-label="Меню разделов"
      style={{
        width: ARM_STATS_DRAWER_WIDTH,
        height: "100%",
        flexShrink: 0,
        display: "flex",
        flexDirection: "column",
        background: scheme.headerBg,
        ...panelStyle(t, { borderRadius: 0, borderTop: "none", borderBottom: "none", borderLeft: "none" }),
      }}
    >
      <Row
        style={{
          flexShrink: 0,
          borderBottom: `1px solid ${t.stroke.secondary}`,
          alignItems: "stretch",
        }}
      >
        <button
          type="button"
          title="Скрыть меню"
          aria-label="Скрыть меню"
          onClick={onClose}
          style={{
            ...railButtonStyle,
            fontSize: 14,
            color: scheme.accentControl,
          }}
        >
          ☰
        </button>
        <button
          type="button"
          title="Закрыть меню"
          aria-label="Закрыть меню"
          onClick={onClose}
          style={{
            ...railButtonStyle,
            fontSize: 16,
          }}
        >
          ×
        </button>
      </Row>
      <div role="tablist" aria-label="Разделы меню" style={{ display: "flex", flexDirection: "column", flex: 1, minHeight: 0 }}>
        {visibleTabs.map((tab) => (
          <ArmStatsRailTab
            key={tab.id}
            t={t}
            scheme={scheme}
            label={tab.label}
            active={statsTab === tab.id}
            onClick={() => onTabChange(tab.id)}
          />
        ))}
      </div>
    </div>
  );
}

export function ArmOperatorView({
  t,
  scheme,
  selectedQueue,
  onSelectQueue,
  reply,
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
  onToggleTheme,
}: {
  t: ArmTheme;
  scheme: SchemePalette;
  selectedQueue: string;
  onSelectQueue: (id: string) => void;
  reply: string;
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
  onToggleTheme: () => void;
}): JSX.Element {
  const [armRole, setArmRole] = useState<ArmRole>("operator");
  const [closedDialogIds, setClosedDialogIds] = useState<Record<string, boolean>>({});
  const [blockedDialogIds, setBlockedDialogIds] = useState<Record<string, boolean>>({});
  /** Live widget dialogs land in «Общая очередь» until an operator takes them. */
  const [liveShared, setLiveShared] = useState<QueueItem[]>([]);
  const [liveMine, setLiveMine] = useState<QueueItem[]>([]);
  const [liveMessages, setLiveMessages] = useState<OnlineChatMessage[]>([]);
  const acceptedLiveRef = useRef<Record<string, boolean>>({});
  const selectedQueueRef = useRef(selectedQueue);
  selectedQueueRef.current = selectedQueue;

  const refreshLiveQueues = useCallback(async () => {
    try {
      const [waiting, activeDialogs] = await Promise.all([
        listDialogs("waiting"),
        listDialogs("active"),
      ]);
      setLiveShared(
        waiting.map((dialog, index) => dialogToQueueItem(dialog, { active: index === 0 })),
      );
      setLiveMine(
        activeDialogs.map((dialog, index) => dialogToQueueItem(dialog, { active: index === 0 })),
      );
    } catch {
      /* Backend may be offline in pure UI/story mode — keep mock queues. */
    }
  }, []);

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
            payload?: OnlineChatMessage & { dialog_id?: string };
          };
          if (
            data.type === "message.created" &&
            data.payload?.dialog_id &&
            data.payload.dialog_id === selectedQueueRef.current
          ) {
            setLiveMessages((prev) => {
              if (prev.some((item) => item.id === data.payload?.id)) return prev;
              return [...prev, data.payload as OnlineChatMessage];
            });
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

  const visibleSections = useMemo(() => {
    const sections = queueSectionsForRole(armRole);
    return sections.map((section) => {
      if (section.id === "shared") {
        const items = [...liveShared, ...section.items];
        return {
          ...section,
          items,
          count: items.length,
          /* Auto-expand when real widget dialogs are waiting. */
          defaultExpanded: liveShared.length > 0 ? true : section.defaultExpanded,
        };
      }
      if (section.id === "mine") {
        const items = [...liveMine, ...section.items];
        return { ...section, items, count: items.length };
      }
      return section;
    });
  }, [armRole, liveShared, liveMine]);

  const remainingDialogs = visibleSections
    .flatMap((section) => section.items)
    .filter((item) => !closedDialogIds[item.id]);
  const active = remainingDialogs.find((q) => q.id === selectedQueue) ?? remainingDialogs[0] ?? null;
  const hasActiveDialog = !!active;
  const isReadOnly = viewMode === "colleague";
  const isClientBlocked = !!(active && blockedDialogIds[active.id]);
  const composerLocked = isReadOnly || isClientBlocked || !hasActiveDialog;

  const clientForCard: ClientInfoData = active?.live
    ? {
        ...ACTIVE_CLIENT,
        name: active.name,
        phoneFull: active.phone || "—",
        phoneMasked: active.phone ? maskPhone(active.phone) : "—",
        dialogNo: `№ ${active.id.replace(/-/g, "").slice(0, 6)}`,
        email: "—",
        channel: active.channel,
        entryChannel: "Виджет сайта",
        visitorId: active.id.slice(0, 12),
      }
    : ACTIVE_CLIENT;

  useEffect(() => {
    if (!active?.live) {
      setLiveMessages([]);
      return;
    }
    let cancelled = false;
    void getDialog(active.id)
      .then((dialog) => {
        if (!cancelled) setLiveMessages(dialog.messages ?? []);
      })
      .catch(() => {
        if (!cancelled) setLiveMessages([]);
      });

    const isSharedLive = liveShared.some((item) => item.id === active.id);
    if (isSharedLive && !acceptedLiveRef.current[active.id]) {
      acceptedLiveRef.current[active.id] = true;
      void acceptDialog(active.id)
        .then((dialog) => {
          if (!cancelled) {
            setLiveMessages(dialog.messages ?? []);
            void refreshLiveQueues();
          }
        })
        .catch(() => {
          acceptedLiveRef.current[active.id] = false;
        });
    }

    return () => {
      cancelled = true;
    };
  }, [active?.id, active?.live, liveShared, refreshLiveQueues]);

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
  const [statsDrawerOpen, setStatsDrawerOpen] = useState(false);
  const [statsTab, setStatsTab] = useState<ArmStatsTab>("dialogs");

  useEffect(() => {
    if (canvasBuild !== CANVAS_MOCKUP_VERSION) {
      setCanvasBuild(CANVAS_MOCKUP_VERSION);
      setStatsDrawerOpen(false);
      setStatsTab("dialogs");
    }
  }, [canvasBuild, setCanvasBuild, setStatsDrawerOpen, setStatsTab]);

  useEffect(() => {
    if (!ARM_STATS_TAB_ROLES[statsTab].includes(armRole)) {
      setStatsTab(firstArmStatsTabForRole(armRole));
    }
  }, [armRole, statsTab, setStatsTab]);

  const toggleStatsDrawer = () => {
    setStatsDrawerOpen((open) => {
      const next = !open;
      if (next && !ARM_STATS_TAB_ROLES[statsTab].includes(armRole)) {
        setStatsTab(firstArmStatsTabForRole(armRole));
      }
      return next;
    });
  };
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
    if (liveShared.length === 0) return;
    setExpandedSections((prev) => (prev.shared ? prev : { ...prev, shared: true }));
  }, [liveShared.length]);

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
      void closeDialogRemote(closingId).then(() => void refreshLiveQueues()).catch(() => {});
    }
    const nextDialog = remainingDialogs.find((item) => item.id !== closingId);
    if (nextDialog) {
      onSelectQueue(nextDialog.id);
      setComposerNotice(`Диалог с ${closedName} закрыт.`);
    } else {
      onSelectQueue("");
      setComposerNotice("Диалог закрыт. Очередь пуста.");
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
      void blockDialogRemote(active.id).then(() => void refreshLiveQueues()).catch(() => {});
    }
    setComposerNotice(`Клиент ${active.name} заблокирован.`);
  };

  const deliverReply = (notice: string) => {
    const text = reply.trim();
    if (!text || !active || composerLocked) return;
    if (active.live) {
      void sendOperatorMessage(active.id, text)
        .then((message) => {
          setLiveMessages((prev) =>
            prev.some((item) => item.id === message.id) ? prev : [...prev, message],
          );
          onReplyChange("");
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
    setSpellWarning(false);
    setComposerNotice(notice);
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
          gap: 16,
        }}
      >
        <div style={{ flex: 1, minWidth: 0 }}>
          <Row style={{ gap: 12, alignItems: "center", flexWrap: "wrap", minWidth: 0 }}>
            <button
              type="button"
              aria-expanded={statsDrawerOpen}
              aria-controls="arm-stats-drawer"
              title={statsDrawerOpen ? "Скрыть сдвижную панель" : "Меню: диалоги, история, статистика"}
              onClick={toggleStatsDrawer}
              style={{
                border: statsDrawerOpen ? `1px solid ${scheme.accent}` : `1px solid ${t.stroke.secondary}`,
                background: statsDrawerOpen ? t.fill.tertiary : "transparent",
                color: statsDrawerOpen ? scheme.accentControl : t.text.secondary,
                borderRadius: RADIUS_SM,
                padding: "4px 10px",
                fontSize: 12,
                fontFamily: "inherit",
                cursor: "pointer",
                lineHeight: 1.3,
              }}
            >
              ☰ Меню
            </button>
            <Text weight="semibold">Беларусбанк · Онлайн-чат</Text>
            <button
              type="button"
              className="arm-theme-toggle"
              title={t.kind === "light" ? "Включить тёмную тему" : "Включить светлую тему"}
              aria-label={t.kind === "light" ? "Тёмная тема" : "Светлая тема"}
              onClick={onToggleTheme}
              style={{
                width: 34,
                height: 34,
                display: "inline-flex",
                alignItems: "center",
                justifyContent: "center",
                border: `1px solid ${scheme.accent}`,
                background: t.fill.tertiary,
                color: scheme.accentControl,
                borderRadius: RADIUS_SM,
                padding: 0,
                fontFamily: "inherit",
                cursor: "pointer",
              }}
            >
              <svg width="18" height="18" viewBox="0 0 24 24" fill="none" aria-hidden>
                <circle cx="12" cy="12" r="4.2" stroke="currentColor" strokeWidth="1.8" />
                <path
                  d="M12 3v1.6M12 19.4V21M4.6 12H3M21 12h-1.6M6.2 6.2l1.1 1.1M16.7 16.7l1.1 1.1M6.2 17.8l1.1-1.1M16.7 7.3l1.1-1.1"
                  stroke="currentColor"
                  strokeWidth="1.8"
                  strokeLinecap="round"
                />
              </svg>
            </button>
          </Row>
          <Row
            style={{
              gap: 6,
              flexWrap: "wrap",
              alignItems: "center",
              marginTop: 10,
              minWidth: 0,
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
        <Stack gap={6} style={{ alignItems: "flex-end", flexShrink: 0, justifyContent: "center" }}>
          <Text
            style={{
              fontSize: 15,
              fontWeight: 600,
              color: t.text.primary,
              whiteSpace: "nowrap",
            }}
          >
            Иванов И.И. · {ARM_ROLE_LABELS[armRole]}
          </Text>
          <Row style={{ gap: 5, flexWrap: "wrap", justifyContent: "flex-end" }}>
            {(["operator", "supervisor", "admin"] as ArmRole[]).map((role) => (
              <Pill
                key={role}
                size="sm"
                active={armRole === role}
                onClick={() => setArmRole(role)}
                title={`Роль: ${ARM_ROLE_LABELS[role]}`}
              >
                {role === "operator" ? "Опер." : role === "supervisor" ? "Суп." : "Адм."}
              </Pill>
            ))}
          </Row>
        </Stack>
      </div>

      <div style={{ display: "flex", flex: 1, minHeight: 0, position: "relative", overflow: "hidden" }}>
        <div
          style={{
            width: statsDrawerOpen ? ARM_STATS_DRAWER_WIDTH : 0,
            flexShrink: 0,
            overflow: "hidden",
            transition: "width 0.22s ease",
            height: "100%",
            minHeight: 0,
          }}
        >
          <ArmStatsDrawer
            t={t}
            scheme={scheme}
            armRole={armRole}
            statsTab={statsTab}
            onTabChange={setStatsTab}
            onClose={() => setStatsDrawerOpen(false)}
          />
        </div>
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
                  border: `1px solid ${t.stroke.secondary}`,
                  background: t.fill.secondary,
                  color: t.text.secondary,
                  fontSize: 11,
                  cursor: "pointer",
                  padding: "2px 6px",
                  fontFamily: "inherit",
                  borderRadius: RADIUS_SM,
                  display: "flex",
                  alignItems: "center",
                  gap: 4,
                  lineHeight: 1.3,
                }}
              >
                <span aria-hidden style={{ fontSize: 12, lineHeight: 1 }}>
                  {allSectionsCollapsed ? "⊞" : "⊟"}
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
                  <Text style={{ fontSize: 12, color: t.text.secondary }}>#{active.id}8472</Text>
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
                <Pill tone={active.urgent ? "warning" : "neutral"} size="sm">
                  SLA {active.wait}
                </Pill>
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
            style={{
              flex: 1,
              minHeight: 0,
              padding: 16,
              overflowY: "auto",
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
                        label="Иванов И.И. · оператор"
                        avatarInitials="ИИ"
                        text={message.text}
                        time={messageTimeLabel(message.created_at)}
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
                  text="Оператор Иванов И.И. подключился к диалогу"
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
                  label="Иванов И.И. · оператор"
                  avatarInitials="ИИ"
                  text="Проверяю лимиты по вашей карте, одну минуту."
                  time="10:04"
                />
              </>
            )}
          </div>
          <div style={{ padding: 12, borderTop: `1px solid ${t.stroke.secondary}`, flexShrink: 0 }}>
            <Row style={{ gap: 8, marginBottom: 8, flexWrap: "wrap", alignItems: "center" }}>
              <Button variant="secondary" disabled={composerLocked}>Шаблоны</Button>
              <Button variant="secondary" disabled={composerLocked}>Файл</Button>
              <Button variant="secondary" disabled={composerLocked}>Перевести</Button>
            </Row>
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
            data={ACTIVE_SUMMARY_HISTORY}
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
          description="Диалог будет завершён и исчезнет из очереди. Отменить закрытие после подтверждения будет нельзя."
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
    </div>
  );
}
