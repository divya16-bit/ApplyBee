export default function DarkModeToggle({ isDark, setIsDark }) {
  return (
    <button
      onClick={() => setIsDark(!isDark)}
      className="fixed top-4 right-4 p-3 rounded-full bg-gray-200 dark:bg-bumblebee-gray-800 hover:bg-gray-300 dark:hover:bg-bumblebee-gray-700 border-2 border-transparent dark:border-bumblebee-yellow transition-all shadow-lg z-50"
      aria-label="Toggle dark mode"
    >
       {isDark ? (
        // Sun icon - shows in dark mode (click to go light)
        <svg className="w-6 h-6 text-bumblebee-yellow" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 3v1m0 16v1m9-9h-1M4 12H3m15.364 6.364l-.707-.707M6.343 6.343l-.707-.707m12.728 0l-.707.707M6.343 17.657l-.707.707M16 12a4 4 0 11-8 0 4 4 0 018 0z" />
        </svg>
      ) : (
        // Moon icon - shows in light mode (click to go dark)
        <svg className="w-6 h-6 text-gray-700" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M20.354 15.354A9 9 0 018.646 3.646 9.003 9.003 0 0012 21a9.003 9.003 0 008.354-5.646z" />
        </svg>
      )}
    </button>
  );
}