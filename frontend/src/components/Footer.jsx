export default function Footer() {
  return (
    <footer className="mt-16 pb-8">
      <div className="max-w-4xl mx-auto px-4">
        {/* Divider */}
        <div className="border-t border-gray-200 dark:border-bumblebee-gray-800 mb-6"></div>
        
        {/* Content */}
        <div className="text-center space-y-3">
          {/* Supported Platforms */}
          <div className="bg-blue-50 dark:bg-bumblebee-gray-800 border border-blue-200 dark:border-bumblebee-gray-700 rounded-lg p-4 inline-block">
            <p className="text-sm text-gray-700 dark:text-bumblebee-gray-300">
              <span className="font-semibold">📋 Currently Supported:</span> Greenhouse Job Boards Only
            </p>
          </div>

          {/* Copyright */}
          <p className="text-sm text-gray-500 dark:text-bumblebee-gray-400">
            © 2025 ApplyBee 🐝 • Built to make job applications easier
          </p>
        </div>
      </div>
    </footer>
  );
}