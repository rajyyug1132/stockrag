export default {
  content: ["./index.html", "./src/**/*.{js,ts,jsx,tsx}"],
  theme: {
    extend: {
      colors: {
        black: "#000000",
        white: "#ffffff",
        gray: {
          50: "#fafafa",
          100: "#f5f5f5",
          200: "#eeeeee",
          300: "#e5e5e5",
          400: "#d9d9d9",
          500: "#cccccc",
          600: "#999999",
          700: "#666666",
          800: "#333333",
          900: "#1a1a1a",
        },
        accent: "#0052cc",
      },
      fontFamily: {
        sans: "system-ui, -apple-system, 'Segoe UI', Roboto, sans-serif",
        mono: "ui-monospace, 'Cascadia Code', 'SF Mono', Consolas, monospace",
      },
      fontSize: {
        xs: ["12px", "16px"],
        sm: ["13px", "18px"],
        base: ["14px", "20px"],
        lg: ["15px", "22px"],
        xl: ["16px", "24px"],
        "2xl": ["18px", "28px"],
        "3xl": ["20px", "28px"],
      },
      borderColor: { DEFAULT: "#e5e5e5" },
      borderWidth: { DEFAULT: "1px", hairline: "1px" },
    },
  },
  plugins: [],
};
