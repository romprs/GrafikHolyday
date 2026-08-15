// Нерабочие праздничные дни (ст. 112 ТК РФ), без учёта переноса выходных
// дней по ежегодным постановлениям Правительства — перенос объявляется не
// заранее на все планируемые годы, поэтому здесь не учитывается.
const HOLIDAY_MONTH_DAY: [month: number, day: number][] = [
  [0, 1],
  [0, 2],
  [0, 3],
  [0, 4],
  [0, 5],
  [0, 6],
  [0, 7],
  [0, 8], // Новогодние каникулы + Рождество Христово
  [1, 23], // День защитника Отечества
  [2, 8], // Международный женский день
  [4, 1], // Праздник Весны и Труда
  [4, 9], // День Победы
  [5, 12], // День России
  [10, 4], // День народного единства
];

export function isHoliday(date: Date): boolean {
  return HOLIDAY_MONTH_DAY.some(([month, day]) => date.getMonth() === month && date.getDate() === day);
}

export function isWeekend(date: Date): boolean {
  const day = date.getDay();
  return day === 0 || day === 6;
}

export function isNonWorkingDay(date: Date): boolean {
  return isWeekend(date) || isHoliday(date);
}
