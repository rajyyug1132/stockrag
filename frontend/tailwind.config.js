export default {
  content: ["./index.html", "./src/**/*.{js,ts,jsx,tsx}"],
  theme: {
    extend: {
      // Two-tone warm system: espresso surfaces, cream ink. One family (Inter),
      // hierarchy carried by size/weight/tracking, hairlines over shadows.
      colors: {
        bg: "#0A0D0C",          // near-black, faint cool/teal cast
        surface: "#121614",     // glass cards / raised panels
        sunken: "#0D100F",      // inputs, wells
        ink: "#E8EDEB",         // near-white text (~14:1 on bg)
        "ink-dim": "#9AA6A2",   // secondary text (~7:1 on bg)
        "ink-faint": "#69736F", // tertiary/labels/placeholders
        line: "#1E2825",        // hairline borders
        accent: "#34E5A0",      // mint — primary actions
        "accent-dim": "#4ADEA0",// mint for kickers/nav on dark
        ok: "#34E5A0",
        warn: "#E5C97A",
        err: "#FF6B6B",
      },
      fontFamily: {
        sans: "'Inter', system-ui, -apple-system, 'Segoe UI', sans-serif",
        serif: "'Newsreader', Georgia, 'Times New Roman', serif",
        mono: "'JetBrains Mono', ui-monospace, 'Cascadia Code', Consolas, monospace",
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
