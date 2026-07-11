export default {
  content: ["./index.html", "./src/**/*.{js,ts,jsx,tsx}"],
  theme: {
    extend: {
      // Two-tone warm system: espresso surfaces, cream ink. One family (Inter),
      // hierarchy carried by size/weight/tracking, hairlines over shadows.
      colors: {
        bg: "#30231E",          // espresso body
        surface: "#3A2B25",     // raised panels/rows
        sunken: "#251B17",      // code blocks, wells
        ink: "#F5EFDF",         // cream text (~12:1 on bg)
        "ink-dim": "#C9BBAA",   // secondary text (~7:1 on bg)
        "ink-faint": "#A5947F", // tertiary/labels (~4.6:1 on bg)
        line: "#4B3E39",        // hairline borders
        ok: "#A8C9A0",
        warn: "#D9C08A",
        err: "#DB9C8B",
      },
      fontFamily: {
        sans: "'Inter', system-ui, -apple-system, 'Segoe UI', Roboto, sans-serif",
        mono: "ui-monospace, 'Cascadia Code', 'SF Mono', Consolas, monospace",
      },
      fontSize: {
        xs: ["12px", "16px"],
        sm: ["13px", "18px"],
        base: ["14px", "20px"],
        lg: ["15px", "22px"],
        xl: ["17px", "24px"],
        "2xl": ["20px", "28px"],
        "3xl": ["24px", "30px"],
        "4xl": ["30px", "36px"],
      },
      letterSpacing: {
        tightest: "-0.035em",
        kicker: "0.08em",
      },
      borderColor: { DEFAULT: "#4B3E39" },
    },
  },
  plugins: [],
};
