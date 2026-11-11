// One source for colour, type, space and motion; components read only from here.
export const color = {
  paper: "#F1F3EF",
  card: "#FFFFFF",
  ink: "#1E2321",
  muted: "#5B635F",
  line: "#D5DAD5",
  panel: "#E4E8E3",
  supply: "#0F766E", // scooters on the street
  lost: "#D9480F", // people who found none
  truth: "#1E2321",
  naive: "#A1A9A4", // the censored or status-quo version
  method: "#3B5BDB", // the corrected or proposed version
  good: "#2B8A3E",
  bad: "#C92A2A",
  focus: "#3B5BDB",
  // sequential map for scooters available in a zone: none to many
  stock: ["#F1F3EF", "#C3E3DE", "#7CC2B8", "#2E9C8F", "#0F766E", "#0A4F4A"],
} as const;

export const font = { body: '"IBM Plex Sans", system-ui, sans-serif', code: "ui-monospace, Menlo, monospace" } as const;
export const size = { xs: 12, sm: 14, md: 16, lg: 20, xl: 28, xxl: 46 } as const;
export const weight = { regular: 400, medium: 500, semibold: 600, bold: 700 } as const;
export const space = [0, 4, 8, 12, 16, 24, 32, 48, 64, 96] as const;
export const radius = { sm: 3, md: 8, pill: 999 } as const;
export const measure = { text: 66, page: 1120, chart: 280, map: 460, axis: 44, dot: 6, cellGap: 2 } as const;
export const breakpoint = { narrow: 720 } as const;
export const motion = { fast: 0.2, step: 0.35, ease: [0.22, 1, 0.36, 1] as const, playMs: 450 } as const;
