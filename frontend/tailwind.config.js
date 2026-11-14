/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        cream: "#F5EAD7",
        sand: "#E8D9BA",
        forest: "#14504F",
        terracotta: "#C8341F",
        ochre: "#D9892B",
        river: "#1F8A8A",
      },
      fontFamily: {
        heading: ["'Bricolage Grotesque'", "sans-serif"],
        body: ["'DM Sans'", "sans-serif"],
        arabic: ["'Noto Kufi Arabic'", "'Cairo'", "sans-serif"],
      },
    },
  },
  plugins: [],
}
