/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  darkMode: 'class',
  theme: {
    extend: {
      colors: {
        // Bumblebee theme colors
        bumblebee: {
          yellow: '#fbbf24',      // Main yellow
          gold: '#f59e0b',        // Darker yellow/gold
          amber: '#fcd34d',       // Bright yellow
          dark: '#0a0a0a',        // Almost black
          darker: '#000000',      // Pure black
          gray: {
            900: '#1a1a1a',       // Charcoal
            800: '#2d2d2d',       // Dark gray
            700: '#404040',       // Medium dark
            600: '#525252',       // Medium
            500: '#737373',       // Light medium
            400: '#a3a3a3',       // Light gray
            300: '#d4d4d4',       // Very light
            200: '#e5e5e5',       // Super light
                100: '#f5f5f5',       // Almost white
          }
        }
      },
    },
  },
  plugins: [],
}