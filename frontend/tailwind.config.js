/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,jsx,ts,tsx}"
  ],

  theme: {
    extend: {
      fontFamily: {
        sans: [
          "Inter",
          "ui-sans-serif",
          "system-ui",
          "-apple-system",
          "BlinkMacSystemFont",
          "Segoe UI",
          "sans-serif"
        ],
        display: [
          "Inter",
          "ui-sans-serif",
          "system-ui",
          "sans-serif"
        ],
        mono: [
          "JetBrains Mono",
          "SFMono-Regular",
          "Consolas",
          "monospace"
        ]
      },

      fontSize: {
        "2xs": [
          "10px",
          {
            lineHeight: "14px"
          }
        ]
      },

      colors: {
        canvas: "#f5f7fb",
        surface: "#ffffff",
        ink: "#172033",
        "ink-2": "#526078",
        "ink-3": "#8793a8",

        rule: "#e5eaf2",
        ruleStrong: "#d4dbe7",

        provider: "#2563eb",
        "provider-deep": "#1d4ed8",
        "provider-soft": "#eff6ff",
        "provider-line": "#bfdbfe",

        payer: "#7c3aed",
        "payer-deep": "#6d28d9",
        "payer-soft": "#f5f3ff",
        "payer-line": "#ddd6fe",

        approve: "#059669",
        "approve-soft": "#ecfdf5",
        "approve-line": "#a7f3d0",

        deny: "#dc2626",
        "deny-soft": "#fef2f2",
        "deny-line": "#fecaca",

        review: "#d97706",
        "review-soft": "#fffbeb",
        "review-line": "#fde68a",

        info: "#0284c7",
        "info-soft": "#f0f9ff",
        "info-line": "#bae6fd"
      },

      boxShadow: {
        card: "0 1px 2px rgba(15,23,42,.04), 0 8px 30px rgba(15,23,42,.04)",
        soft: "0 10px 40px rgba(15,23,42,.08)",
        elevated: "0 20px 60px rgba(15,23,42,.12)"
      },

      borderRadius: {
        xl: "14px",
        "2xl": "18px"
      },

      animation: {
        "fade-in": "fadeIn .25s ease-out",
        "slide-up": "slideUp .3s ease-out",
        "pulse-soft": "pulseSoft 2s ease-in-out infinite"
      },

      keyframes: {
        fadeIn: {
          "0%": {
            opacity: "0"
          },
          "100%": {
            opacity: "1"
          }
        },

        slideUp: {
          "0%": {
            opacity: "0",
            transform: "translateY(8px)"
          },
          "100%": {
            opacity: "1",
            transform: "translateY(0)"
          }
        },

        pulseSoft: {
          "0%, 100%": {
            opacity: ".55"
          },
          "50%": {
            opacity: "1"
          }
        }
      }
    }
  },

  plugins: []
}