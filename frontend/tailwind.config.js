/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{js,ts,jsx,tsx}"],
  darkMode: "class",
  theme: {
    extend: {
      colors: {
        brand: {
          50: "#eff6ff",
          100: "#dbeafe",
          200: "#bfdbfe",
          300: "#93c5fd",
          400: "#60a5fa",
          500: "#3b82f6",
          600: "#2563eb",
          700: "#1d4ed8",
          800: "#1e40af",
          900: "#1e3a8a",
          950: "#172554",
        },
        sentiment: {
          positive: "#10b981",
          "positive-light": "#d1fae5",
          negative: "#ef4444",
          "negative-light": "#fee2e2",
          neutral: "#6b7280",
          "neutral-light": "#f3f4f6",
        },
      },
    },
  },
  plugins: [],
};
