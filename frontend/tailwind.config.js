/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{js,jsx,ts,tsx}"],
  theme: {
    extend: {
      keyframes: {
        fall: {
          "0%": { opacity: "1", transform: "translateY(0) scale(1)" },
          "100%": { opacity: "0", transform: "translateY(100px) scale(0.8)" },
        },
      },
      animation: {
        fall: "fall 0.6s ease-out forwards",
      },
    },
  },
  plugins: [],
};
