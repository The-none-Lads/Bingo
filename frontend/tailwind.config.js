// tailwind.config.js
/** @type {import('tailwindcss').Config} */
// tailwind.config.js - REPLACE your keyframes and animation sections with this:

export default {
  content: ["./index.html", "./src/**/*.{js,jsx,ts,tsx}"],
  theme: {
    extend: {
      keyframes: {
        fall: {
          "0%": { opacity: "1", transform: "translateY(0) scale(1)" },
          "100%": { opacity: "0", transform: "translateY(100px) scale(0.8)" },
        },
        // FIXED: Roll in animation for new balls
        rollIn: {
          "0%": { 
            transform: "translateY(-50%) translateX(0) rotateZ(0deg)", 
            opacity: "0.5" 
          },
          "100%": { 
            transform: "translateY(-50%) translateX(140px) rotateZ(360deg)", 
            opacity: "1" 
          }
        },
        // FIXED: Drop off animation for oldest ball
        dropOff: {
          "0%": { 
            transform: "translateY(-50%) scale(1) rotateZ(0deg)", 
            opacity: "1" 
          },
          "50%": { 
            transform: "translateY(100px) scale(0.8) rotateZ(180deg)", 
            opacity: "0.5" 
          },
          "100%": { 
            transform: "translateY(250px) scale(0.3) rotateZ(360deg)", 
            opacity: "0" 
          }
        }
      },
      animation: {
        fall: "fall 0.6s ease-out forwards",
        rollIn: "rollIn 800ms cubic-bezier(0.34, 1.56, 0.64, 1) forwards",
        dropOff: "dropOff 700ms ease-in forwards"
      },
      boxShadow: {
        neonYellow: "0 0 12px rgba(255, 215, 0, 0.8), 0 0 24px rgba(255, 215, 0, 0.6)"
      }
    },
  },
  plugins: [],
};