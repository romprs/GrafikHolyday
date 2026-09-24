// Простые однострочные SVG-иконки для боковой панели навигации — без
// внешних иконочных шрифтов/библиотек, чтобы не тащить лишнюю зависимость
// ради десятка пунктов меню.
const common = { width: 16, height: 16, viewBox: "0 0 16 16", fill: "none", stroke: "currentColor", strokeWidth: 1.4 } as const;

export const NavIcon = {
  doc: () => (
    <svg {...common}><rect x="2" y="3" width="12" height="10" rx="1.5" /><line x1="2" y1="6.5" x2="14" y2="6.5" /></svg>
  ),
  plus: () => (
    <svg {...common}><line x1="8" y1="3" x2="8" y2="13" /><line x1="3" y1="8" x2="13" y2="8" /></svg>
  ),
  star: () => (
    <svg {...common}><path d="M8 2 L9.5 6 L14 6.5 L10.5 9.5 L11.5 14 L8 11.5 L4.5 14 L5.5 9.5 L2 6.5 L6.5 6 Z" /></svg>
  ),
  grid: () => (
    <svg {...common}><rect x="2" y="2.5" width="12" height="11" rx="1.5" /><line x1="2" y1="6" x2="14" y2="6" /><rect x="4.5" y="8" width="2.5" height="2.5" /></svg>
  ),
  lock: () => (
    <svg {...common}><rect x="4" y="7" width="8" height="6" rx="1" /><path d="M6 7 V5 a2 2 0 0 1 4 0 V7" /></svg>
  ),
  users: () => (
    <svg {...common}><circle cx="6" cy="6" r="2" /><path d="M2 14 v-1.5 A3 3 0 0 1 6 9 A3 3 0 0 1 10 12.5 V14" /><circle cx="12" cy="6.5" r="1.6" /><path d="M10.5 9.2 A2.6 2.6 0 0 1 14 12 v1" /></svg>
  ),
  swap: () => (
    <svg {...common}><path d="M3 5 h9 M9 2 l3 3 l-3 3" /><path d="M13 11 h-9 M7 8 l-3 3 l3 3" /></svg>
  ),
  all: () => (
    <svg {...common}><rect x="2" y="2.5" width="12" height="11" rx="1.5" /><line x1="2" y1="6" x2="14" y2="6" /><line x1="5.5" y1="2.5" x2="5.5" y2="1" /><line x1="10.5" y1="2.5" x2="10.5" y2="1" /></svg>
  ),
  sync: () => (
    <svg {...common}><path d="M3 8 a5 5 0 0 1 9 -3 M13 8 a5 5 0 0 1 -9 3" /><path d="M12 2 v3 h-3 M4 14 v-3 h3" /></svg>
  ),
  sliders: () => (
    <svg {...common}>
      <line x1="3" y1="4" x2="13" y2="4" /><circle cx="6" cy="4" r="1.6" fill="currentColor" stroke="none" />
      <line x1="3" y1="8" x2="13" y2="8" /><circle cx="10" cy="8" r="1.6" fill="currentColor" stroke="none" />
      <line x1="3" y1="12" x2="13" y2="12" /><circle cx="7" cy="12" r="1.6" fill="currentColor" stroke="none" />
    </svg>
  ),
  plug: () => (
    <svg {...common}><path d="M6 2 v4 M10 2 v4 M4.5 6 h7 v2 a3.5 3.5 0 0 1 -7 0 z" /><line x1="8" y1="11.5" x2="8" y2="14" /></svg>
  ),
  clock: () => (
    <svg {...common}><circle cx="8" cy="8" r="6" /><path d="M8 5 v3 l2 1.5" /></svg>
  ),
};

export type NavIconKey = keyof typeof NavIcon;
