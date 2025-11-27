export default function Loader() {
  return (
    <div className="flex flex-col items-center justify-center py-12">
      <div className="animate-spin rounded-full h-16 w-16 border-b-4 border-indigo-600 dark:border-bumblebee-yellow mb-4"></div>
      <p className="text-gray-600 dark:text-bumblebee-gray-300 text-lg">Analyzing your resume...</p>
    </div>
  );
}